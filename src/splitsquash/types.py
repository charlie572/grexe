from copy import deepcopy
from dataclasses import dataclass
from os import PathLike
from typing import Literal

from git import Commit

REBASE_ACTIONS = ["pick", "drop", "edit", "reword", "squash", "fixup"]
RebaseAction = Literal["pick", "drop", "edit", "reword", "squash", "fixup"]


@dataclass
class OptionalFile:
    """A file path and a boolean

    This can be used in the following cases:
    - Store a file that has been modified in a commit, which the user can optionally drop from the commit
      by setting the boolean to False.
    - Pass a list of files to a FileSelector, and have it highlight the ones with the boolean set to True.
    """

    path: str | PathLike[str]
    included: bool


class RebaseItem:
    def __init__(self, action: RebaseAction, commit: Commit):
        self.action = action
        self.commit = commit
        self.file_changes = {
            file: OptionalFile(file, True) for file in self.commit.stats.files.keys()
        }

    def copy(self):
        """Copy RebaseItem

        All the mutable fields are deep-copied, except the commit. Deep-copying the commit can
        lead to max recursion depth errors. I'm not sure why.
        """
        result = RebaseItem(self.action, self.commit)
        result.file_changes = deepcopy(self.file_changes)
        return result
