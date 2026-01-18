import os

from textual.widget import Widget
from textual.widgets import Label


class FileChangeIndicator(Widget):
    def __init__(self, changed: bool, selectable: bool, active: bool, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._selectable = selectable
        self._changed = changed
        self._active = active

    def render(self):
        if not self._selectable:
            content = " "
        elif self._changed:
            content = "⬤"
        else:
            content = "╳"

        content_colour = "$primary" if self._active else "white"
        return f" [{content_colour} on $secondary]{content} [/] "


class FilenameLabel(Label):
    def __init__(self, path, *args, **kwargs):
        _, filename = os.path.split(path)
        super().__init__(filename, *args, **kwargs)
        self.path = path
