import os
from typing import List

from textual.containers import Horizontal
from textual.screen import Screen

from grex.file_selector import FileSelector
from grex.rebase_todo_widget import RebaseTodoWidget
from grex.types import RebaseItem


class MainScreen(Screen):
    CSS_PATH = "main.tcss"

    def __init__(
        self,
        rebase_items: List[RebaseItem],
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self._files: List[str | os.PathLike[str]] = sum(
            [list(item.commit.stats.files.keys()) for item in rebase_items], start=[]
        )

        self._rebase_todo_widget = RebaseTodoWidget(rebase_items)
        self._rebase_todo_widget.styles.width = "50%"
        self._file_selector = FileSelector(self._files)
        self._file_selector.styles.width = "50%"

    def get_rebase_items(self) -> List[RebaseItem]:
        return self._rebase_todo_widget.get_rebase_items()

    def on_file_selector_changed_active_files(self, event):
        self._rebase_todo_widget.set_visible_files(event.active_files)

    def compose(self):
        with Horizontal():
            yield self._file_selector
            yield self._rebase_todo_widget
