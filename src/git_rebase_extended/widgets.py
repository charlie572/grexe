from textual.widget import Widget


class FileChange(Widget):
    def __init__(self, changed: bool, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._changed = changed

    def render(self):
        content = "⬤" if self._changed else " "
        return f" [on $secondary]{content} [/on $secondary] "
