import os
import subprocess
from itertools import groupby
from typing import List, Optional, Counter

from git import Repo

from grex.types import RebaseItem


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

        all_files_included = all(
            change.modified for change in item.file_changes.values()
        )
        no_files_included = all(
            not change.modified for change in item.file_changes.values()
        )

        if item.action == "drop" or all_files_included:
            # No exec commands needed. Just apply the rebase action as normal.
            rebase_todo_text += (
                f"{item.action} {item.commit.hexsha[:7]} {first_message_line}\n"
            )
        elif no_files_included:
            # No files included, so just drop it.
            rebase_todo_text += f"drop {item.commit.hexsha[:7]} {first_message_line}\n"
        else:
            # This rebase item only contains a subset of the files of the original commit. Pick the
            # commit, then call grex-edit-rebase-item in an exec command. The edit-rebase-item command will
            # edit the commit to only include the specified files, and apply the specified rebase action.

            rebase_todo_text += f"pick {item.commit.hexsha[:7]} {first_message_line}\n"

            changed_files = " ".join(
                change.path for change in item.file_changes.values() if change.modified
            )
            rebase_todo_text += (
                f"exec grex-edit-rebase-item -a {item.action} {changed_files}\n"
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
