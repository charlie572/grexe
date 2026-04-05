from copy import deepcopy
from typing import Literal, Optional

from textual.containers import Horizontal, Vertical
from textual.events import Key
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Label

from grexe.rebase_todo.rebase_todo_interactions import (
    RebaseItemMover,
    RebaseItemDistributor,
)
from grexe.rebase_todo.rebase_todo_state import RebaseTodoStateAndCursor
from grexe.types import RebaseItem, RebaseAction
from grexe.utility_functions import get_files_modified
from grexe.widgets.commit_grid import CommitGrid
from grexe.widgets.file_grid import FileGrid


class RebaseTodoWidget(Widget):
    CSS_PATH = "../styles/main.tcss"

    class Updated(Message):
        pass

    def __init__(
        self,
        rebase_todo_state: RebaseTodoStateAndCursor,
        show_files: bool,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self.can_focus = True

        self._show_files = show_files

        # state
        self._todo_state = rebase_todo_state
        self._state: Literal["idle", "moving", "distributing"] = "idle"

        # classes providing stateful user interactions
        self._item_mover = RebaseItemMover(self._todo_state)
        self._item_distributor = RebaseItemDistributor(self._todo_state)

        # children
        self._status_label: Optional[Label] = None
        self._commit_grid: Optional[CommitGrid] = None
        self._file_grid: Optional[FileGrid] = None

    @property
    def file_grid(self):
        return self._file_grid

    def on_key(self, event: Key):
        if self._state != "idle":
            # These are the only actions that can be performed in a non-idle state.
            if event.key == "j":
                self.action_move_down()
            if event.key == "k":
                self.action_move_up()
            if event.key == "m":
                self.action_move_commits()
            if event.key == "q":
                self.action_distribute()
            if event.key == "v":
                self.action_select()
            return

        if event.key == "j":
            self.action_move_down()
        if event.key == "k":
            self.action_move_up()
        if event.key == "h" and self._file_grid is not None:
            self._file_grid.action_move_left()
        if event.key == "l" and self._file_grid is not None:
            self._file_grid.action_move_right()
        if event.key == "v":
            self.action_select()
        if event.key == "p":
            self._set_rebase_action("pick")
        if event.key == "f":
            self._set_rebase_action("fixup")
        if event.key == "s":
            self._set_rebase_action("squash")
        if event.key == "e":
            self._set_rebase_action("edit")
        if event.key == "r":
            self._set_rebase_action("reword")
        if event.key == "d":
            self._set_rebase_action("drop")
        if event.key == "m":
            self.action_move_commits()
        if event.key == "c":
            self.action_copy()
        if event.key == "t" and self._file_grid is not None:
            self._file_grid.action_toggle_file()
        if event.key == "ctrl+a":
            self.action_select_all()
        if event.key == "ctrl+z":
            self._todo_state.undo()
            self.update_state()
        if event.key == "ctrl+y":
            self._todo_state.redo()
            self.update_state()
        if event.key == "q":
            self.action_distribute()

    def on_commit_grid_clicked_commit(self, event):
        self._todo_state.set_cursor(event.commit_index)
        self._todo_state.select_single(event.commit_index)
        self.update_state()

    def on_file_grid_set_file_status(self, event):
        # find rebase item to modify
        rebase_items = list(deepcopy(self._todo_state.get_current_items()))
        rebase_item: RebaseItem = rebase_items[event.commit_index]

        # set file change status
        file_change = rebase_item.file_changes[event.file_path]
        file_change.included = event.included

        # select modified commit
        self._todo_state.set_cursor(event.commit_index)

        # modify item and update
        self._todo_state.modify_items(tuple(rebase_items))
        self.update_state()

    def action_distribute(self):
        if self._state == "idle":
            picked_valid_sources = self._item_distributor.pick_sources()
            if picked_valid_sources:
                self._state = "distributing"
                self.update_state()
        elif self._state == "distributing":
            picked_valid_targets = self._item_distributor.pick_targets()
            if picked_valid_targets:
                error = self._item_distributor.distribute()
                if error:
                    self.notify(error, severity="error", timeout=10)
            else:
                self._item_distributor.reset()

            self._state = "idle"
            self.update_state()

    def action_copy(self):
        self._todo_state.insert_item(
            self._todo_state.get_active_item(), self._todo_state.cursor
        )
        self.update_state()

    def action_move_commits(self):
        if self._state == "idle":
            self._item_mover.start_moving()
            self._state = "moving"
            self.update_state()
        elif self._state == "moving":
            self._item_mover.stop_moving()
            self._state = "idle"
            self.update_state()

    def action_move_up(self):
        if self._state == "moving":
            self._item_mover.move_up()
            self.update_state()
        else:
            self._todo_state.move_cursor("dec")
            self.update_state()

    def action_move_down(self):
        if self._state == "moving":
            self._item_mover.move_down()
            self.update_state()
        else:
            self._todo_state.move_cursor("inc")
            self.update_state()

    def action_select(self):
        self._todo_state.toggle_active_item()
        self.update_state()

    def action_select_all(self):
        self._todo_state.toggle_select_all_or_none()
        self.update_state()

    def _set_rebase_action(self, action: RebaseAction):
        rebase_items = deepcopy(self._todo_state.get_current_items())

        for i in self._todo_state.get_indices_to_modify():
            rebase_items[i].action = action

        self._todo_state.modify_items(rebase_items)
        self.update_state()

    def update_state(
        self,
        recompose: bool = True,
        notify_other_widets: bool = True,
    ):
        """Update the state of all the children, and refresh them

        Call this after updating any of the state.
        """

        rebase_items = self._todo_state.get_current_items()

        if self._state == "moving":
            highlighted_indices = self._item_mover.get_moving_indices()
        else:
            highlighted_indices = self._todo_state.get_selected_indices()

        status_text = (
            "Select commits to distribute into..."
            if self._state == "distributing"
            else ""
        )
        self._status_label.update(status_text)

        self._commit_grid.update_state(
            rebase_items,
            self._todo_state.cursor if self._state != "moving" else None,
            highlighted_indices,
        )

        if self._file_grid is not None:
            self._file_grid.update_state(
                rebase_items,
                self._todo_state.cursor if self._state != "moving" else None,
                highlighted_indices,
            )

        if recompose:
            self._commit_grid.refresh(recompose=True)
            if self._file_grid is not None:
                self._file_grid.refresh(recompose=True)

        if notify_other_widets:
            self.post_message(self.Updated())

    def compose(self):
        # The left half of the widget shows the rebase actions, hashes, and commit messages. The
        # right half shows the file changes. The right half is scrollable horizontally. Both halves
        # are grid layouts.

        # Instantiate the children as empty widgets, then populate them with state

        self._status_label = Label()
        self._commit_grid = CommitGrid()

        if self._show_files:
            files = get_files_modified(self._todo_state.get_original_items())
            self._file_grid = FileGrid(files)

        self.update_state()

        with Vertical():
            yield self._status_label

            with Horizontal():
                yield self._commit_grid
                if self._file_grid is not None:
                    yield self._file_grid
