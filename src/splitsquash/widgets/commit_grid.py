from typing import Tuple, Optional, List

from git import Repo
from textual import worker, work
from textual.containers import Grid
from textual.events import Click
from textual.message import Message
from textual.widgets import Label
from textual.worker import get_current_worker

from splitsquash.merge_conflicts import MergeConflictDetectorSingleton
from splitsquash.messages import OpenTextViewer
from splitsquash.rebasing import currently_rebasing_on
from splitsquash.types import RebaseItem


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
        self.styles.grid_size_columns = 5
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

    @work(exclusive=True, thread=True)
    def _update_merge_conflict_warnings(self):
        # This is done in a separate thread, because it may be expensive. It
        # requires cherry-picking commits in a temporary repo.

        worker = get_current_worker()

        conflicting_item_indices = (
            MergeConflictDetectorSingleton().check_for_merge_conflicts(
                self._rebase_items
            )
        )

        if not worker.is_cancelled:
            self.app.call_from_thread(
                self._set_merge_conflict_warnings, conflicting_item_indices
            )

    def _set_merge_conflict_warnings(self, conflicting_item_indices):
        conflict_warnings = self.query_children(".conflict_warning")
        for rebase_item_index, conflict_warning in enumerate(conflict_warnings):
            conflict_warning.content = (
                "💥" if rebase_item_index in conflicting_item_indices else ""
            )

    def on_click(self, event: Click):
        for child_index, child in enumerate(self.children):
            if child is not event.widget:
                continue

            item_index = child_index // self.styles.grid_size_columns - 1

            if isinstance(child, Label) and child.content == "💥":
                # Clicked merge conflict marker. Open the file content in a sidebar.
                merge_conflict_text = (
                    MergeConflictDetectorSingleton().get_merge_conflict_text(
                        self._rebase_items[: item_index + 1]
                    )
                )
                self.post_message(OpenTextViewer(merge_conflict_text))
            else:
                self.post_message(self.ClickedCommit(item_index))

            return

    def compose(self):
        # header row
        yield Label("Conflicts")
        yield Label("")
        yield Label("Lines changed")
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

            yield Label("", classes=f"conflict_warning {classes}")

            yield Label(item.action, classes=f"rebase_action {classes}")

            yield Label(item.commit.hexsha[:7], classes=f"hexsha {classes}")

            num_inserted = item.commit.stats.total["insertions"]
            num_deleted = item.commit.stats.total["deletions"]
            yield Label(f"[green]+{num_inserted}[/green][red]-{num_deleted}[/red]")

            first_message_line = item.commit.message.split("\n")[0]
            yield Label(first_message_line, classes=f"commit_message {classes}")

        self._update_merge_conflict_warnings()
