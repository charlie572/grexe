import hashlib
import os
import re
import shutil
import tempfile
import threading
from dataclasses import dataclass
from datetime import datetime
from typing import List, Tuple, Optional, Dict

from git import GitCommandError, Repo

from splitsquash.rebasing import currently_rebasing_on
from splitsquash.types import RebaseItem


class CherryPickCacheKey:
    """A hashable representation of a bash commit hash and a rebase item to be cherry-picked on top of it"""

    def __init__(self, base_hash: Optional[str], cherry_picked_item: RebaseItem):
        self._base_hash = base_hash
        self._cherry_picked_hash = cherry_picked_item.commit.hexsha

        # the file paths need to be sorted to make the hash consistent
        file_paths = [
            change.path
            for change in cherry_picked_item.file_changes.values()
            if change.included
        ]
        self._included_file_paths = tuple(sorted(file_paths))

    def nonrandom_hash(self):
        """Get a thread-safe, non-random hash

        Python adds an unpredictable salt to the hash values. This salt
        is the same for the duration of a particular invocation of Python,
        but it is different for different threads. This means this class
        cannot be used in multiple threads. If you only need this class
        for a key in a dictionary, then you can use this method as the key.
        This method will return the same value in every thread, with the
        same data given as input.
        """
        return hashlib.sha1(
            self._base_hash.encode()
            + self._cherry_picked_hash.encode()
            + b"".join(p.encode() for p in self._included_file_paths)
        ).digest()

    def __hash__(self):
        obj = (self._base_hash, self._cherry_picked_hash, self._included_file_paths)
        return hash(obj)

    def __eq__(self, other):
        if not isinstance(other, CherryPickCacheKey):
            return False

        obj = (self._base_hash, self._cherry_picked_hash, self._included_file_paths)
        other_obj = (
            other._base_hash,
            other._cherry_picked_hash,
            other._included_file_paths,
        )
        return obj == other_obj


@dataclass
class CherryPickCacheValue:
    """Represents the result of a cherry-pick in the check_for_merge_conflicts function

    This cherry-pick may have caused a merge conflict. In that case,
    only the non-conflicting files will be committed. This class
    contains the merge conflict text if there was a merge conflict.
    """

    commit_hash: str
    merge_conflict_text: Optional[str]
    # conflicting file paths in all cherry-picked commits, up to and including this one.
    conflicting_file_paths_total: Tuple[str]
    # Conflicting commit indices, up to and including this one. 0 is the first commit that was cherry-picked.
    conflicting_commit_indices: Tuple[str]


class CherryPickCache:
    def __init__(self, onto: str):
        self._onto = onto

        # Each entry of this dictionary corresponds to the cached result of cherry-picking
        # a single commit. The keys are obtained by CherryPickCacheKey.nonrandom_hash.
        self._cache: Dict[bytes, CherryPickCacheValue] = {}

    def add(
        self,
        base_commit: str,
        cherry_picked_item: RebaseItem,
        result_commit: str,
        merge_conflict_text: str,
        conflicting_file_paths_total: Tuple[str],
        conflicting_commit_indices: Tuple[str],
    ):
        """Call this time each time you do a cherry-pick in the temporary repo, and want to cache it"""
        key = CherryPickCacheKey(base_commit, cherry_picked_item).nonrandom_hash()
        self._cache[key] = CherryPickCacheValue(
            result_commit,
            merge_conflict_text,
            conflicting_file_paths_total,
            conflicting_commit_indices,
        )

    def check_cache(self, rebase_items: List[RebaseItem]) -> List[CherryPickCacheValue]:
        """If you're about the cherry-pick all these commits, use this function check the cache first

        It returns one CherryPickCacheValue for each RebaseItem, plus another one at the start for the base
        commit. It may return fewer items if they aren't all in the cache.
        """
        cache_values = [CherryPickCacheValue(self._onto, None, tuple(), tuple())]
        for item_index, rebase_item in enumerate(rebase_items):
            if rebase_item.action == "drop":
                continue

            key = CherryPickCacheKey(
                cache_values[-1].commit_hash, rebase_item
            ).nonrandom_hash()
            print(f"{len(self._cache)=}")
            if key in self._cache:
                cache_values.append(self._cache[key])
            else:
                return cache_values

        return cache_values


