"""These classes provide stateful user interactions to modify the rebase todo."""


class RebaseItemMover:
    """Allows the user to move one or more rebase items up or down

    This is a stateful interaction. The user can select some items, press
    a button to begin moving them, move them up or down, then press a
    button to confirm the change.
    """

    pass


class RebaseItemDistributor:
    """Allows the user to "distribute" some rebase items into other rebase items

    The first set of rebase items are split and squashed into the second set.

    This is a stateful interaction. The user does the following:
    1. Select the commits you want to split and squash.
    2. Press a button.
    3. Select the commits you want to squash them into.
    4. Press a button.

    It will squash together commits that modify the same files. This doesn't work if multiple commits in the second set
    modify the same file, as it doesn't know which commit it should squash into.
    """

    pass
