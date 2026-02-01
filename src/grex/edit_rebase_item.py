import argparse

from git import Repo

from grex.types import REBASE_ACTIONS


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Run this script after applying a commit in a rebase. You can use\n"
            + "this to change the rebase action or remove some files."
        )
    )
    parser.add_argument(
        "-a",
        "--action",
        type=str,
        choices=REBASE_ACTIONS,
    )
    parser.add_argument("files_included", nargs="+", type=str)
    args = parser.parse_args()

    repo = Repo(".")

    # We need to edit the most recent rebase commit to only include the specified files, and use
    # the specified rebase action. To do this, we:
    # 1. Edit the commit to only include the specified files.
    # 2. Reset the commit.
    # 3. Edit the `git-rebase-todo` file to re-apply the commit with the specified action.

    # 1. Edit the commit.
    commit_message = repo.head.commit.message
    repo.head.reset("HEAD~1", index=True, working_tree=False)
    repo.index.add(args.files_included)
    repo.index.commit(commit_message)
    repo.head.reset("HEAD", index=True, working_tree=True)

    if args.action == "pick":
        # Steps 2 and 3 are unnecessary for picks, since the correct action has already been applied.
        return

    # 2. Reset the commit
    new_commit_hash = repo.head.commit.hexsha
    repo.head.reset("HEAD~1", index=True, working_tree=True)

    # 3. Edit the git-rebase-todo file
    todo_file = ".git/rebase-merge/git-rebase-todo"
    with open(todo_file, "r") as f:
        rebase_todo = f.readlines()

    commit_message_first_line = commit_message.split("\n")[0]
    rebase_todo = [
        f"{args.action} {new_commit_hash} {commit_message_first_line}\n"
    ] + rebase_todo

    with open(todo_file, "w") as f:
        f.writelines(rebase_todo)


if __name__ == "__main__":
    main()