class MergeConflictDetectorSingleton:
    instance = None
    original_repo = Repo(".")
    temp_dir: Optional[str] = None
    temp_repo: Optional[Repo] = None
    _cache: Optional[CherryPickCache] = None
    _lock = threading.Lock()

    # This is updated every time we check for merge conflicts.
    # The key is the ordered tuple of commit hashes to be applied.
    # The value is a tuple with one element for each commit. If a
    # commit causes a merge conflict, the corresponding element will
    # be some human-readable text about the merge conflict. This text
    # is obtained using self.get_merge_conflict_text().
    merge_conflict_cache: Dict[Tuple[str, ...], Tuple[Optional[str], ...]] = {}

    def __new__(cls):
        if cls.instance is None:
            cls.instance = super().__new__(cls)

            repo = Repo(".")
            onto = currently_rebasing_on(repo)
            cls._cache = CherryPickCache(onto.hexsha)

        return cls.instance

    def setup(self):
        TEMP_DIR_PARENT = "/tmp/splitsquash"
        os.makedirs(TEMP_DIR_PARENT, exist_ok=True)
        self.temp_dir = tempfile.mkdtemp(dir=TEMP_DIR_PARENT)

        self.temp_repo = self.original_repo.clone(self.temp_dir)

    def cleanup(self):
        shutil.rmtree(self.temp_dir)
        self.temp_dir = None
        self.temp_repo = None

    def check_for_merge_conflicts(
        self,
        rebase_items: Tuple[RebaseItem, ...],
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

        self._lock.acquire(blocking=True)

        # 1. Create a temporary clone of the repo.
        # 2. Apply each commit in turn in the temporary repo.
        # 3. Terminate if there is a merge conflict.
        # 4. Clean up the temporary repo.

        # Start from a cached commit, or the original base.
        cache_values = self._cache.check_cache(rebase_items)
        base = cache_values[-1].commit_hash

        # File paths that have conflicted so far. Make sure these aren't committed
        # again after a conflict is detected, since we are only looking for the
        # first conflict for each file.
        conflicting_files = set(cache_values[-1].conflicting_file_paths_total)

        conflicting_commit_indices = list(cache_values[-1].conflicting_commit_indices)

        remaining_commits_start = len(cache_values) - 1

        self.temp_repo.head.reset(working_tree=True, index=True)
        self.temp_repo.git.checkout(base)

        for commit_index, rebase_item in enumerate(
            rebase_items[remaining_commits_start:], remaining_commits_start
        ):
            if rebase_item.action == "drop":
                continue

            print(
                "Applying commit", rebase_item.commit.hexsha, rebase_item.commit.message
            )

            # Cherry-pick without commiting, remove the excluded files, then commit.

            merge_conflict = False
            try:
                self.temp_repo.git.cherry_pick(rebase_item.commit, n=True)
            except GitCommandError:
                # Cherry-pick caused a merge conflict.
                # This is only a genuine merge conflict if the conflict is on an included file. Check
                # if it is on an included file.
                for change in rebase_item.file_changes.values():
                    if (
                        change.included
                        and change.path in self.temp_repo.index.unmerged_blobs()
                    ):
                        # Merge conflict on included file
                        conflicting_files.add(change.path)
                        conflicting_commit_indices.append(commit_index)
                        merge_conflict = True

            merge_conflict_text = None
            if merge_conflict:
                merge_conflict_text = self._get_merge_conflict_text()

            # remove excluded files and conflicting files from the index before committing
            for change in rebase_item.file_changes.values():
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
                    self.temp_repo.git.restore(
                        "--staged", "--worktree", "--", change.path
                    )
                    continue

            result_commit = self.temp_repo.index.commit(
                rebase_item.commit.message,
                author=rebase_item.commit.author,
                committer=rebase_item.commit.committer,
                author_date=datetime.fromtimestamp(
                    rebase_item.commit.authored_date
                ).isoformat(),
                commit_date=datetime.fromtimestamp(
                    rebase_item.commit.committed_date
                ).isoformat(),
                trailers=rebase_item.commit.trailers_list,
                skip_hooks=True,
            )

            self._cache.add(
                result_commit.parents[0].hexsha,
                rebase_item,
                result_commit.hexsha,
                merge_conflict_text,
                tuple(conflicting_files),
                tuple(conflicting_commit_indices),
            )

        self._lock.release()

        return conflicting_commit_indices

    def _get_merge_conflict_text(self, num_context_lines: int = 3):
        """Get human-readable text about the current merge conflict in the temporary repo"""

        merge_conflict_regex = re.compile(
            r"<<<<<<< HEAD\n(.*)\n=======\n(.*)\n>>>>>>> [0-9a-f]{7} \(.*\)",
            flags=re.DOTALL,
        )
        merge_conflict_text = ""

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

    def get_merge_conflict_text(
        self,
        rebase_items: Tuple[RebaseItem, ...],
    ) -> str:
        """Get the text of a merge conflict

        The last commit in the list must cause the merge conflict.
        """
        text = self._cache.get_cached_merge_conflict_text(rebase_items)
        assert text is not None
        return text
