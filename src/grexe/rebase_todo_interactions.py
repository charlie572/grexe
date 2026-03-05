"""These classes provide stateful user interactions to modify the rebase todo."""

from copy import deepcopy
from typing import List, Optional

from grexe.rebase_todo_state import RebaseTodoStateAndCursor


class RebaseItemMover:
    """Allows the user to move one or more rebase items up or down

    This is a stateful interaction. The user can select some items, press
    a button to begin moving them, move them up or down, then press a
    button to confirm the change.
    """

    def __init__(self, rebase_todo_state: RebaseTodoStateAndCursor):
        self._todo_state = rebase_todo_state

        self._moving = False
        self._first_moving_index: Optional[int] = None
        self._last_moving_index: Optional[int] = None

    def get_moving_indices(self) -> List[int]:
        if not self._moving:
            raise RuntimeError

        return list(range(self._first_moving_index, self._last_moving_index + 1))

    def start_moving(self, indices_to_move: List[int]):
        """Start moving the items at the selected indices

        The selection will be cleared.
        """
        rebase_items = list(deepcopy(self._todo_state.get_current_items()))

        # remove selected items
        items_to_move = [rebase_items.pop(i) for i in reversed(indices_to_move)]

        # insert widgets back again as one block, with the bottom commit at its original index
        dest_index = indices_to_move[-1] - len(indices_to_move) + 1
        for item in items_to_move:
            rebase_items.insert(dest_index, item)

        self._todo_state.modify_items(tuple(rebase_items), clear_selection=True)

        self._moving = True
        self._first_moving_index = dest_index
        self._last_moving_index = dest_index + len(items_to_move) - 1

    def move_up(self):
        """Move block of rebase items up

        Must have called start_moving first.
        """
        if not self._moving:
            raise RuntimeError

        rebase_items = list(deepcopy(self._todo_state.get_current_items()))

        if self._first_moving_index == 0:
            return

        item_before_moving_block = rebase_items.pop(self._first_moving_index - 1)
        rebase_items.insert(self._last_moving_index, item_before_moving_block)
        self._todo_state.modify_items(tuple(rebase_items))

        self._first_moving_index -= 1
        self._last_moving_index -= 1

    def move_down(self):
        """Move block of rebase items down

        Must have called start_moving first.
        """
        if not self._moving:
            raise RuntimeError

        rebase_items = list(deepcopy(self._todo_state.get_current_items()))

        if self._last_moving_index == len(rebase_items) - 1:
            return

        item_after_moving_block = rebase_items.pop(self._last_moving_index + 1)
        rebase_items.insert(self._first_moving_index, item_after_moving_block)
        self._todo_state.modify_items(tuple(rebase_items))

        self._first_moving_index += 1
        self._last_moving_index += 1

    def stop_moving(self):
        if not self._moving:
            raise RuntimeError

        self._todo_state.set_cursor(self._first_moving_index)

        self._moving = False
        self._first_moving_index = None
        self._last_moving_index = None


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
