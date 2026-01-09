import os
import subprocess
from typing import List, Optional

from git_rebase_extended.types import RebaseItem


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
