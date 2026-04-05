from typing import Tuple, Optional, List

from textual.containers import Grid
from textual.events import Click
from textual.message import Message
from textual.widgets import Label

from grexe.types import RebaseItem


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
