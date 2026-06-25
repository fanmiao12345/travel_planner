"""
工作区管理器 — 路径遍历防护
"""

from __future__ import annotations

from pathlib import Path


class WorkspaceManager:
    """工作区管理器，带路径遍历防护。"""

    def __init__(self, base_path: str = "./output") -> None:
        self._base = Path(base_path).resolve()
        self._base.mkdir(parents=True, exist_ok=True)

    @property
    def base_path(self) -> str:
        return str(self._base)

    def set_base(self, path: str) -> None:
        """设置工作区根目录。"""
        self._base = Path(path).resolve()
        self._base.mkdir(parents=True, exist_ok=True)

    def resolve_path(self, relative: str) -> Path:
        """解析相对路径，防止路径遍历攻击。

        Raises:
            ValueError: 如果路径逃逸出工作区。
        """
        target = (self._base / relative).resolve()
        if not str(target).startswith(str(self._base)):
            raise ValueError(f"路径遍历攻击: {relative} 逃逸出工作区")
        return target

    def list_files(self, sub_path: str = "") -> list[dict[str, str]]:
        """列出工作区文件。"""
        dir_path = self.resolve_path(sub_path) if sub_path else self._base
        if not dir_path.is_dir():
            return []
        results = []
        for item in sorted(dir_path.iterdir()):
            results.append({
                "name": item.name,
                "path": str(item.relative_to(self._base)),
                "type": "dir" if item.is_dir() else "file",
                "size": str(item.stat().st_size) if item.is_file() else "",
            })
        return results

    def read_file(self, relative: str) -> str:
        """读取文件内容（文本）。"""
        path = self.resolve_path(relative)
        if not path.is_file():
            raise FileNotFoundError(f"文件不存在: {relative}")
        return path.read_text(encoding="utf-8")

    def read_file_bytes(self, relative: str) -> bytes:
        """读取文件内容（二进制）。"""
        path = self.resolve_path(relative)
        if not path.is_file():
            raise FileNotFoundError(f"文件不存在: {relative}")
        return path.read_bytes()

    def save_file(self, relative: str, content: str) -> str:
        """保存文件。"""
        path = self.resolve_path(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return str(path.relative_to(self._base))
