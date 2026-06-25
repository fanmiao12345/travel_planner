"""
Skill 文件系统热插拔发现

扫描指定目录的 .py 文件，动态导入触发自注册。
"""

from __future__ import annotations

import importlib.util
import threading
import time
from pathlib import Path
from typing import Any


class SkillDiscovery:
    """Skill 自动发现器。"""

    def __init__(
        self,
        registry: Any = None,
        search_paths: list[str] | None = None,
    ) -> None:
        from .registry import SkillRegistry
        self._registry = registry or SkillRegistry()
        self._search_paths: list[Path] = [
            Path(p) for p in (search_paths or [])
        ]
        self._discovered: set[str] = set()
        self._stop_event = threading.Event()

    def add_search_path(self, path: str) -> None:
        """添加搜索路径。"""
        p = Path(path)
        if p not in self._search_paths:
            self._search_paths.append(p)

    def discover(self) -> list[str]:
        """扫描目录，动态导入新发现的 Skill 模块。返回新 Skill 名称列表。"""
        new_skills: list[str] = []
        for search_path in self._search_paths:
            if not search_path.is_dir():
                continue
            for py_file in search_path.glob("*.py"):
                if py_file.name.startswith("_"):
                    continue
                module_name = py_file.stem
                if module_name in self._discovered:
                    continue
                try:
                    spec = importlib.util.spec_from_file_location(
                        f"backend.skills.{module_name}", str(py_file)
                    )
                    if spec and spec.loader:
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                        self._discovered.add(module_name)
                        # 模块级自注册会自动调用 SkillRegistry().register()
                except Exception:
                    pass
        # 返回本次新发现的 Skill
        return [
            s.name for s in self._registry.list_skills()
            if s.name not in self._discovered
        ]

    def watch_and_discover(
        self,
        interval_s: float = 5.0,
        callback: Any = None,
    ) -> None:
        """阻塞式后台监控，定期扫描新 Skill。"""
        self._stop_event.clear()
        while not self._stop_event.is_set():
            new = self.discover()
            if new and callback:
                callback(new)
            self._stop_event.wait(interval_s)

    def stop_watching(self) -> None:
        """停止后台监控。"""
        self._stop_event.set()
