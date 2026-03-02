import os
from typing import List

from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import TabbedContent, Label

from grexe.file_selector import FileSelector
from grexe.rebase_todo_widget import RebaseTodoWidget
from grexe.types import RebaseItem, FileChange


class HistoryForSelectedFilesScreen(Screen):
    CSS_PATH = "main.tcss"

    def __init__(
        self,
        rebase_items: List[RebaseItem],
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self._rebase_items = rebase_items

        self._rebase_todo_widget = RebaseTodoWidget(rebase_items, True)
        self._rebase_todo_widget.styles.width = "50%"

        file_paths: List[str | os.PathLike[str]] = sum(
            [list(item.commit.stats.files.keys()) for item in rebase_items], start=[]
        )
        file_changes = [FileChange(file_path, True) for file_path in file_paths]

        self._file_selector = FileSelector(file_changes)
        self._file_selector.styles.width = "33%"

    def get_rebase_items(self) -> List[RebaseItem]:
        return self._rebase_todo_widget.get_rebase_items()

    def on_file_selector_changed_active_files(self, event):
        active_files = set(event.active_files)
        items_visible = []
        for item in self._rebase_items:
            item_files = item.commit.stats.files.keys()
            active_files_in_item = active_files.intersection(item_files)
            items_visible.append(len(active_files_in_item) > 0)

        self._rebase_todo_widget.set_visible_items(items_visible)

    def compose(self):
        with TabbedContent():
            with Horizontal():
                yield self._file_selector
                yield self._rebase_todo_widget

            with Horizontal():
                yield Label("Second tab")
