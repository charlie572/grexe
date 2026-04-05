import os
from copy import deepcopy
from typing import List, Tuple, Literal, Optional

from textual.containers import Horizontal, Grid, Vertical
from textual.events import Click, Key
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Label

from grexe.rebase_todo_interactions import RebaseItemMover, RebaseItemDistributor
from grexe.rebase_todo_state import RebaseTodoStateAndCursor
from grexe.types import RebaseItem, RebaseAction, OptionalFile
from grexe.widgets import FilenameLabel, FileChangeIndicator


def get_files_modified(
    rebase_items: Tuple[RebaseItem, ...], include_files_excluded_by_user: bool = False
):
    file_changes: List[OptionalFile] = sum(
        [list(item.file_changes.values()) for item in rebase_items], start=[]
    )
    if not include_files_excluded_by_user:
        file_changes = [change for change in file_changes if change.included]
    files = [change.path for change in file_changes]
    return list(set(files))


class RebaseTodoWidget(Widget):
    CSS_PATH = "main.tcss"

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


class CommitGrid(Grid):
    """Displays a list of rebase items, showing their hashes and messages

    The constructor has no parameters. You must instantiate it as an empty widget,
    then populate the state using the update_state() method.
    """

    class ClickedCommit(Message):
        def __init__(self, commit_index):
            self.commit_index = commit_index
            super().__init__()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._rebase_items: Tuple[RebaseItem, ...] = ()
        self._active_index: Optional[int] = None
        self._highlighted_indices: List[int] = []

        self.styles.grid_columns = "auto"
        self.styles.grid_gutter_vertical = 2
        self.styles.grid_rows = "1"
        self.styles.grid_size_rows = 1
        self.styles.grid_size_columns = 3
        self.styles.height = 1

    def update_state(
        self,
        rebase_items: Tuple[RebaseItem, ...],
        active_index: Optional[int],
        highlighted_indices: List[int],
        recompose: bool = False,
    ):
        """Set all of the state

        Call this method after instantiating the widget. Call it again to update all the state.
        """
        self._rebase_items = rebase_items
        self._active_index = active_index
        self._highlighted_indices = highlighted_indices

        self.styles.grid_size_rows = len(rebase_items) + 1
        self.styles.height = len(rebase_items) + 1

        if recompose:
            self.refresh(recompose=True)

    def on_click(self, event: Click):
        for child_index, child in enumerate(self.children):
            if child is not event.widget:
                continue

            commit_index = child_index // 3 - 1
            self.post_message(self.ClickedCommit(commit_index))

            return

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
    """Displays FileChangeIndicators for a list of commits

    There is one row for each commit, and each row contains one indicator for each
    file.

    Each indicator shows
    - a dot is shown if the file is included in the commit
    - a cross if it is included, but the user has clicked on it to remove it
    - nothing otherwise

    Only the list of files is initialised in the constructor, so the widget
    is empty when it is instantiated. You must populate the other state with the
    update_state() method.

    :param files: The list of file paths to use as the column headers. The columns
                  can be shown or hidden later using set_visible_files().
    """

    class SetFileStatus(Message):
        def __init__(self, commit_index, file_path, included):
            self.commit_index = commit_index
            self.file_path = file_path
            self.included = included
            super().__init__()

    def __init__(
        self,
        files: List[str | os.PathLike[str]],
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self._rebase_items: Tuple[RebaseItem, ...] = ()
        self._active_index: Optional[int] = None
        self._highlighted_indices: List[int] = []
        self._visible_files: List[str | os.PathLike[str]] = files
        self._active_file_index: int = -1

        self._last_hovered_file = None

        self.styles.grid_columns = "auto"
        self.styles.grid_gutter_vertical = 1
        self.styles.grid_rows = "1"
        self.styles.grid_size_rows = 1
        self.styles.grid_size_columns = len(self._visible_files)
        self.styles.height = 2
        self.styles.overflow_x = "auto"

    def update_state(
        self,
        rebase_items: Tuple[RebaseItem, ...],
        active_index: Optional[int],
        highlighted_indices: List[int],
        recompose: bool = False,
    ):
        """Set all of the state

        Call this method after instantiating the widget. Call it again to update all the state.
        """
        self._rebase_items = rebase_items
        self._active_index = active_index
        self._highlighted_indices = highlighted_indices

        self.styles.grid_size_rows = len(rebase_items) + 1
        # An extra row is added at the bottom so the scroll bar doesn't cover the bottom row.
        self.styles.height = len(rebase_items) + 2

        if recompose:
            self.refresh(recompose=True)

    def set_visible_files(
        self,
        visible_files: List[str | os.PathLike[str]],
        recompose: bool = False,
    ):
        """Only these files will be shown"""
        self._visible_files = visible_files
        self.styles.grid_size_columns = len(self._visible_files)

        if recompose:
            self.refresh(recompose=True)

    def action_move_left(self):
        """Highlight the file one space to the left"""
        active_item = self._rebase_items[self._active_index]

        # move left to next file indicator, or select no files (self._active_file_index == -1)
        while self._active_file_index > -1:
            self._active_file_index -= 1
            file = self._visible_files[self._active_file_index]
            if file in active_item.file_changes:
                break

        self.refresh(recompose=True)

    def action_move_right(self):
        """Highlight the file one space to the right"""
        active_item = self._rebase_items[self._active_index]

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

    def on_click(self, event: Click) -> None:
        # find clicked child index
        clicked_child_index: Optional[int] = None
        for child_index, child in enumerate(self.children):
            if child is event.widget:
                clicked_child_index = child_index
                break
        if clicked_child_index is None:
            return

        # get commit index (row) and file index (column) that was clicked
        commit_index = clicked_child_index // len(self._visible_files) - 1
        file_index = clicked_child_index % len(self._visible_files)

        self._toggle_file(commit_index, file_index)

        # select file (if there is a file at the clicked location)
        self._active_file_index = file_index
        self._toggle_file(commit_index, file_index)

    def action_toggle_file(self):
        """Toggle the status of the selected file indicator"""
        self._toggle_file(self._active_index, self._active_file_index)

    def _toggle_file(self, commit_index: int, file_index: int):
        """Toggle the file indicator at these coordinates

        If there is no indicator at this location, just a blank space, then nothing will
        happen.
        """
        # Check if there is a file change in the clicked region, or just a blank space.
        file = self._visible_files[file_index]
        file_change = self._rebase_items[commit_index].file_changes.get(file)
        if file_change is None:
            return

        new_included_state = not file_change.included

        # notify other widgets
        self.post_message(
            self.SetFileStatus(commit_index, file_change.path, new_included_state)
        )

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
                    changed = file_change.included
                else:
                    selectable = False
                    changed = False

                active = (
                    i == self._active_index
                    and j == self._active_file_index
                    and isinstance(item, RebaseItem)
                )

                yield FileChangeIndicator(changed, selectable, active, classes=classes)
