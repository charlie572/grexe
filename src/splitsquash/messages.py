from typing import Optional

from textual.message import Message


# TODO: rename
class ViewFile(Message):
    """Trigger this to open a file in a sidebar"""

    def __init__(self, file_content: str):
        super().__init__()
        self.file_content = file_content
