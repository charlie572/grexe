import os.path
from os import PathLike
from typing import Iterable

from textual.widgets import Tree


class FileSelector(Tree):
    def __init__(self, file_paths: Iterable[str | PathLike], *args, **kwargs):
        common_path = os.path.commonpath(file_paths)
        super().__init__(common_path, *args, **kwargs)

        file_paths = [os.path.relpath(path, common_path) for path in file_paths]
        nodes = {"": self.root}
        self.root.expand()
        for path in file_paths:
            path_elements = path.split(os.path.sep)
            for i in range(len(path_elements)):
                node_path = os.path.sep.join(path_elements[: i + 1])
                if node_path not in nodes:
                    parent_node_path = os.path.sep.join(path_elements[:i])
                    parent_node = nodes[parent_node_path]
                    node_name = path_elements[i]
                    nodes[node_path] = parent_node.add(node_name, expand=True)
