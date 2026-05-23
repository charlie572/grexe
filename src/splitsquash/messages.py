from typing import Optional

from textual.message import Message


class ViewFile(Message):
    """Trigger this to open a file in a sidebar"""

    def __init__(self, file_content: str, language: Optional[str] = None):
        super().__init__()
        self.file_content = file_content
        self.language = language
