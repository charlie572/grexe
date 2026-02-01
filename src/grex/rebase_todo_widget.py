import os
from copy import deepcopy
from typing import List, Tuple, Literal, Optional

from textual.containers import Horizontal, Grid, Vertical
from textual.events import Click, Key
from textual.widget import Widget
from textual.widgets import Label

from grex.distribute import distribute_changes
from grex.types import RebaseItem, RebaseAction
from grex.widgets import FilenameLabel, FileChangeIndicator


class RebaseTodoWidget(Widget):
    CSS_PATH = "main.tcss"

    def __init__(
        self,
        rebase_items: List[RebaseItem],
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self.can_focus = True

        self._history: List[Tuple[RebaseItem, ...]] = [tuple(rebase_items)]
        self._history_index = 0
        self._active_index = 0
        self._active_file_index = -1
        self._selected = [False] * len(rebase_items)
        self._distribute_sources: Optional[List[int]] = None

        self._state: Literal["idle", "moving", "selecting_distribute_targets"] = "idle"

        self._visible_files: List[str | os.PathLike[str]] = sum(
            [list(item.commit.stats.files.keys()) for item in rebase_items], start=[]
        )
        self._visible_files = list(set(self._visible_files))

        self._last_hovered_file = None

    def on_key(self, event: Key):
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
            self.action_pick()
        if event.key == "f":
            self.action_fixup()
        if event.key == "s":
            self.action_squash()
        if event.key == "e":
            self.action_edit()
        if event.key == "r":
            self.action_reword()
        if event.key == "d":
            self.action_drop()
        if event.key == "m":
            self.action_move_commits()
        if event.key == "c":
            self.action_copy()
        if event.key == "t":
            self.action_toggle_file()
        if event.key == "ctrl+a":
            self.action_select_all()
        if event.key == "ctrl+z":
            self.action_undo()
        if event.key == "ctrl+y":
            self.action_redo()
        if event.key == "q":
            self.action_distribute()

    @property
    def num_commits(self):
        return len(self._history[self._history_index])

    def get_rebase_items(self):
        return self._history[self._history_index]

    def _set_rebase_items(self, rebase_items: Tuple[RebaseItem, ...]):
        self._history = self._history[: self._history_index + 1] + [rebase_items]
        self._history_index += 1

    def action_distribute(self):
        if self._state == "idle":
            self._distribute_sources = [
                i for i in range(len(self._selected)) if self._selected[i]
            ]
            if len(self._distribute_sources) == 0:
                return
            self._selected = [False] * len(self._selected)
            self._state = "selecting_distribute_targets"
            self.refresh(recompose=True)
        elif self._state == "selecting_distribute_targets":
            distribute_targets = [
                i for i in range(len(self._selected)) if self._selected[i]
            ]
            if len(self._distribute_sources) > 0:
                distributed_items, error = distribute_changes(
                    self._distribute_sources,
                    distribute_targets,
                    self.get_rebase_items(),
                )
                if error is not None:
                    self.notify(error, severity="error", timeout=10)
                else:
                    self._set_rebase_items(distributed_items)
            self._selected = [False] * self.num_commits
            self._distribute_sources = None
            self._state = "idle"
            self.refresh(recompose=True)

    def action_undo(self):
        self._history_index = max(0, self._history_index - 1)
        self._selected = [False] * len(self._history[self._history_index])
        self.refresh(recompose=True)

    def action_redo(self):
        self._history_index = min(self.num_commits - 1, self._history_index + 1)
        self._selected = [False] * len(self._history[self._history_index])
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
            rebase_items = self.get_rebase_items()

        selected_items = self._get_selected(rebase_items)
        if len(selected_items) == 0:
            return [rebase_items[self._active_index]]
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
            return [self._active_index]
        else:
            return selected_indices

    def _get_selected(self, rebase_items=None, indices=False):
        if rebase_items is None:
            rebase_items = self.get_rebase_items()

        result = []
        for i, item in enumerate(rebase_items):
            if self._selected[i]:
                if indices:
                    result.append(i)
                else:
                    result.append(item)

        return result

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
            rebase_items = self.get_rebase_items()
            file = self._visible_files[file_index]
            file_change = rebase_items[commit_index].file_changes.get(file)
            if file_change is None:
                # This file change isn't included in this commit. It is a blank space in the UI. Do nothing.
                return

            # select commit
            self._active_index = commit_index
            self._selected = [False] * self.num_commits
            self._selected[commit_index] = True

            # select file
            self._active_file_index = file_index

            # toggle file
            file_change.modified = not file_change.modified
            self._set_rebase_items(rebase_items)

            self.refresh(recompose=True)
            return

        # check if a commit was clicked
        commit_grid = self.query_one("#commit_grid")
        for child_index, child in enumerate(commit_grid.children):
            if child is not event.widget:
                continue

            # Commit was clicked. Select it.
            commit_index = child_index // 3 - 1
            self._active_index = commit_index
            self._selected = [False] * self.num_commits
            self._selected[commit_index] = True

            self.refresh(recompose=True)
            return

    def action_copy(self):
        rebase_items = list(deepcopy(self.get_rebase_items()))
        active_item = rebase_items[self._active_index]

        rebase_items.insert(self._active_index + 1, deepcopy(active_item))
        self._selected.insert(self._active_index + 1, False)

        self._set_rebase_items(tuple(rebase_items))
        self.refresh(recompose=True)

    def action_toggle_file(self):
        rebase_items = list(deepcopy(self.get_rebase_items()))
        active_item: RebaseItem = rebase_items[self._active_index]

        file = self._visible_files[self._active_file_index]
        file_change = active_item.file_changes[file]
        file_change.modified = not file_change.modified

        self._set_rebase_items(tuple(rebase_items))
        self.refresh(recompose=True)

    def action_move_left(self):
        active_item = self.get_rebase_items()[self._active_index]
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
        active_item = self.get_rebase_items()[self._active_index]
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
            rebase_items = list(deepcopy(self.get_rebase_items()))

            # remove selected widgets
            indices_to_move = self._get_indices_to_modify()
            items_to_move = [rebase_items.pop(i) for i in reversed(indices_to_move)]

            # insert widgets back again as one block, with the bottom commit at its original index
            dest_index = indices_to_move[-1] - len(indices_to_move) + 1
            for item in items_to_move:
                rebase_items.insert(dest_index, item)

            self._selected[:] = [False] * self.num_commits
            for i in range(dest_index, dest_index + len(items_to_move)):
                self._selected[i] = True

            self._state = "moving"

            self._set_rebase_items(tuple(rebase_items))
            self.refresh(recompose=True)
        elif self._state == "moving":
            selected_indices = self._get_selected(indices=True)

            self._active_index = selected_indices[0]
            self._selected[:] = [False] * self.num_commits

            self._state = "idle"

            self.refresh(recompose=True)

    def action_move_up(self):
        if self._state == "moving":
            rebase_items = list(deepcopy(self.get_rebase_items()))
            selected_indices = [i for i in range(self.num_commits) if self._selected[i]]
            if selected_indices[0] == 0:
                return

            item_before_selected = rebase_items.pop(selected_indices[0] - 1)
            rebase_items.insert(selected_indices[-1], item_before_selected)
            self._set_rebase_items(tuple(rebase_items))

            self._selected[:] = [False] * self.num_commits
            for i in selected_indices:
                self._selected[i - 1] = True

            self.refresh(recompose=True)
        else:
            self._active_index = max(0, self._active_index - 1)
            self.refresh(recompose=True)

    def action_move_down(self):
        if self._state == "moving":
            rebase_items = list(deepcopy(self.get_rebase_items()))

            selected_indices = self._get_selected(indices=True)
            if selected_indices[-1] == len(rebase_items) - 1:
                return

            item_after_selected = rebase_items.pop(selected_indices[-1] + 1)
            rebase_items.insert(selected_indices[0], item_after_selected)
            self._set_rebase_items(tuple(rebase_items))

            self._selected[:] = [False] * len(self._selected)
            for i in selected_indices:
                self._selected[i + 1] = True

            self.refresh(recompose=True)
        else:
            self._active_index = min(self.num_commits - 1, self._active_index + 1)
            self.refresh(recompose=True)

    def action_select(self):
        self._selected[self._active_index] = not self._selected[self._active_index]
        self.refresh(recompose=True)

    def action_select_all(self):
        if self._state != "idle":
            return

        selected = not self._selected[self._active_index]
        self._selected[:] = [selected] * self.num_commits
        self.refresh(recompose=True)

    def _set_rebase_action(self, action: RebaseAction):
        if self._state != "idle":
            return

        rebase_items = deepcopy(self.get_rebase_items())

        for item in self._get_items_to_modify(rebase_items):
            item.action = action

        self._set_rebase_items(rebase_items)
        self.refresh(recompose=True)

    def action_edit(self):
        self._set_rebase_action("edit")

    def action_pick(self):
        self._set_rebase_action("pick")

    def action_fixup(self):
        self._set_rebase_action("fixup")

    def action_squash(self):
        self._set_rebase_action("squash")

    def action_drop(self):
        self._set_rebase_action("drop")

    def action_reword(self):
        self._set_rebase_action("reword")

    def set_visible_files(self, visible_files):
        self._visible_files = visible_files
        self.refresh(recompose=True)

    def compose(self):
        rebase_items = self.get_rebase_items()

        # The left half of the widget shows the rebase actions, hashes, and commit messages. The
        # right half shows the file changes. The right half is scrollable horizontally. Both halves
        # are grid layouts.

        with Vertical():
            status_text = (
                "Select commits to distribute into..."
                if self._state == "selecting_distribute_targets"
                else ""
            )
            yield Label(status_text)

            with Horizontal():
                with Grid(id="commit_grid") as commit_grid:
                    commit_grid.styles.grid_columns = "auto"
                    commit_grid.styles.grid_gutter_vertical = 2
                    commit_grid.styles.grid_rows = "1"
                    commit_grid.styles.grid_size_rows = len(rebase_items) + 1
                    commit_grid.styles.grid_size_columns = 3
                    commit_grid.styles.height = len(rebase_items) + 1

                    # header row
                    yield Label("")
                    yield Label("")
                    yield Label("")

                    # commit rows
                    for i, item in enumerate(rebase_items):
                        classes = []
                        if i == self._active_index and self._state != "moving":
                            classes.append("active")
                        if self._selected[i]:
                            classes.append("selected")
                        classes = " ".join(classes)

                        yield Label(item.action, classes=f"rebase_action {classes}")

                        yield Label(item.commit.hexsha[:7], classes=f"hexsha {classes}")

                        first_message_line = item.commit.message.split("\n")[0]
                        yield Label(
                            first_message_line, classes=f"commit_message {classes}"
                        )

                with Grid(id="file_grid") as file_grid:
                    file_grid.styles.grid_columns = "auto"
                    file_grid.styles.grid_gutter_vertical = 1
                    file_grid.styles.grid_rows = "1"
                    file_grid.styles.grid_size_rows = len(rebase_items) + 1
                    file_grid.styles.grid_size_columns = len(self._visible_files)
                    # An extra row is added at the bottom so the scroll bar doesn't cover the bottom row.
                    file_grid.styles.height = len(rebase_items) + 2
                    file_grid.styles.overflow_x = "auto"

                    # header row
                    for file in self._visible_files:
                        yield FilenameLabel(file, classes="filename")

                    # commit rows
                    for i, item in enumerate(rebase_items):
                        classes = []
                        if i == self._active_index and self._state != "moving":
                            classes.append("active")
                        if self._selected[i]:
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

                            yield FileChangeIndicator(
                                changed, selectable, active, classes=classes
                            )
