import pickle
from copy import deepcopy
from typing import List, Tuple

from git_rebase_extended.types import RebaseItem


def get_modified_file_paths(rebase_item: RebaseItem):
    return [
        path for path, change in rebase_item.file_changes.items() if change.modified
    ]


def distribute_changes(
    source_indices: List[int],
    target_indices: List[int],
    rebase_items: Tuple[RebaseItem, ...],
) -> Tuple[Tuple[RebaseItem, ...] | None, str | None]:
    """Split the changes from some source commits, and squash them into some target commits"""

    # TODO: handle case where some of the target commits are squashed into each other.

    with open("distribute_changes", "wb") as f:
        pickle.dump((source_indices, target_indices, rebase_items), f)

    # check that source and target are disjoint
    intersection = set(source_indices).intersection(target_indices)
    if len(intersection) != 0:
        intersect_shas = [rebase_items[i].commit.hexsha[:7] for i in intersection]
        return None, f"{', '.join(intersect_shas)} are in both source and target set."

    # Check for any file changes with ambiguous target commits.
    all_source_files = set(
        sum(
            [get_modified_file_paths(rebase_items[i]) for i in source_indices], start=[]
        )
    )
    target_files_seen = set()
    ambiguous_files = set()
    for target_index in target_indices:
        target_files = get_modified_file_paths(rebase_items[target_index])
        common_files = all_source_files.intersection(target_files)
        ambiguous_files.update(target_files_seen.intersection(common_files))
        target_files_seen.update(common_files)
    if len(ambiguous_files) > 0:
        return (
            None,
            "Each file change in the source should map to a single commit in the target. "
            "But the following files are present in multiple target commits, so their "
            f"destination commit is ambiguous: {', '.join(ambiguous_files)}.",
        )

    result: List[RebaseItem] = []
    for i, item in enumerate(rebase_items):
        if i not in target_indices:
            new_item = deepcopy(item)
            if i in source_indices:
                new_item.action = "drop"
            result.append(new_item)
            continue

        # add target commit
        target_item = rebase_items[i]
        result.append(target_item)

        target_file_paths = set(get_modified_file_paths(target_item))

        # squash source file changes into this target commit
        for source_index in source_indices:
            # get file changes to squash
            source_item = rebase_items[source_index]
            source_file_paths = set(get_modified_file_paths(source_item))
            paths_to_squash = target_file_paths.intersection(source_file_paths)
            if len(paths_to_squash) == 0:
                continue

            # add fixup to squash changes into target commit
            fixup: RebaseItem = deepcopy(source_item)
            fixup.action = "fixup"
            for file_path, file_change in fixup.file_changes.items():
                file_change.modified = file_path in paths_to_squash
            result.append(fixup)

    return result, None
