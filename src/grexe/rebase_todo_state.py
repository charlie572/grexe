from copy import deepcopy
from typing import List, Tuple, Callable, Literal, Optional

from grexe.types import RebaseItem


class RebaseTodoState:
    """Stores the state of the rebase todo, and tracks an undo history"""

    def __init__(self, rebase_items: List[RebaseItem]):
        self._history: List[Tuple[RebaseItem, ...]] = [tuple(rebase_items)]
        self._history_index = 0

    def get_current_num_items(self):
        return len(self._history[self._history_index])

    def get_current_items(self):
        return self._history[self._history_index]

    def get_original_items(self):
        return self._history[0]

    def modify_items(self, rebase_items: Tuple[RebaseItem, ...]):
        """Modify the rebase_items, while tracking the changes so this action can be undone"""
        self._history = self._history[: self._history_index + 1] + [rebase_items]
        self._history_index += 1

    def undo(self):
        self._history_index = max(0, self._history_index - 1)

    def redo(self):
        self._history_index = min(len(self._history) - 1, self._history_index + 1)


class RebaseTodoStateAndCursor:
    """Allows you to store a list of RebaseItems, select some of them, and have a cursor
    that hovers over a single commit. This only tracks and updates the state.
    """

    def __init__(
        self,
        rebase_todo_state: RebaseTodoState,
        on_change_active_item: Callable[[int, RebaseItem], None],
    ):
        self._state = rebase_todo_state
        self._selected = [False] * self._state.get_current_num_items()
        self._cursor = 0
        self._on_change_active_item = on_change_active_item

    @property
    def cursor(self):
        return self._cursor

    def get_active_item(self):
        """Get the rebase item currently under the cursor"""
        return deepcopy(self._state.get_current_items()[self._cursor])

    def get_indices_to_modify(self) -> List[int]:
        """Get the indices of the rebase items to modify

        This can be used when moving multiple items, or changing the rebase action of
        multiple items.

        If some items are selected, this function will return their indices. If no items
        are selected, the active item will be returned (the one currently under the
        cursor).
        """
        selected_indices = self.get_selected_indices()
        if len(selected_indices) == 0:
            return [self._cursor]
        else:
            return selected_indices

    def set_cursor(self, new_cursor):
        self._cursor = new_cursor
        self._on_change_active_item(self._cursor, self.get_active_item())

    def _clamp_cursor(self):
        num_items = self.get_current_num_items()
        if self._cursor < 0:
            self.set_cursor(0)
        elif self._cursor >= num_items:
            self.set_cursor(num_items - 1)

    def select_all(self):
        self._selected = [True] * self._state.get_current_num_items()

    def select_none(self):
        self._selected = [False] * self._state.get_current_num_items()

    def toggle_select_all_or_none(self):
        selected = not self._selected[self._cursor]
        self._selected[:] = [selected] * self.get_current_num_items()

    def select_single(self, index):
        self._selected = [False] * self._state.get_current_num_items()
        self._selected[index] = True

    def set_selected(self, selected: List[bool]):
        self._selected[:] = selected

    def get_selected(self) -> List[bool]:
        return self._selected.copy()

    def get_selected_indices(self):
        return [i for i in range(len(self._selected)) if self._selected[i]]

    def is_selected(self, index: int):
        return self._selected[index]

    def toggle_active_item(self):
        self._selected[self._cursor] = not self._selected[self._cursor]

    def get_current_num_items(self):
        return self._state.get_current_num_items()

    def get_current_items(self):
        return self._state.get_current_items()

    def get_original_items(self):
        return self._state.get_original_items()

    def modify_items(
        self, rebase_items: Tuple[RebaseItem, ...], clear_selection: bool = False
    ):
        """Modify the current rebase items, while tracking the history so this change can be undone

        If the length of rebase_items is different to the current number of rebase items, then the length of
        self._selected will be wrong after the change. There is no way to know how it's supposed to be updated, because
        items may have been inserted or deleted, and we don't know where. However, if the clear_selection flag is set to
        True, then we can just set every element to False.

        Therefore, if the number of rebase items might change, clear_selection must be set to True. If the number
        changes, and clear_selection == False, then an error will be raised.

        :param rebase_items:
        :param clear_selection: If True, the current selection will be cleared. Set to true if the number of rebase
                                items might change.
        """
        if (
            not clear_selection
            and len(rebase_items) != self._state.get_current_num_items()
        ):
            # self._selected_array is now the wrong length, and we don't know how to update it. We may need to insert
            # False somewhere, or delete an item.
            raise RuntimeError(
                "New rebase_items must have same length as original. You may need to use a different method e.g."
                "insert_item."
            )

        if clear_selection:
            self._selected = [False] * len(rebase_items)

        self._state.modify_items(rebase_items)
        self._clamp_cursor()
        self._on_change_active_item(self._cursor, self.get_active_item())

    def insert_item(self, rebase_item: RebaseItem, index: Optional[int] = None):
        if index is None:
            index = self._cursor + 1

        rebase_items = list(deepcopy(self._state.get_current_items()))

        rebase_items.insert(index, rebase_item)
        self._selected.insert(index, False)

        self._state.modify_items(tuple(rebase_items))

    def undo(self):
        self._state.undo()
        self.select_none()
        self._clamp_cursor()
        self._on_change_active_item(self._cursor, self.get_active_item())

    def redo(self):
        self._state.redo()
        self.select_none()
        self._clamp_cursor()
        self._on_change_active_item(self._cursor, self.get_active_item())

    def move_cursor(self, direction: Literal["inc", "dec"]):
        """Increment or decrement cursor, and clamp to valid bounds"""
        if direction == "inc":
            self.set_cursor(min(self.get_current_num_items() - 1, self._cursor + 1))
        elif direction == "dec":
            self.set_cursor(max(0, self._cursor - 1))
