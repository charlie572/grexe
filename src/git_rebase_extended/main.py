import argparse
from os import path
from typing import List, Optional

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


class GitRebaseExtendedApp(App):
    CSS_PATH = "main.tcss"

    BINDINGS = [
        ("j", "move_down", "Move the cursor down."),
        ("k", "move_up", "Move the cursor up."),
        ("v", "select", "Select commit."),
    ]

    def __init__(self, commits: List[Commit], *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._commits: List[Commit] = commits
        self._commit_widgets: Optional[List[List[Widget]]] = None
        self._active_index = None

    def _set_active(self, index):
        # clear previous active commit
        for widgets in self._commit_widgets:
            for widget in widgets:
                widget.remove_class("active")

        # set background of new active commit
        widgets = self._commit_widgets[index]
        for widget in widgets:
            widget.add_class("active")

        self._active_index = index

    def action_move_up(self):
        new_index = max(0, self._active_index - 1)
        self._set_active(new_index)

    def action_move_down(self):
        new_index = min(len(self._commits) - 1, self._active_index + 1)
        self._set_active(new_index)

    def action_select(self):
        widgets = self._commit_widgets[self._active_index]
        for widget in widgets:
            widget.toggle_class("selected")

    def compose(self):
        files = sum(
            [list(commit.stats.files.keys()) for commit in self._commits], start=[]
        )
        files = list(set(files))

        with Grid() as grid:
            grid.styles.grid_columns = "7 10 2fr " + "1fr " * len(files)
            grid.styles.grid_rows = "1"
            grid.styles.grid_size_rows = len(self._commits) + 1
            grid.styles.grid_size_columns = 3 + len(files)
            grid.styles.height = len(self._commits)

            # header row
            yield Label("")
            yield Label("")
            yield Label("")
            for file in files:  # add file names in file columns headers
                _, filename = path.split(file)
                yield Label(filename, classes="filename")

            # commit rows
            self._commit_widgets = []
            for commit in self._commits:
                widgets = [
                    Label("pick", classes="rebase_action"),
                    Label(commit.hexsha[:7], classes="hexsha"),
                ]

                first_message_line = commit.message.split("\n")[0]
                message_label = Label(first_message_line, classes="commit_message")
                widgets.append(message_label)

                for file in files:
                    widgets.append(FileChange(file in commit.stats.files))

                self._commit_widgets.append(widgets)
                yield from widgets

    def on_mount(self):
        self._set_active(0)


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


if __name__ == "__main__":
    main()
