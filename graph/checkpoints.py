"""
出游计划平台 — 持久化配置

知识点：
  - MemorySaver: 内存检查点（开发用）
  - SqliteSaver: SQLite 检查点（单机持久化）
  - InMemoryStore: 内存长期记忆
  - Checkpoint 历史回溯（Time Travel）
  - 线程管理
"""

from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.memory import InMemoryStore


def create_memory_checkpointer() -> MemorySaver:
    """创建内存检查点（适合开发和演示）。

    知识点：MemorySaver 将检查点保存在内存中，
    进程重启后丢失，但开发时最简单。
    """
    return MemorySaver()


def create_sqlite_checkpointer(db_path: str = "checkpoints.db"):
    """创建 SQLite 检查点（适合单机持久化）。

    知识点：SqliteSaver 将检查点保存到 SQLite 文件，
    进程重启后可恢复。
    """
    try:
        # SQLite checkpointer 是可选依赖；项目默认没有强制安装，
        # 所以这里做 ImportError 回退，避免启动失败。
        from langgraph.checkpoint.sqlite import SqliteSaver
        return SqliteSaver.from_conn_string(db_path)
    except ImportError:
        print("⚠️ langgraph-checkpoint-sqlite 未安装，回退到 MemorySaver")
        return MemorySaver()


def create_memory_store() -> InMemoryStore:
    """创建内存长期记忆存储。

    知识点：Store 提供跨线程的记忆能力，
    可以保存用户偏好、历史行程等。
    """
    return InMemoryStore()


def list_checkpoints(graph, thread_id: str) -> list:
    """
    列出指定线程的所有检查点（Time Travel 功能）。

    知识点：
    - get_state_history(): 获取完整的状态历史
    - 每个检查点包含：config、values、next（待执行节点）
    - 可以恢复到任意历史状态
    """
    config = {"configurable": {"thread_id": thread_id}}
    # get_state_history 返回的是 LangGraph 保存的每一步状态快照。
    # 这里截断 values 只做预览，避免把完整计划文本打印得太长。
    history = list(graph.get_state_history(config))
    return [
        {
            "step": i,
            "values_preview": {k: str(v)[:50] for k, v in entry.values.items()},
            "next_nodes": entry.next,
        }
        for i, entry in enumerate(history)
    ]


def restore_to_checkpoint(graph, thread_id: str, step: int):
    """
    恢复到指定检查点。

    知识点：
    - 通过 get_state_history 获取历史
    - 用该历史的 config 重新 invoke 可以从该点继续
    """
    config = {"configurable": {"thread_id": thread_id}}
    history = list(graph.get_state_history(config))

    if step >= len(history):
        raise ValueError(f"Step {step} 超出范围，最大步数: {len(history) - 1}")

    # 返回指定历史状态本身；真正继续执行时，调用方再用 target.config 调图。
    target = history[step]
    return graph.get_state(target.config)
