import os.path
from os import PathLike
from typing import Iterable, Dict

from rich.style import Style
from rich.text import Text

from textual.widgets import Tree
from textual.widgets._tree import TreeNode, TreeDataType


class FileSelector(Tree):
    def __init__(self, file_paths: Iterable[str | PathLike], *args, **kwargs):
        common_path = os.path.commonpath(file_paths)
        super().__init__(
            common_path,
            data={"path": common_path, "active": True},
            *args,
            **kwargs,
        )

        file_paths = [os.path.relpath(path, common_path) for path in file_paths]
        nodes: Dict[str : TreeNode[str]] = {"": self.root}
        self.root.expand()
        for path in file_paths:
            path_elements = path.split(os.path.sep)
            for i in range(len(path_elements)):
                node_path = os.path.sep.join(path_elements[: i + 1])
                if node_path not in nodes:
                    parent_node_path = os.path.sep.join(path_elements[:i])
                    parent_node = nodes[parent_node_path]
                    node_name = path_elements[i]
                    nodes[node_path] = parent_node.add(
                        node_name,
                        expand=True,
                        data={
                            "path": path,
                            "active": True,
                        },
                    )

    def on_tree_node_selected(self, event):
        node: TreeNode[str] = event.node
        active = not node.data["active"]
        self.set_nodes_active(node, active)

    @classmethod
    def set_nodes_active(cls, node: TreeNode[str], active: bool):
        node.data["active"] = active
        for child in node.children:
            cls.set_nodes_active(child, active)

    def render_label(
        self, node: TreeNode[TreeDataType], base_style: Style, style: Style
    ) -> Text:
        text = node.label
        if node.data["active"]:
            text += " *"
        return Text.assemble(text, style=Style.chain(base_style, style))
