from dataclasses import dataclass
from os import PathLike
from typing import Literal

from git import Commit

REBASE_ACTIONS = ["pick", "drop", "edit", "reword", "squash", "fixup"]
RebaseAction = Literal["pick", "drop", "edit", "reword", "squash", "fixup"]


@dataclass
class FileChange:
    """A file that has been modified in a commit"""

    path: str | PathLike[str]
    # If the user wants to drop this file from the commit, they can set this to False.
    included: bool


class RebaseItem:
    def __init__(self, action: RebaseAction, commit: Commit):
        self.action = action
        self.commit = commit
        self.file_changes = {
            file: FileChange(file, True) for file in self.commit.stats.files.keys()
        }
