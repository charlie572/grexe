import os
from copy import deepcopy
from typing import List, Tuple, Literal, Optional

from textual.containers import Horizontal, Grid, Vertical
from textual.events import Click, Key
from textual.widget import Widget
from textual.widgets import Label

from grexe.distribute import distribute_changes
from grexe.rebase_todo_interactions import RebaseItemMover
from grexe.types import RebaseItem, RebaseAction
from grexe.rebase_todo_state import RebaseTodoState, RebaseTodoStateAndCursor
from grexe.widgets import FilenameLabel, FileChangeIndicator


class RebaseTodoWidget(Widget):
    CSS_PATH = "main.tcss"

    def __init__(
        self,
        rebase_todo_state: RebaseTodoState,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self.can_focus = True

        self._todo_state = RebaseTodoStateAndCursor(
            rebase_todo_state,
            self._on_changed_active_item,
        )

        # Classes providing stateful user interactions
        self._item_mover = RebaseItemMover(self._todo_state)

        self._active_file_index = -1
        self._distribute_sources: Optional[List[int]] = None

        self._state: Literal["idle", "moving", "selecting_distribute_targets"] = "idle"

        rebase_items = rebase_todo_state.get_original_items()
        self._visible_files: List[str | os.PathLike[str]] = sum(
            [list(item.commit.stats.files.keys()) for item in rebase_items], start=[]
        )
        self._visible_files = list(set(self._visible_files))

        self._last_hovered_file = None

    def _on_changed_active_item(self, cursor: int, active_item: RebaseItem):
        pass

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
            return

        if event.key == "j":
            self.action_move_down()
        if event.key == "k":
            self.action_move_up()
        if event.key == "h":
            self.action_move_left()
        if event.key == "l":
            self.action_move_right()
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
        if event.key == "t":
            self.action_toggle_file()
        if event.key == "ctrl+a":
            self.action_select_all()
        if event.key == "ctrl+z":
            self._todo_state.undo()
            self.refresh(recompose=True)
        if event.key == "ctrl+y":
            self._todo_state.redo()
            self.refresh(recompose=True)
        if event.key == "q":
            self.action_distribute()

    def action_distribute(self):
        if self._state == "idle":
            self._distribute_sources = self._todo_state.get_selected_indices()
            if len(self._distribute_sources) == 0:
                return
            self._todo_state.select_none()
            self._state = "selecting_distribute_targets"
            self.refresh(recompose=True)
        elif self._state == "selecting_distribute_targets":
            distribute_targets = self._todo_state.get_selected_indices()
            if len(self._distribute_sources) > 0:
                distributed_items, error = distribute_changes(
                    self._distribute_sources,
                    distribute_targets,
                    self._todo_state.get_current_items(),
                )
                if error is not None:
                    self.notify(error, severity="error", timeout=10)
                else:
                    self._todo_state.modify_items(
                        distributed_items, clear_selection=True
                    )
            self._todo_state.select_none()
            self._distribute_sources = None
            self._state = "idle"
            self.refresh(recompose=True)

    def _get_items_to_modify(self, rebase_items=None):
        """Get the rebase items to modify

        This can be used when moving multiple items, or changing the rebase action of
        multiple items.

        If some items are selected, this function will return them. If no items are
        selected, the active item will be returned (the one currently under the
        cursor).
        """
        if rebase_items is None:
            rebase_items = self._todo_state.get_current_items()

        selected_items = self._get_selected(rebase_items)
        if len(selected_items) == 0:
            return [rebase_items[self._todo_state.cursor]]
        else:
            return selected_items

    def _get_indices_to_modify(self):
        """Get the indices of the rebase items to modify

        This can be used when moving multiple items, or changing the rebase action of
        multiple items.

        If some items are selected, this function will return them. If no items are
        selected, the active item will be returned (the one currently under the
        cursor).
        """
        selected_indices = self._get_selected(indices=True)
        if len(selected_indices) == 0:
            return [self._todo_state.cursor]
        else:
            return selected_indices

    def _get_selected(self, rebase_items=None, indices=False):
        if rebase_items is None:
            rebase_items = self._todo_state.get_current_items()

        result = []
        for i, item in enumerate(rebase_items):
            if self._todo_state.is_selected(i):
                if indices:
                    result.append(i)
                else:
                    result.append(item)

        return result

    def get_active_item(self):
        return self._todo_state.get_active_item()

    def on_mouse_move(self, event):
        # Show a message with the full path of the file the user is hovering over. Use
        # self._last_hovered file to make sure a new message isn't shown for every frame
        # that the cursor moves over a file.
        if isinstance(self.app.mouse_over, FilenameLabel):
            if self.app.mouse_over.path != self._last_hovered_file:
                self.notify(self.app.mouse_over.path, timeout=3)
            self._last_hovered_file = self.app.mouse_over.path
        else:
            self._last_hovered_file = None

    def on_click(self, event: Click):
        # check if a file was clicked
        file_grid = self.query_one("#file_grid")
        for child_index, child in enumerate(file_grid.children):
            if child is not event.widget:
                continue

            # File change indicator was clicked. Select it and toggle it.

            commit_index = child_index // len(self._visible_files) - 1
            file_index = child_index % len(self._visible_files)

            # get file change object
            rebase_items = self._todo_state.get_current_items()
            file = self._visible_files[file_index]
            file_change = rebase_items[commit_index].file_changes.get(file)
            if file_change is None:
                # This file change isn't included in this commit. It is a blank space in the UI. Do nothing.
                return

            # select file
            self._active_file_index = file_index

            # toggle file
            file_change.modified = not file_change.modified
            self._todo_state.modify_items(rebase_items)

            # select commit
            self._todo_state.set_cursor(commit_index)
            self._todo_state.select_single(commit_index)

            self.refresh(recompose=True)
            return

        # check if a commit was clicked
        commit_grid = self.query_one("#commit_grid")
        for child_index, child in enumerate(commit_grid.children):
            if child is not event.widget:
                continue

            # Commit was clicked. Select it.
            commit_index = child_index // 3 - 1
            self._todo_state.set_cursor(commit_index)
            self._todo_state.select_single(commit_index)

            self.refresh(recompose=True)
            return

    def action_copy(self):
        self._todo_state.insert_item(
            self._todo_state.get_active_item(), self._todo_state.cursor
        )
        self.refresh(recompose=True)

    def action_toggle_file(self):
        rebase_items = list(deepcopy(self._todo_state.get_current_items()))
        active_item: RebaseItem = rebase_items[self._todo_state.cursor]

        file = self._visible_files[self._active_file_index]
        file_change = active_item.file_changes[file]
        file_change.modified = not file_change.modified

        self._todo_state.modify_items(tuple(rebase_items))
        self.refresh(recompose=True)

    def action_move_left(self):
        active_item = self._todo_state.get_current_items()[self._todo_state.cursor]
        if not isinstance(active_item, RebaseItem):
            return

        # move left to next file indicator, or select no files (self._active_file_index == -1)
        while self._active_file_index > -1:
            self._active_file_index -= 1
            file = self._visible_files[self._active_file_index]
            if file in active_item.file_changes:
                break

        self.refresh(recompose=True)

    def action_move_right(self):
        active_item = self._todo_state.get_current_items()[self._todo_state.cursor]
        if not isinstance(active_item, RebaseItem):
            return

        previous_active_file_index = self._active_file_index

        # move right to next file indicator
        while self._active_file_index < len(self._visible_files) - 1:
            self._active_file_index += 1
            file = self._visible_files[self._active_file_index]
            if file in active_item.file_changes:
                self.refresh(recompose=True)
                return

        # No more files. Reset index to what it was before this function was run.
        self._active_file_index = previous_active_file_index

    def action_move_commits(self):
        if self._state == "idle":
            indices_to_move = self._get_indices_to_modify()
            self._item_mover.start_moving(indices_to_move)
            self._state = "moving"
            self.refresh(recompose=True)
        elif self._state == "moving":
            self._item_mover.stop_moving()
            self._state = "idle"
            self.refresh(recompose=True)

    def action_move_up(self):
        if self._state == "moving":
            self._item_mover.move_up()
            self.refresh(recompose=True)
        else:
            self._todo_state.move_cursor("dec")
            self.refresh(recompose=True)

    def action_move_down(self):
        if self._state == "moving":
            self._item_mover.move_down()
            self.refresh(recompose=True)
        else:
            self._todo_state.move_cursor("inc")
            self.refresh(recompose=True)

    def action_select(self):
        self._todo_state.toggle_active_item()
        self.refresh(recompose=True)

    def action_select_all(self):
        self._todo_state.toggle_select_all_or_none()
        self.refresh(recompose=True)

    def _set_rebase_action(self, action: RebaseAction):
        rebase_items = deepcopy(self._todo_state.get_current_items())

        for item in self._get_items_to_modify(rebase_items):
            item.action = action

        self._todo_state.modify_items(rebase_items)
        self.refresh(recompose=True)

    def set_visible_files(self, visible_files):
        self._visible_files = visible_files
        self.refresh(recompose=True)

    def compose(self):
        rebase_items = self._todo_state.get_current_items()

        # The left half of the widget shows the rebase actions, hashes, and commit messages. The
        # right half shows the file changes. The right half is scrollable horizontally. Both halves
        # are grid layouts.

        if self._state == "moving":
            highlighted_indices = self._item_mover.get_moving_indices()
        else:
            highlighted_indices = self._todo_state.get_selected_indices()

        with Vertical():
            status_text = (
                "Select commits to distribute into..."
                if self._state == "selecting_distribute_targets"
                else ""
            )
            yield Label(status_text)

            with Horizontal():
                yield CommitGrid(
                    rebase_items,
                    self._todo_state.cursor if self._state != "moving" else None,
                    highlighted_indices,
                    id="commit_grid",
                )

                yield FileGrid(
                    rebase_items,
                    self._todo_state.cursor if self._state != "moving" else None,
                    self._active_file_index,
                    highlighted_indices,
                    self._visible_files,
                    id="file_grid",
                )


class CommitGrid(Grid):
    def __init__(
        self,
        rebase_items: Tuple[RebaseItem, ...],
        active_index: Optional[int],
        highlighted_indices: List[int],
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self._rebase_items = rebase_items
        self._active_index = active_index
        self._highlighted_indices = highlighted_indices

        self.styles.grid_columns = "auto"
        self.styles.grid_gutter_vertical = 2
        self.styles.grid_rows = "1"
        self.styles.grid_size_rows = len(rebase_items) + 1
        self.styles.grid_size_columns = 3
        self.styles.height = len(rebase_items) + 1

    def compose(self):
        # header row
        yield Label("")
        yield Label("")
        yield Label("")

        # make boolean array from self._highlighted_indices
        highlighted = [False] * len(self._rebase_items)
        for i in self._highlighted_indices:
            highlighted[i] = True

        # commit rows
        for i, item in enumerate(self._rebase_items):
            classes = []
            if i == self._active_index:
                classes.append("active")
            if highlighted[i]:
                classes.append("selected")
            classes = " ".join(classes)

            yield Label(item.action, classes=f"rebase_action {classes}")

            yield Label(item.commit.hexsha[:7], classes=f"hexsha {classes}")

            first_message_line = item.commit.message.split("\n")[0]
            yield Label(first_message_line, classes=f"commit_message {classes}")


class FileGrid(Grid):
    def __init__(
        self,
        rebase_items: Tuple[RebaseItem, ...],
        active_index: Optional[int],
        active_file_index: int,
        highlighted_indices: List[int],
        visible_files: List[str | os.PathLike[str]],
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self._rebase_items = rebase_items
        self._active_index = active_index
        self._highlighted_indices = highlighted_indices
        self._visible_files = visible_files
        self._active_file_index = active_file_index

        self.styles.grid_columns = "auto"
        self.styles.grid_gutter_vertical = 1
        self.styles.grid_rows = "1"
        self.styles.grid_size_rows = len(rebase_items) + 1
        self.styles.grid_size_columns = len(visible_files)
        # An extra row is added at the bottom so the scroll bar doesn't cover the bottom row.
        self.styles.height = len(rebase_items) + 2
        self.styles.overflow_x = "auto"

    def compose(self):
        # header row
        for file in self._visible_files:
            yield FilenameLabel(file, classes="filename")

        # make boolean array from self._highlighted_indices
        highlighted = [False] * len(self._rebase_items)
        for i in self._highlighted_indices:
            highlighted[i] = True

        # commit rows
        for i, item in enumerate(self._rebase_items):
            classes = []
            if i == self._active_index:
                classes.append("active")
            if highlighted[i]:
                classes.append("selected")
            classes = " ".join(classes)

            for j, file in enumerate(self._visible_files):
                file_change = item.file_changes.get(file)
                if file_change:
                    selectable = True
                    changed = file_change.modified
                else:
                    selectable = False
                    changed = False

                active = (
                    i == self._active_index
                    and j == self._active_file_index
                    and isinstance(item, RebaseItem)
                )

                yield FileChangeIndicator(changed, selectable, active, classes=classes)
