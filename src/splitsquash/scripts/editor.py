import argparse
from typing import List, Optional

from git import Repo
from textual.app import App
from textual.containers import Horizontal
from textual.widgets import TabbedContent, Tabs, TextArea

from splitsquash.messages import ViewFile
from splitsquash.widgets.editor_widget_with_file_grid import EditorWidgetWithFileGrid
from splitsquash.widgets.default_editor_widget import DefaultEditorWidget
from splitsquash.rebase_todo.rebase_todo_state import RebaseTodoState
from splitsquash.rebasing import parse_rebase_items, create_rebase_todo_text
from splitsquash.types import RebaseItem


class GitRebaseExtendedEditor(App):
    CSS_PATH = "../styles/main.tcss"

    BINDINGS = [
        ("enter", "submit", "Submit and perform rebase."),
    ]

    def __init__(self, rebase_items: List[RebaseItem], *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._rebase_todo_state = RebaseTodoState(rebase_items)
        self._result: Optional[str] = None

        self._editor_widgets = {
            "Default Editor": DefaultEditorWidget(self._rebase_todo_state),
            "Editor With File Grid": EditorWidgetWithFileGrid(self._rebase_todo_state),
        }
        self._file_view_widget: Optional[TextArea] = None

    def action_quit(self) -> None:
        # Return exit code 1, so the rebase isn't performed.
        exit(1)

    def get_result(self):
        return self._result

    def action_submit(self):
        rebase_items = self._rebase_todo_state.get_current_items()
        self._result = create_rebase_todo_text(rebase_items)
        self.exit()

    def on_tabbed_content_tab_activated(self, event: Tabs.TabMessage):
        # Pass rebase todo state to new editor widget and refresh. This means changes
        # applied since this editor was last focussed will be visible.
        editor_widget = self._editor_widgets[event.tab.label]
        editor_widget.set_rebase_todo_state(self._rebase_todo_state, recompose=True)

    def on_view_file(self, event: ViewFile):
        # TODO: add close button
        self._file_view_widget = TextArea(
            event.file_content,
            language=event.language,
            show_line_numbers=True,
            read_only=True,
        )
        self.refresh(recompose=True)

    def compose(self):
        with Horizontal():
            with TabbedContent(
                "Default Editor", "Editor With File Grid"
            ) as tabbed_content:
                tabbed_content.styles.width = "2fr"
                yield self._editor_widgets["Default Editor"]
                yield self._editor_widgets["Editor With File Grid"]

            if self._file_view_widget is not None:
                self._file_view_widget.styles.width = "1fr"
                yield self._file_view_widget


def main():
    parser = argparse.ArgumentParser(
        "splitsquash",
        description="An editor for git rebase todo files.",
    )
    parser.add_argument("rebase_todo_file", type=str)
    args = parser.parse_args()

    repo = Repo(".")

    # parse rebase to-do file
    with open(args.rebase_todo_file, "r") as f:
        rebase_todo_text = f.read()
    rebase_items = parse_rebase_items(rebase_todo_text, repo)

    app = GitRebaseExtendedEditor(rebase_items)
    app.run()

    new_rebase_todo_text = app.get_result()
    if new_rebase_todo_text is not None:
        with open(args.rebase_todo_file, "w") as f:
            f.write(new_rebase_todo_text)


if __name__ == "__main__":
    main()
