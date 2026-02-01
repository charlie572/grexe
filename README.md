# Grexe (Git Rebase Extended Editor)

An editor for performing interactive rebases with extra features.

Features:

- Select and move commits.
- Change rebase actions (pick, fixup, etc.).
- View the files that each commit changes.

# Controls

## Basic controls

- Move the cursor up and down with j and k.
- Select commits with v, or with the mouse.
- Move selected commits with m.
- Set actions for selected commits with f (fixup), s (squash), p (pick), e (edit), d (drop) and r (reword).
- Duplicate a commit with c.
- Remove some files from a commit by using h and l to move the cursor left and right, and t to toggle the selected file
  for a particular commit. You can also use the mouse.
- Press enter to perform the rebase.
- Press ctrl+q to cancel the rebase.

## Distribute Changes

You may want to split some commits up into several changes, and squash them into previous commits. You can do this by
copying the commits multiple times, squashing them into the previous commits, and toggling the files that you want
included in each commit. But Grexe provides a way to automate this.

1. Select the commits you want to split and squash.
2. Press q.
3. Select the commits you want to squash them into.
4. Press q again.

Grexe will split and squash the first set of commits into the second. It will squash together commits that modify the
same files. This doesn't work if multiple commits in the second set modify the same file, as Grexe doesn't know which
commit it should squash into.

## File Hierarchy

The right side of the screen shows the file hierarchy. You can expand/collapse nodes by right-clicking. You can
left-click to select/deselect a file. Only the selected files will be shown in the screen on the right. This can be
useful if you have a lot of files.

# Setup

1. `pip install .` or `pip install -e .`
2. `pre-commit install`

# Usage

Set the `GIT_SEQUENCE_EDITOR` environment variable or the `sequence.editor` setting in git to
`grexe-editor`. You can now run git rebases with grexe.

# Dependencies

- Python 3.13.1
- git