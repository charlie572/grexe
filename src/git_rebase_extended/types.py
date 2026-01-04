from dataclasses import dataclass, field
from os import PathLike
from typing import Literal, List

from git import Commit

RebaseAction = Literal["pick", "drop", "edit", "reword", "squash", "fixup"]


@dataclass
class FileChange:
    path: str | PathLike[str]
    modified: bool


class RebaseItem:
    def __init__(self, action: RebaseAction, commit: Commit):
        self.action = action
        self.commit = commit
        self.file_changes = {
            file: FileChange(file, True) for file in self.commit.stats.files.keys()
        }
