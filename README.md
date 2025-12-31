# Git Extended Rebase

A CLI for performing interactive rebases with extra features.

Features:
- Split a commit into several commits. You can select certain files to go into each new commit.
- "Distribute" a group of commit into new commits. This removes the original commits, creates some new commits, and 
  selects certain files to go into the new commits.
- "Distribute" a group of commits into previous commits. Like the feature above, but the changes are squashed into 
  previous commits.

# Setup

`pip install .` or `pip install -e .`.

# Usage

Run `git-rebase-extended` in the command line. This will open a CLI to perform an interactive rebase. Command line
arguments will be passed to `git rebase`.

# Dependencies

- Python 3.13.1
- git