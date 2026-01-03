from dataclasses import dataclass
from typing import Literal

from git import Commit

RebaseAction = Literal["pick", "drop", "edit", "reword", "squash", "fixup"]


@dataclass
class RebaseItem:
    commit: Commit
    action: RebaseAction = "pick"
