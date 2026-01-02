import argparse
import os
import subprocess
import sys
from os import path
from typing import List, Optional, Literal, Tuple

from dataclasses import dataclass

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
    selected: bool = False
    active: bool = False


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
        ("enter", "submit", "Submit and perform rebase."),
        ("m", "move_commits", "Move commits."),
        ("ctrl+a", "select_all", "Select all/none."),
    ]

    def __init__(self, commits: List[Commit], *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._rebase_items = [RebaseItem(commit) for commit in commits]
        self._state: Literal["idle", "moving"] = "idle"

        self._command_output = ""

        self._files = sum(
            [list(commit.stats.files.keys()) for commit in commits], start=[]
        )
        self._files = list(set(self._files))

    def _get_items_to_modify(self):
        """Get the rebase items to modify

        This can be used when moving multiple items, or changing the rebase action of
        multiple items.

        If some items are selected, this function will return them. If no items are
        selected, the active item will be returned (the one currently under the
        cursor).
        """
        selected_items = self._get_selected()
        if len(selected_items) == 0:
            _, active_item = self._get_active()
            if active_item is None:
                return []
            else:
                return [active_item]
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
        selected_indices = self._get_selected_indices()
        if len(selected_indices) == 0:
            active_index, _ = self._get_active()
            if active_index is None:
                return []
            else:
                return [active_index]
        else:
            return selected_indices

    def _get_active(self):
        for i, item in enumerate(self._rebase_items):
            if item.active:
                return i, item

        return None, None

    def _get_selected(self):
        result = []
        for i, item in enumerate(self._rebase_items):
            if item.selected:
                result.append(item)

        return result

    def _get_selected_indices(self):
        result = []
        for i, item in enumerate(self._rebase_items):
            if item.selected:
                result.append(i)

        return result

    def get_command_output(self):
        return self._command_output

    def _set_active(self, index):
        for item in self._rebase_items:
            item.active = False

        self._rebase_items[index].active = True

        self.refresh(recompose=True)

    def action_submit(self):
        # build rebase file
        rebase_todo = ""
        for action, commit in self._rebase_items:
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
            # remove selected widgets
            indices_to_move = self._get_indices_to_modify()
            items_to_move = [
                self._rebase_items.pop(i) for i in reversed(indices_to_move)
            ]

            # insert widgets back again as one block, with the bottom commit at its original index
            dest_index = indices_to_move[-1] - len(indices_to_move) + 1
            for item in items_to_move:
                self._rebase_items.insert(dest_index, item)

            self._state = "moving"

            self.refresh(recompose=True)
        elif self._state == "moving":
            selected_indices = self._get_selected_indices()

            self._set_active(selected_indices[0])
            for item in self._rebase_items:
                item.selected = False

            self._state = "idle"

            self.refresh(recompose=True)

    def action_move_up(self):
        if self._state == "idle":
            index, _ = self._get_active()
            new_index = max(0, index - 1)
            self._set_active(new_index)
            self.refresh(recompose=True)
        elif self._state == "moving":
            selected_indices = self._get_selected_indices()
            if selected_indices[0] > 0:
                item_before_selected = self._rebase_items.pop(selected_indices[0] - 1)
                self._rebase_items.insert(selected_indices[-1], item_before_selected)
                self.refresh(recompose=True)

    def action_move_down(self):
        if self._state == "idle":
            index, _ = self._get_active()
            new_index = min(len(self._rebase_items) - 1, index + 1)
            self._set_active(new_index)
            self.refresh(recompose=True)
        elif self._state == "moving":
            selected_indices = self._get_selected_indices()
            if selected_indices[-1] < len(self._rebase_items) - 1:
                item_after_selected = self._rebase_items.pop(selected_indices[-1] + 1)
                self._rebase_items.insert(selected_indices[0], item_after_selected)
                self.refresh(recompose=True)

    def action_select(self):
        _, item = self._get_active()
        item.selected = not item.selected
        self.refresh(recompose=True)

    def action_select_all(self):
        if self._state != "idle":
            return

        _, active_item = self._get_active()
        if not active_item:
            raise RuntimeError()

        selected = not active_item.selected
        for item in self._rebase_items:
            item.selected = selected

        self.refresh(recompose=True)

    def _set_rebase_action(self, action: RebaseAction):
        if self._state != "idle":
            return

        for item in self._get_items_to_modify():
            item.action = action

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

    def compose(self):
        with Grid() as grid:
            grid.id = "main_grid"
            grid.styles.grid_columns = "7 10 2fr " + "1fr " * len(self._files)
            grid.styles.grid_rows = "1"
            grid.styles.grid_size_rows = len(self._rebase_items) + 1
            grid.styles.grid_size_columns = 3 + len(self._files)
            grid.styles.height = len(self._rebase_items) + 1

            # header row
            yield Label("")
            yield Label("")
            yield Label("")
            for file in self._files:  # add file names in file columns headers
                _, filename = path.split(file)
                yield Label(filename, classes="filename")

            # commit rows
            for item in self._rebase_items:
                classes = []
                if item.active:
                    classes.append("active")
                if item.selected:
                    classes.append("selected")
                classes = " ".join(classes)

                yield Label(item.action, classes=f"rebase_action {classes}")

                yield Label(item.commit.hexsha[:7], classes=f"hexsha {classes}")

                first_message_line = item.commit.message.split("\n")[0]
                yield Label(first_message_line, classes=f"commit_message {classes}")

                for file in self._files:
                    yield FileChange(file in item.commit.stats.files, classes=classes)

    def on_mount(self):
        self._set_active(0)
        self.refresh(recompose=True)


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
