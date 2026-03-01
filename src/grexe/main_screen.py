import os
from typing import List

from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import TabbedContent, Label

from grexe.file_selector import FileSelector
from grexe.rebase_todo_widget import RebaseTodoWidget
from grexe.types import RebaseItem


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

        self._rebase_todo_widget = RebaseTodoWidget(rebase_items, False)
        self._rebase_todo_widget.styles.width = "50%"

        file_changes = list(
            self._rebase_todo_widget.get_active_item().file_changes.values()
        )

        self._file_selector = FileSelector(file_changes)
        self._file_selector.styles.width = "50%"

    def get_rebase_items(self) -> List[RebaseItem]:
        return self._rebase_todo_widget.get_rebase_items()

    def on_rebase_todo_widget_changed_active_item(self, event):
        # re-create file selector with files of new active commit
        file_changes = list(event.active_item.file_changes.values())
        self._file_selector = FileSelector(file_changes)

        # refresh screen without de-focussing widgets
        focussed_widget = self.focused
        self.refresh(recompose=True)
        focussed_widget.focus()

    def on_file_selector_changed_active_files(self, event):
        # set modified files in active commit
        active_item = self._rebase_todo_widget.get_active_item()
        for file_change in active_item.file_changes.values():
            file_change.modified = False
        for file_path in event.active_files:
            active_item.file_changes[file_path].modified = True

    def compose(self):
        with TabbedContent():
            with Horizontal():
                yield self._file_selector
                yield self._rebase_todo_widget

            with Horizontal():
                yield Label("Second tab")
