import os
import re
import shutil
import tempfile
from typing import List, Tuple, Optional

from git import GitCommandError, Repo, Commit

from splitsquash.types import RebaseItem


class MergeConflictDetectorSingleton:
    instance = None
    original_repo = Repo(".")
    temp_dir: Optional[str] = None
    temp_repo: Optional[Repo] = None

    def __new__(cls):
        if cls.instance is None:
            cls.instance = super().__new__(cls)
        return cls.instance

    def setup(self):
        self.temp_dir = tempfile.mkdtemp()
        self.temp_repo = self.original_repo.clone(self.temp_dir)

    def cleanup(self):
        shutil.rmtree(self.temp_dir)
        self.temp_dir = None
        self.temp_repo = None

    def check_for_merge_conflicts(
        self,
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

        self.temp_repo.git.checkout(onto)

        for commit_index, item in enumerate(rebase_items):
            if item.action == "drop":
                continue

            # Cherry-pick without commiting, remove the excluded files, then commit.

            try:
                self.temp_repo.git.cherry_pick(item.commit, n=True)
            except GitCommandError:
                # Cherry-pick caused a merge conflict.
                # This is only a genuine merge conflict if the conflict is on an included file. Check
                # if it is on an included file.
                for change in item.file_changes.values():
                    if (
                        change.included
                        and change.path in self.temp_repo.index.unmerged_blobs()
                        and change.path not in conflicting_files
                    ):
                        # Merge conflict on included file
                        conflicting_files.add(change.path)
                        conflicting_commit_indices.append(commit_index)

            # remove excluded files and conflicting files from the index before committing
            for change in item.file_changes.values():
                if change.included and change.path not in conflicting_files:
                    continue

                unmerged_blobs = self.temp_repo.index.unmerged_blobs()

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
                    self.temp_repo.index.resolve_blobs(target_branch_blob).write()
                else:
                    # No merge conflict. Just reset the file.
                    self.temp_repo.index.reset(paths=[change.path], working_tree=True)
                    continue

            self.temp_repo.index.commit(item.commit.message)

        return conflicting_commit_indices

    def get_merge_conflict_text(
        self,
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

        self.temp_repo.git.checkout(onto)

        for commit in commits[:-1]:
            self.temp_repo.git.cherry_pick(commit)
            self.temp_repo.index.commit(commit.message)

        # Expect the last commit to cause a merge conflict, so cherry-picking
        # should raise a GitCommandError.
        try:
            self.temp_repo.git.cherry_pick(commits[-1])
        except GitCommandError:
            pass
        else:
            raise RuntimeError("Expected a merge conflict, but didn't get one.")

        # add merge conflicts from each file to merge_conflict_text
        for diff in self.temp_repo.index.diff(None).iter_change_type("M"):
            # add heading with file name
            separator_line = "-" * (len(diff.b_path) + 10) + "\n"
            merge_conflict_text += separator_line + diff.b_path + "\n" + separator_line

            with open(os.path.join(self.temp_repo.working_dir, diff.b_path), "r") as f:
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
