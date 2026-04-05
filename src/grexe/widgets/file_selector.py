import os.path
from os import PathLike
from typing import Iterable, Dict, List, Set

from rich.style import Style
from rich.text import Text
from textual.events import Click
from textual.message import Message

from textual.widgets import Tree
from textual.widgets._tree import TreeNode, TreeDataType

from grexe.types import OptionalFile


class FileSelector(Tree):
    class ChangedActiveFiles(Message):
        def __init__(self, active_files: List[str | PathLike]):
            self.active_files = active_files
            super().__init__()

    def __init__(
        self,
        files: List[OptionalFile],
        *args,
        **kwargs,
    ):
        super().__init__(
            "",
            *args,
            **kwargs,
        )

        self._ctrl = False
        self._mouse_button = None

        self._common_path = ""

        self.set_data(files, recompose=False)

    def set_data(
        self,
        optional_files: List[OptionalFile],
        recompose: bool = True,
    ):
        """Re-create the file hierarchy with the given file changes"""
        if len(optional_files) == 0:
            self._common_path = ""
            self.reset("", data={"path": "", "active": True})
            if recompose:
                self.refresh(recompose=True)
            return
        elif len(optional_files) == 1:
            self._common_path = ""
            optional_file = optional_files[0]
            self.reset(
                optional_file.path,
                data={"path": optional_files[0].path, "active": optional_file.included},
            )
            if recompose:
                self.refresh(recompose=True)
            return

        self._common_path = os.path.commonpath(
            [change.path for change in optional_files]
        )

        self.reset(
            self._common_path,
            data={"path": self._common_path, "active": True},
        )

        self.root.expand()
        self.root.allow_expand = False

        if len(optional_files) < 2:
            return

        nodes: Dict[str : TreeNode[str]] = {"": self.root}
        for optional_file in optional_files:
            rel_path = os.path.relpath(optional_file.path, self._common_path)
            path_elements = rel_path.split(os.path.sep)
            for i in range(len(path_elements)):
                node_path = os.path.sep.join(path_elements[: i + 1])
                if node_path in nodes:
                    continue

                parent_node_path = os.path.sep.join(path_elements[:i])
                parent_node = nodes[parent_node_path]
                node_name = path_elements[i]
                nodes[node_path] = parent_node.add(
                    node_name,
                    expand=True,
                    allow_expand=False,
                    data={
                        "path": node_path,
                        "active": optional_file.included,
                    },
                )

        if recompose:
            self.refresh(recompose=True)

    def on_click(self, event: Click):
        self._mouse_button = event.button
        self._ctrl = event.ctrl

    def on_tree_node_selected(self, event):
        node: TreeNode[str] = event.node

        if self._mouse_button == 3:
            node.toggle()
            return

        make_selected_active = not node.data["active"]

        if not self._ctrl:
            self.set_nodes_active(self.root, False)

        self.set_nodes_active(node, make_selected_active)

        active_files = self.get_active_files(self.root)
        active_files = [
            os.path.join(self._common_path, rel_path) for rel_path in active_files
        ]
        self.post_message(self.ChangedActiveFiles(active_files))

    @classmethod
    def get_active_files(cls, node: TreeNode[str]):
        active_paths = []
        if len(node.children) == 0 and node.data["active"]:
            active_paths.append(node.data["path"])
        for child in node.children:
            active_paths += cls.get_active_files(child)

        return active_paths

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
