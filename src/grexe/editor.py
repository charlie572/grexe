import argparse
from typing import List, Optional

from git import Repo
from textual.app import App

from grexe.main_screen import MainScreen
from grexe.rebasing import parse_rebase_items, create_rebase_todo_text
from grexe.types import RebaseItem


class GitRebaseExtendedEditor(App):
    CSS_PATH = "main.tcss"

    BINDINGS = [
        ("enter", "submit", "Submit and perform rebase."),
    ]

    def __init__(self, rebase_items: List[RebaseItem], *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._main_screen: Optional[MainScreen] = None
        self._rebase_items = rebase_items
        self._result: Optional[str] = None

    def action_quit(self) -> None:
        # Return exit code 1, so the rebase isn't performed.
        exit(1)

    def get_result(self):
        return self._result

    def action_submit(self):
        rebase_items = self._main_screen.get_rebase_items()
        self._result = create_rebase_todo_text(rebase_items)
        self.exit()

    def on_mount(self):
        self._main_screen = MainScreen(self._rebase_items)
        self.push_screen(self._main_screen)


def main():
    parser = argparse.ArgumentParser(
        "git-rebase-extended-editor",
        description="An editor for git rebase todo files.",
    )
    parser.add_argument("rebase_todo_file", type=str)
    args = parser.parse_args()

    repo = Repo(".")

    # parse rebase to-do file
    with open(args.rebase_todo_file, "r") as f:
        rebase_todo_text = f.read()
    rebase_items = parse_rebase_items(rebase_todo_text, repo)

    app = GitRebaseExtendedEditor(rebase_items)
    app.run()

    new_rebase_todo_text = app.get_result()
    if new_rebase_todo_text is not None:
        with open(args.rebase_todo_file, "w") as f:
            f.write(new_rebase_todo_text)


if __name__ == "__main__":
    main()
