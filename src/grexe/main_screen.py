import os
from typing import List

from textual.containers import Horizontal
from textual.screen import Screen

from grexe.file_selector import FileSelector
from grexe.rebase_todo_state import RebaseTodoState
from grexe.rebase_todo_widget import RebaseTodoWidget


class MainScreen(Screen):
    CSS_PATH = "main.tcss"

    def __init__(
        self,
        rebase_todo_state: RebaseTodoState,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        files: List[str | os.PathLike[str]] = sum(
            [
                list(item.commit.stats.files.keys())
                for item in rebase_todo_state.get_current_items()
            ],
            start=[],
        )

        self._rebase_todo_widget = RebaseTodoWidget(rebase_todo_state)
        self._rebase_todo_widget.styles.width = "50%"
        self._file_selector = FileSelector(files)
        self._file_selector.styles.width = "50%"

    def on_file_selector_changed_active_files(self, event):
        self._rebase_todo_widget.set_visible_files(event.active_files)

    def compose(self):
        with Horizontal():
            yield self._file_selector
            yield self._rebase_todo_widget
