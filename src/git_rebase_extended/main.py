import argparse
import os
import subprocess
import sys
from copy import deepcopy
from dataclasses import dataclass
from os import path
from typing import List, Literal, Tuple

from git import Repo, Commit
from textual.app import App
from textual.containers import Grid
from textual.widget import Widget
from textual.widgets import Label


class FileChange(Widget):
    def __init__(self, changed: bool, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._changed = changed

    def render(self):
        content = "⬤" if self._changed else " "
        return f" [on $secondary]{content} [/on $secondary] "


RebaseAction = Literal["pick", "drop", "edit", "reword", "squash", "fixup"]


@dataclass
class RebaseItem:
    commit: Commit
    action: RebaseAction = "pick"


class GitRebaseExtendedApp(App):
    CSS_PATH = "main.tcss"

    BINDINGS = [
        ("j", "move_down", "Move the cursor down."),
        ("k", "move_up", "Move the cursor up."),
        ("v", "select", "Select commit."),
        ("p", "pick", "Set the commit's action to 'pick'."),
        ("f", "fixup", "Set the commit's action to 'fixup'."),
        ("s", "squash", "Set the commit's action to 'squash'."),
        ("e", "edit", "Set the commit's action to 'edit'."),
        ("r", "reword", "Set the commit's action to 'reword'."),
        ("d", "drop", "Set the commit's action to 'drop'."),
        ("enter", "submit", "Submit and perform rebase."),
        ("m", "move_commits", "Move commits."),
        ("ctrl+a", "select_all", "Select all/none."),
        ("ctrl+z", "undo", "Undo"),
        ("ctrl+y", "redo", "Redo"),
    ]

    def __init__(self, commits: List[Commit], *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._history: List[Tuple[RebaseItem, ...]] = [
            tuple(RebaseItem(commit) for commit in commits)
        ]
        self._history_index = 0
        self._active_index = 0
        self._selected = [False] * len(commits)

        self._state: Literal["idle", "moving"] = "idle"

        self._command_output = ""

        self._files = sum(
            [list(commit.stats.files.keys()) for commit in commits], start=[]
        )
        self._files = list(set(self._files))

    @property
    def num_commits(self):
        return len(self._history[0])

    def _get_rebase_items(self):
        return self._history[self._history_index]

    def _set_rebase_items(self, rebase_items: Tuple[RebaseItem, ...]):
        self._history = self._history[: self._history_index + 1] + [rebase_items]
        self._history_index += 1

    def action_undo(self):
        self._history_index = max(0, self._history_index - 1)
        self.refresh(recompose=True)

    def action_redo(self):
        self._history_index = min(self.num_commits - 1, self._history_index + 1)
        self.refresh(recompose=True)

    def _get_items_to_modify(self, rebase_items=None):
        """Get the rebase items to modify

        This can be used when moving multiple items, or changing the rebase action of
        multiple items.

        If some items are selected, this function will return them. If no items are
        selected, the active item will be returned (the one currently under the
        cursor).
        """
        if rebase_items is None:
            rebase_items = self._get_rebase_items()

        selected_items = self._get_selected(rebase_items)
        if len(selected_items) == 0:
            return [rebase_items[self._active_index]]
        else:
            return selected_items

    def _get_indices_to_modify(self):
        """Get the indices of the rebase items to modify

        This can be used when moving multiple items, or changing the rebase action of
        multiple items.

        If some items are selected, this function will return them. If no items are
        selected, the active item will be returned (the one currently under the
        cursor).
        """
        selected_indices = self._get_selected(indices=True)
        if len(selected_indices) == 0:
            return [self._active_index]
        else:
            return selected_indices

    def _get_selected(self, rebase_items=None, indices=False):
        if rebase_items is None:
            rebase_items = self._get_rebase_items()

        result = []
        for i, item in enumerate(rebase_items):
            if self._selected[i]:
                if indices:
                    result.append(i)
                else:
                    result.append(item)

        return result

    def get_command_output(self):
        return self._command_output

    def action_submit(self):
        # build rebase file
        rebase_todo = ""
        for action, commit in self._get_rebase_items():
            rebase_todo += f"{action} {commit.hexsha[:7]} {commit.message}\n"

        # run git rebase command
        # Custom editor command outputs rebase_todo to file.
        env = os.environ.copy()
        env["GIT_EDITOR"] = f"echo {repr(rebase_todo)}"
        process = subprocess.run(
            ["git", "rebase", "-i", *sys.argv[1:]],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )

        self._command_output += process.stdout.decode()

        self.exit()

    def action_move_commits(self):
        if self._state == "idle":
            rebase_items = list(deepcopy(self._get_rebase_items()))

            # remove selected widgets
            indices_to_move = self._get_indices_to_modify()
            items_to_move = [rebase_items.pop(i) for i in reversed(indices_to_move)]

            # insert widgets back again as one block, with the bottom commit at its original index
            dest_index = indices_to_move[-1] - len(indices_to_move) + 1
            for item in items_to_move:
                rebase_items.insert(dest_index, item)

            self._selected[:] = [False] * self.num_commits
            for i in range(dest_index, dest_index + len(items_to_move)):
                self._selected[i] = True

            self._state = "moving"

            self._set_rebase_items(tuple(rebase_items))
            self.refresh(recompose=True)
        elif self._state == "moving":
            selected_indices = self._get_selected(indices=True)

            self._active_index = selected_indices[0]
            self._selected[:] = [False] * self.num_commits

            self._state = "idle"

            self.refresh(recompose=True)

    def action_move_up(self):
        if self._state == "idle":
            self._active_index = max(0, self._active_index - 1)
            self.refresh(recompose=True)
        elif self._state == "moving":
            rebase_items = list(deepcopy(self._get_rebase_items()))
            selected_indices = [i for i in range(self.num_commits) if self._selected[i]]
            if selected_indices[0] == 0:
                return

            item_before_selected = rebase_items.pop(selected_indices[0] - 1)
            rebase_items.insert(selected_indices[-1], item_before_selected)
            self._set_rebase_items(tuple(rebase_items))

            self._selected[:] = [False] * self.num_commits
            for i in selected_indices:
                self._selected[i - 1] = True

            self.refresh(recompose=True)

    def action_move_down(self):
        rebase_items = list(deepcopy(self._get_rebase_items()))

        if self._state == "idle":
            self._active_index = min(self.num_commits - 1, self._active_index + 1)
            self.refresh(recompose=True)
        elif self._state == "moving":
            selected_indices = self._get_selected(indices=True)
            if selected_indices[-1] == len(rebase_items) - 1:
                return

            item_after_selected = rebase_items.pop(selected_indices[-1] + 1)
            rebase_items.insert(selected_indices[0], item_after_selected)
            self._set_rebase_items(tuple(rebase_items))

            self._selected[:] = [False] * len(self._selected)
            for i in selected_indices:
                self._selected[i + 1] = True

            self.refresh(recompose=True)

    def action_select(self):
        self._selected[self._active_index] = not self._selected[self._active_index]
        self.refresh(recompose=True)

    def action_select_all(self):
        if self._state != "idle":
            return

        selected = not self._selected[self._active_index]
        self._selected[:] = [selected] * self.num_commits
        self.refresh(recompose=True)

    def _set_rebase_action(self, action: RebaseAction):
        if self._state != "idle":
            return

        rebase_items = deepcopy(self._get_rebase_items())

        for item in self._get_items_to_modify(rebase_items):
            item.action = action

        self._set_rebase_items(rebase_items)
        self.refresh(recompose=True)

    def action_edit(self):
        self._set_rebase_action("edit")

    def action_pick(self):
        self._set_rebase_action("pick")

    def action_fixup(self):
        self._set_rebase_action("fixup")

    def action_squash(self):
        self._set_rebase_action("squash")

    def action_drop(self):
        self._set_rebase_action("drop")

    def action_reword(self):
        self._set_rebase_action("reword")

    def compose(self):
        rebase_items = self._get_rebase_items()

        with Grid() as grid:
            grid.id = "main_grid"
            grid.styles.grid_columns = "7 10 2fr " + "1fr " * len(self._files)
            grid.styles.grid_rows = "1"
            grid.styles.grid_size_rows = len(rebase_items) + 1
            grid.styles.grid_size_columns = 3 + len(self._files)
            grid.styles.height = len(rebase_items) + 1

            # header row
            yield Label("")
            yield Label("")
            yield Label("")
            for file in self._files:  # add file names in file columns headers
                _, filename = path.split(file)
                yield Label(filename, classes="filename")

            # commit rows
            for i, item in enumerate(rebase_items):
                classes = []
                if i == self._active_index and self._state == "idle":
                    classes.append("active")
                if self._selected[i]:
                    classes.append("selected")
                classes = " ".join(classes)

                yield Label(item.action, classes=f"rebase_action {classes}")

                yield Label(item.commit.hexsha[:7], classes=f"hexsha {classes}")

                first_message_line = item.commit.message.split("\n")[0]
                yield Label(first_message_line, classes=f"commit_message {classes}")

                for file in self._files:
                    yield FileChange(file in item.commit.stats.files, classes=classes)


def main():
    parser = argparse.ArgumentParser(
        "git-rebase-extended",
        description=(
            "A CLI for performing interactive rebases with extra features.\n"
            "\n"
            "Arguments will be passed to `git rebase`.\n"
        ),
    )
    parser.add_argument("branch")
    args = parser.parse_args()

    repo = Repo(".")
    commits = list(repo.iter_commits(f"{args.branch}..{repo.head.commit}"))

    app = GitRebaseExtendedApp(commits)
    app.run()

    print(app.get_command_output())


if __name__ == "__main__":
    main()
