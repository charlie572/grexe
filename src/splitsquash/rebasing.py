import os
import re
import shutil
import subprocess
from itertools import groupby
from tempfile import TemporaryDirectory
from typing import List, Optional, Tuple

from git import Repo, Commit, GitCommandError

from splitsquash.types import RebaseItem


def check_rebase_is_valid(rebase_items: List[RebaseItem]) -> List[str]:
    # group together items copied from the same commit
    items_by_commit = groupby(rebase_items, lambda item: item.commit.hexsha)

    errors = []

    # check that no file change is repeated
    for commit_sha, items_for_commit in items_by_commit:
        files_seen = set()
        for item in items_for_commit:
            for file_path, file_change in item.file_changes.items():
                if not file_change.included:
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
            change.included for change in item.file_changes.values()
        )
        no_files_included = all(
            not change.included for change in item.file_changes.values()
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
            # commit, then call ss-edit-rebase-item in an exec command. The edit-rebase-item command will
            # edit the commit to only include the specified files, and apply the specified rebase action.

            rebase_todo_text += f"pick {item.commit.hexsha[:7]} {first_message_line}\n"

            changed_files = " ".join(
                change.path for change in item.file_changes.values() if change.included
            )
            rebase_todo_text += (
                f"exec ss-edit-rebase-item -a {item.action} {changed_files}\n"
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


def currently_rebasing_on(repo: Repo) -> Commit:
    with open(".git/rebase-merge/onto", "r") as f:
        commit_hash = f.read()

    return repo.commit(commit_hash)


def check_for_merge_conflicts(
    repo: Repo,
    rebase_items: Tuple[RebaseItem, ...],
    onto: Commit,
) -> List[int]:
    """Given a repo list of commits to apply, return the indices of the commits which will cause merge conflicts

    This function only detects the first merge conflict for each file. There may be later conflicts, but this function
    doesn't return them.We can't know what the file will look like after the first merge conflict is resolved, so it is
    difficult to know if there will be merge conflicts later. One solution could be to keep track of lines the
    conflicted, and keep checking for conflicts on lines that haven't conflicted yet. But for now, it just detects the
    first conflict on each file.

    The output of this function is reliable if there are no edits. So if no commits are modified during the rebase,
    then the commits at the indices it returns will definitely cause merge conflicts. But if there are edits, then these
    may cause additional merge conflicts, or fix later merge conflicts.
    """

    # 1. Create a temporary clone of the repo.
    # 2. Apply each commit in turn in the temporary repo.
    # 3. Terminate if there is a merge conflict.
    # 4. Clean up the temporary repo.

    conflicting_commit_indices = []

    # File paths that have conflicted so far. Make sure these aren't committed
    # again after a conflict is detected, since we are only looking for the
    # first conflict for each file.
    conflicting_files = set()

    with TemporaryDirectory() as temp_dir:
        temp_repo = repo.clone(temp_dir)

        temp_repo.git.checkout(onto)

        for commit_index, item in enumerate(rebase_items):
            if item.action == "drop":
                continue

            # Cherry-pick without commiting, remove the excluded files, then commit.

            try:
                temp_repo.git.cherry_pick(item.commit, n=True)
            except GitCommandError:
                # Cherry-pick caused a merge conflict.
                # This is only a genuine merge conflict if the conflict is on an included file. Check
                # if it is on an included file.
                for change in item.file_changes.values():
                    if (
                        change.included
                        and change.path in temp_repo.index.unmerged_blobs()
                        and change.path not in conflicting_files
                    ):
                        # Merge conflict on included file
                        conflicting_files.add(change.path)
                        conflicting_commit_indices.append(commit_index)

            # remove excluded files and conflicting files from the index before committing
            for change in item.file_changes.values():
                if change.included and change.path not in conflicting_files:
                    continue

                unmerged_blobs = temp_repo.index.unmerged_blobs()

                # check if there was a merge conflict on this excluded file
                if change.path in unmerged_blobs:
                    # Merge conflict
                    # Reset the file back to what it was before the cherry-pick (the stage 2 blob).
                    target_branch_blob = [
                        blob
                        for (stage, blob) in unmerged_blobs[change.path]
                        if stage == 2
                    ]
                    assert len(target_branch_blob) == 1
                    temp_repo.index.resolve_blobs(target_branch_blob).write()
                else:
                    # No merge conflict. Just reset the file.
                    temp_repo.index.reset(paths=[change.path], working_tree=True)
                    continue

            temp_repo.index.commit(item.commit.message)

    return conflicting_commit_indices


def get_merge_conflict_text(
    repo: Repo,
    commits: List[Commit],
    onto: Commit,
    num_context_lines: int = 3,
):
    """Get the text of a merge conflict

    The last commit in the list must cause the merge conflict.
    """
    merge_conflict_regex = re.compile(
        r"<<<<<<< HEAD\n(.*)\n=======\n(.*)\n>>>>>>> [0-9a-f]{7} \(.*\)",
        flags=re.DOTALL,
    )
    merge_conflict_text = ""

    with TemporaryDirectory() as temp_dir:
        temp_repo = repo.clone(temp_dir)

        temp_repo.git.checkout(onto)

        for commit in commits[:-1]:
            temp_repo.git.cherry_pick(commit)
            temp_repo.index.commit(commit.message)

        # Expect the last commit to cause a merge conflict, so cherry-picking
        # should raise a GitCommandError.
        try:
            temp_repo.git.cherry_pick(commits[-1])
        except GitCommandError:
            pass
        else:
            raise RuntimeError("Expected a merge conflict, but didn't get one.")

        # add merge conflicts from each file to merge_conflict_text
        for diff in temp_repo.index.diff(None).iter_change_type("M"):
            # add heading with file name
            separator_line = "-" * (len(diff.b_path) + 10) + "\n"
            merge_conflict_text += separator_line + diff.b_path + "\n" + separator_line

            with open(os.path.join(temp_repo.working_dir, diff.b_path), "r") as f:
                file_content = f.read()

            # add merge conflict text for this file
            for match in merge_conflict_regex.finditer(file_content):
                # get merge conflict lines from match, and add context lines
                previous_lines = file_content[: match.start()].split("\n")
                # The last element will be empty, since the match begins just before a new line. Remove it.
                previous_lines.pop(-1)
                conflict_lines = match.group(0).split("\n")
                next_lines = file_content[match.end()].split("\n")
                display_lines = (
                    previous_lines[:-num_context_lines]
                    + conflict_lines
                    + next_lines[:num_context_lines]
                )

                # add line numbers
                first_line_number = max(1, len(previous_lines) - num_context_lines + 1)
                last_line_number = first_line_number + len(display_lines) - 1
                line_number_digits = len(str(last_line_number))
                display_lines = [
                    f"{first_line_number + n:{line_number_digits}} {line}"
                    for n, line in enumerate(display_lines)
                ]

                merge_conflict_text += "\n".join(display_lines)

    return merge_conflict_text
