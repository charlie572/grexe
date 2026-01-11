# Git Extended Rebase

An editor for performing interactive rebases with extra features.

Features:
- Split a commit into several commits. You can select certain files to go into each new commit.
- "Distribute" a group of commit into new commits. This removes the original commits, creates some new commits, and 
  selects certain files to go into the new commits.
- "Distribute" a group of commits into previous commits. Like the feature above, but the changes are squashed into 
  previous commits.

# Setup

1. `pip install .` or `pip install -e .`
2. `pre-commit install`

# Usage

Set the `GIT_EDITOR` environment variable to `git-rebase-extended-editor`. You can now run git rebases with the extended
editor.

# Dependencies

- Python 3.13.1
- git