import os

from textual.widgets import Label


class FilenameLabel(Label):
    def __init__(self, path, *args, **kwargs):
        _, filename = os.path.split(path)
        super().__init__(filename, *args, **kwargs)
        self.path = path
