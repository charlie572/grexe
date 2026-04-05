from textual.containers import Horizontal

from grexe.utility_functions import get_files_modified
from grexe.widgets.file_selector import FileSelector
from grexe.rebase_todo.rebase_todo_state import (
    RebaseTodoState,
    RebaseTodoStateAndCursor,
)
from grexe.widgets.rebase_todo_widget import RebaseTodoWidget
from grexe.types import OptionalFile


class EditorWidgetWithFileGrid(Horizontal):
    """Allows you to edit the rebase todo, and view a FileGrid with the files for each commit

    It shows a FileSelector on the left side, and a RebaseTodoWidget with a FileGrid on
    the right side. You can use the FileSelector to select which files to show in the
    FileGrid.
    """

    CSS_PATH = "../styles/main.tcss"

    def __init__(
        self,
        rebase_todo_state: RebaseTodoState,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self._todo_state = RebaseTodoStateAndCursor(rebase_todo_state)

        self._rebase_todo_widget = RebaseTodoWidget(self._todo_state, True)
        self._rebase_todo_widget.styles.width = "66%"

        # build list of all files modified in this set of rebase items
        all_files = get_files_modified(self._todo_state.get_original_items())

        self._file_selector = FileSelector(
            [OptionalFile(file, True) for file in all_files]
        )
        self._file_selector.styles.width = "33%"

    def set_rebase_todo_state(
        self,
        rebase_todo_state: RebaseTodoState,
        recompose: bool = False,
    ):
        self._todo_state = RebaseTodoStateAndCursor(rebase_todo_state)

        all_files = get_files_modified(self._todo_state.get_original_items())
        self._file_selector.set_data(
            [OptionalFile(file, True) for file in all_files],
            recompose=False,
        )

        if recompose:
            self.refresh(recompose=True)

    def on_file_selector_changed_active_files(self, event):
        self._rebase_todo_widget.file_grid.set_visible_files(
            event.active_files, recompose=True
        )

    def compose(self):
        yield self._file_selector
        yield self._rebase_todo_widget
