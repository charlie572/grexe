import argparse
import os
import subprocess
import sys
from typing import List, Optional

from git import Repo, Commit
from textual.app import App

from git_rebase_extended.main_screen import MainScreen
from git_rebase_extended.rebasing import rebase


class GitRebaseExtendedApp(App):
    CSS_PATH = "main.tcss"

    BINDINGS = [
        ("enter", "submit", "Submit and perform rebase."),
    ]

    def __init__(self, commits: List[Commit], *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._main_screen: Optional[MainScreen] = None
        self._commits = commits
        self._command_output = ""

    def get_command_output(self):
        return self._command_output

    def action_submit(self):
        output = rebase(self._main_screen.get_rebase_items(), sys.argv[1:])
        self._command_output += output

        self.exit()

    def on_mount(self):
        self._main_screen = MainScreen(self._commits)
        self.push_screen(self._main_screen)


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
    commits.reverse()

    app = GitRebaseExtendedApp(commits)
    app.run()

    print(app.get_command_output())


if __name__ == "__main__":
    main()
