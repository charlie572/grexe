import os
from typing import List, Tuple, Optional, Literal

from textual.containers import Grid
from textual.events import Click
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Label

from splitsquash.types import RebaseItem
from splitsquash.widgets.utility_widgets import FilenameLabel


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
                if not file_change:
                    yield Label("")
                    continue

                change_type = item.commit.stats.files[file_change.path]["change_type"]

                active = (
                    i == self._active_index
                    and j == self._active_file_index
                    and isinstance(item, RebaseItem)
                )

                yield FileChangeIndicator(
                    change_type, file_change.included, active, classes=classes
                )


class FileChangeIndicator(Widget):
    """An indicator to show in the FileGrid

    :param change_type: The change type of the file from the Stats object
                        See https://gitpython.readthedocs.io/en/stable/reference.html#git.util.Stats.
                        A = Added, D = Deleted, M = Modified, R = Renamed, T = Changed in the type
    :param included: False if the user has excluded this file from this commit.
    :param active: True if the user's cursor is hovering over this file change (text cursor, not mouse).
    """

    def __init__(
        self,
        change_type: Literal["A", "D", "M", "R", "T"],
        included: bool,
        active: bool,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self._change_type = change_type
        self._included = included
        self._active = active

    def render(self):
        change_type_colours = {
            "A": "green",
            "D": "red",
            "M": "orange",
            "R": "green",
            "T": "blue",
        }

        content = (
            self._change_type
        )  # single letter indicated type of changed (added, deleted, etc.)

        # white background if the (text) cursor is hovering over this widget
        if self._active:
            content = f"[on white]{content}[/]"

        if self._included:
            # File hasn't been excluded by user. Make it coloured
            content = f"[{change_type_colours[self._change_type]}]{content}[/]"
        else:
            # File has been excluded by user. Make it non-coloured and add strikethrough.
            content = f"[strike]{content}[/]"

        return content
