from copy import deepcopy
from typing import Optional

from textual.containers import Horizontal

from grexe.file_selector import FileSelector
from grexe.rebase_todo_state import RebaseTodoState, RebaseTodoStateAndCursor
from grexe.rebase_todo_widget import RebaseTodoWidget


class DefaultEditorWidget(Horizontal):
    """Allows you to edit the rebase todo

    It shows a RebaseTodoWidget on the right side, and a FileSelector on the left side.
    The FileSelectors shows the files in the selected commit, and allows you to drop
    some files from that commit.
    """

    CSS_PATH = "main.tcss"

    def __init__(
        self,
        rebase_todo_state: RebaseTodoState,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self._todo_state = RebaseTodoStateAndCursor(rebase_todo_state)

        self._rebase_todo_widget: Optional[RebaseTodoWidget] = None
        self._file_selector: Optional[FileSelector] = None

    def set_rebase_todo_state(
        self,
        rebase_todo_state: RebaseTodoState,
        recompose: bool = False,
    ):
        self._todo_state = RebaseTodoStateAndCursor(rebase_todo_state)
        if recompose:
            self.refresh(recompose=True)

    def on_file_selector_changed_active_files(self, event):
        # set included files in active commit

        rebase_items = deepcopy(self._todo_state.get_current_items())
        active_item = rebase_items[self._todo_state.cursor]

        for file_change in active_item.file_changes.values():
            file_change.included = False
        for file_path in event.active_files:
            active_item.file_changes[file_path].included = True

        self._todo_state.modify_items(rebase_items, clear_selection=False)
        self._rebase_todo_widget.update_state(recompose=True, notify_other_widets=False)

    def on_rebase_todo_widget_updated(self, event):
        # re-create file selector with files of new active commit
        active_item = self._todo_state.get_active_item()
        file_changes = list(active_item.file_changes.values())
        self._file_selector.set_data(file_changes)

    def compose(self):
        self._file_selector = FileSelector([])
        self._file_selector.styles.width = "50%"
        yield self._file_selector

        self._rebase_todo_widget = RebaseTodoWidget(self._todo_state, False)
        self._rebase_todo_widget.styles.width = "50%"
        yield self._rebase_todo_widget
