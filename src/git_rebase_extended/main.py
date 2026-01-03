import argparse
import os
import subprocess
import sys
from typing import List, Optional

from git import Repo, Commit
from textual.app import App

from git_rebase_extended.main_screen import MainScreen


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
        # build rebase file
        rebase_todo = ""
        for item in self._main_screen.get_rebase_items():
            rebase_todo += (
                f"{item.action} {item.commit.hexsha[:7]} {item.commit.message}\n"
            )

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

    app = GitRebaseExtendedApp(commits)
    app.run()

    print(app.get_command_output())


if __name__ == "__main__":
    main()
