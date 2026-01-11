import os
import subprocess
from itertools import groupby
from typing import List, Optional, Counter

from git import Repo

from git_rebase_extended.types import RebaseItem


def check_rebase_is_valid(rebase_items: List[RebaseItem]) -> List[str]:
    # group together items copied from the same commit
    items_by_commit = groupby(rebase_items, lambda item: item.commit.hexsha)

    errors = []

    # check that no file change is repeated
    for commit_sha, items_for_commit in items_by_commit:
        files_seen = set()
        for item in items_for_commit:
            for file_path, file_change in item.file_changes.items():
                if not file_change.modified:
                    continue
                elif file_path in files_seen:
                    errors.append(
                        f"File {file_path} in commit {commit_sha[:7]} has been included multiple times."
                    )
                else:
                    files_seen.add(file_path)

    return errors


def parse_rebase_items(rebase_todo: str, repo: Repo) -> List[RebaseItem]:
    result = []
    for line in rebase_todo.split("\n"):
        if line.startswith("#") or len(line.strip()) == 0:
            continue
        action, sha, *message = line.split(" ")
        commit = repo.commit(sha)
        result.append(RebaseItem(action, commit))

    return result


def create_rebase_todo_text(rebase_items: List[RebaseItem]) -> str:
    rebase_todo_text = ""
    for item in rebase_items:
        first_message_line = item.commit.message.split("\n")[0]
        rebase_todo_text += (
            f"{item.action} {item.commit.hexsha[:7]} {first_message_line}\n"
        )

        if all(change.modified for change in item.file_changes.values()):
            continue

        # This rebase item only contains a subset of the files of the original commit. Add an exec command which removes
        # the files that aren't included from the commit.
        #
        # Newline characters seem to work differently in rebase exec commands than in the regular bash shell. Through
        # trial and error, I've found a way to include newline characters in the commit message. I output the commit
        # message to .git/COMMIT_EDITMSG, using a single quote string and no $, then I input that file to `git commit`.
        # I don't know why this works, or why the methods that work in a normal bash shell don't work here. Any file
        # should work, but I'm using .git/COMMIT_EDITMSG because it's the file git normally uses for editing commit
        # messages.
        add_commands = [
            f'git add "{change.path}"'
            for change in item.file_changes.values()
            if change.modified
        ]
        commit_message_bash_string = "'" + repr(item.commit.message)[1:-1] + "'"
        rebase_todo_text += (
            "exec git reset --mixed HEAD~1; "
            + f"{'; '.join(add_commands)}; "
            + f"echo {commit_message_bash_string} > .git/COMMIT_EDITMSG; "
            + f"git commit -F .git/COMMIT_EDITMSG; "
            + f"git restore .\n"
        )

    return rebase_todo_text


def rebase(
    rebase_items: List[RebaseItem],
    rebase_args: Optional[List[str]] = None,
) -> str:
    if rebase_args is None:
        rebase_args = []

    # build rebase file
    rebase_todo = ""
    for item in rebase_items:
        rebase_todo += f"{item.action} {item.commit.hexsha[:7]} {item.commit.message}\n"

    # run git rebase command
    # Custom editor command outputs rebase_todo to file.
    env = os.environ.copy()
    env["GIT_EDITOR"] = f"echo {repr(rebase_todo)}"
    process = subprocess.run(
        ["git", "rebase", "-i", *rebase_args],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    return process.stdout.decode()
