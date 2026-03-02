from copy import deepcopy
from typing import List, Tuple, Callable, Literal

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

    def set_cursor(self, new_cursor):
        self._cursor = new_cursor
        rebase_items = self._state.get_current_items()
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

    def modify_items(self, rebase_items: Tuple[RebaseItem, ...]):
        self._state.modify_items(rebase_items)
        self.select_none()
        self._clamp_cursor()
        self._on_change_active_item(self._cursor, self.get_active_item())

    def insert_item(self, rebase_item: RebaseItem, index: int):
        rebase_items = list(deepcopy(self._state.get_current_items()))

        rebase_items.insert(self._cursor + 1, rebase_item)
        self._selected.insert(self._cursor + 1, False)

        self._state.modify_items(tuple(rebase_items))

        self._on_change_active_item(self._cursor, self.get_active_item())

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
