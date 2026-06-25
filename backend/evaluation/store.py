"""
评估 SQLite 存储 — 7 表

task_metrics, trajectories, eval_results, drift_alerts,
experiments, experiment_assignments, optimization_log
"""

from __future__ import annotations

import json
import sqlite3
import time
from typing import Any


class EvalStore:
    """评估数据 SQLite 存储。"""

    def __init__(self, db_path: str = ":memory:") -> None:
        self._db_path = db_path
        self._conn: sqlite3.Connection | None = None

    async def initialize(self) -> None:
        self._conn = sqlite3.connect(self._db_path)
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS task_metrics (
                task_id TEXT PRIMARY KEY,
                accuracy REAL DEFAULT 0.0,
                total_latency_ms INTEGER DEFAULT 0,
                step_latencies TEXT DEFAULT '[]',
                total_tokens INTEGER DEFAULT 0,
                tool_call_count INTEGER DEFAULT 0,
                tool_success_count INTEGER DEFAULT 0,
                tool_success_rate REAL DEFAULT 0.0,
                agent_count INTEGER DEFAULT 0,
                iteration_count INTEGER DEFAULT 0,
                status TEXT DEFAULT 'completed',
                created_at REAL DEFAULT 0,
                updated_at REAL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS trajectories (
                task_id TEXT PRIMARY KEY,
                steps TEXT DEFAULT '[]',
                created_at REAL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS eval_results (
                task_id TEXT PRIMARY KEY,
                scores TEXT DEFAULT '{}',
                reasoning TEXT DEFAULT '',
                suggestions TEXT DEFAULT '[]',
                overall_score REAL DEFAULT 0.0,
                created_at REAL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS drift_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                metric TEXT NOT NULL,
                baseline REAL DEFAULT 0.0,
                current REAL DEFAULT 0.0,
                deviation REAL DEFAULT 0.0,
                message TEXT DEFAULT '',
                created_at REAL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS experiments (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                variants TEXT DEFAULT '{}',
                status TEXT DEFAULT 'active',
                created_at REAL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS experiment_assignments (
                task_id TEXT NOT NULL,
                experiment_id TEXT NOT NULL,
                variant TEXT NOT NULL,
                created_at REAL DEFAULT 0,
                PRIMARY KEY (task_id, experiment_id)
            );
            CREATE TABLE IF NOT EXISTS optimization_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT NOT NULL,
                params TEXT DEFAULT '{}',
                reason TEXT DEFAULT '',
                created_at REAL DEFAULT 0
            );
        """)
        self._conn.commit()

    def save_task_metrics(self, metrics: dict[str, Any]) -> None:
        if not self._conn:
            return
        now = time.time()
        # 检查是否已存在该 task_id
        existing = self.get_task(metrics["task_id"])
        created_at = existing["created_at"] if existing else now

        self._conn.execute(
            """INSERT OR REPLACE INTO task_metrics
            (task_id, accuracy, total_latency_ms, step_latencies, total_tokens,
             tool_call_count, tool_success_count, tool_success_rate, agent_count,
             iteration_count, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                metrics["task_id"], metrics.get("accuracy", 0),
                metrics.get("total_latency_ms", 0), json.dumps(metrics.get("step_latencies", [])),
                metrics.get("total_tokens", 0), metrics.get("tool_call_count", 0),
                metrics.get("tool_success_count", 0), metrics.get("tool_success_rate", 0),
                metrics.get("agent_count", 0), metrics.get("iteration_count", 0),
                metrics.get("status", "completed"), created_at, now,
            ),
        )
        self._conn.commit()

    def save_trajectory(self, task_id: str, steps: list[dict]) -> None:
        if not self._conn:
            return
        self._conn.execute(
            "INSERT OR REPLACE INTO trajectories (task_id, steps, created_at) VALUES (?, ?, ?)",
            (task_id, json.dumps(steps, ensure_ascii=False), time.time()),
        )
        self._conn.commit()

    def save_eval_result(self, task_id: str, result: dict[str, Any]) -> None:
        if not self._conn:
            return
        self._conn.execute(
            """INSERT OR REPLACE INTO eval_results
            (task_id, scores, reasoning, suggestions, overall_score, created_at)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (
                task_id, json.dumps(result.get("scores", {})),
                result.get("reasoning", ""), json.dumps(result.get("suggestions", [])),
                result.get("overall_score", 0.0), time.time(),
            ),
        )
        self._conn.commit()

    def save_drift_alert(self, metric: str, baseline: float, current: float, deviation: float, message: str) -> None:
        if not self._conn:
            return
        self._conn.execute(
            "INSERT INTO drift_alerts (metric, baseline, current, deviation, message, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (metric, baseline, current, deviation, message, time.time()),
        )
        self._conn.commit()

    def get_all_metrics(self) -> list[dict[str, Any]]:
        if not self._conn:
            return []
        cursor = self._conn.execute("SELECT * FROM task_metrics ORDER BY created_at DESC")
        cols = [d[0] for d in cursor.description]
        return [dict(zip(cols, row)) for row in cursor.fetchall()]

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        if not self._conn:
            return None
        cursor = self._conn.execute("SELECT * FROM task_metrics WHERE task_id = ?", (task_id,))
        row = cursor.fetchone()
        if not row:
            return None
        cols = [d[0] for d in cursor.description]
        return dict(zip(cols, row))

    def get_trajectory(self, task_id: str) -> list[dict] | None:
        if not self._conn:
            return None
        cursor = self._conn.execute("SELECT steps FROM trajectories WHERE task_id = ?", (task_id,))
        row = cursor.fetchone()
        return json.loads(row[0]) if row else None

    def get_drift_alerts(self) -> list[dict[str, Any]]:
        if not self._conn:
            return []
        cursor = self._conn.execute("SELECT * FROM drift_alerts ORDER BY created_at DESC LIMIT 50")
        cols = [d[0] for d in cursor.description]
        return [dict(zip(cols, row)) for row in cursor.fetchall()]

    def save_optimization(self, action: str, params: dict, reason: str) -> None:
        if not self._conn:
            return
        self._conn.execute(
            "INSERT INTO optimization_log (action, params, reason, created_at) VALUES (?, ?, ?, ?)",
            (action, json.dumps(params, ensure_ascii=False), reason, time.time()),
        )
        self._conn.commit()

    def get_optimization_log(self) -> list[dict[str, Any]]:
        if not self._conn:
            return []
        cursor = self._conn.execute("SELECT * FROM optimization_log ORDER BY created_at DESC LIMIT 50")
        cols = [d[0] for d in cursor.description]
        return [dict(zip(cols, row)) for row in cursor.fetchall()]

    async def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
