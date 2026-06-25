"""
出游计划自动规划多智能体平台 — 配置管理 (Pydantic Settings)

使用 pydantic-settings 从环境变量和 .env 文件加载配置。
提供 get_settings() 单例和 get_llm() 工厂方法。
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用总配置，从环境变量 / .env 文件自动加载。"""

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parent.parent.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── LLM ──────────────────────────────────────────────
    llm_provider: str = "openai"
    llm_api_key: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"
    llm_temperature: float = 0.7

    # 兼容旧版 OPENAI_* 环境变量
    openai_api_key: str = ""
    openai_base_url: str = ""
    openai_model: str = ""

    # ── 搜索 ─────────────────────────────────────────────
    tavily_api_key: str = ""

    # ── 高德地图 ─────────────────────────────────────────
    amap_api_key: str = ""

    # ── 服务器 ────────────────────────────────────────────
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    # ── Agent 预算 ────────────────────────────────────────
    max_orchestrator_iterations: int = 90
    max_subagent_iterations: int = 50
    max_concurrent_subagents: int = 3

    # ── 记忆 ──────────────────────────────────────────────
    memory_working_window: int = 20
    memory_db_path: str = "./data/memory.db"
    semantic_memory_path: str = "./data/user_profile.json"

    # ── 评估 ──────────────────────────────────────────────
    eval_enabled: bool = True
    eval_auto_judge: bool = True
    eval_auto_optimize: bool = False
    eval_model: str = ""  # 空则用主模型
    eval_drift_threshold: float = 0.2
    eval_drift_min_samples: int = 3
    eval_db_path: str = "./data/eval.db"

    # ── 证据 ──────────────────────────────────────────────
    evidence_db_path: str = "./data/evidence.db"

    # ── 工作区 ────────────────────────────────────────────
    workspace_path: str = "./output"

    # ── 旧版兼容 ─────────────────────────────────────────
    amadeus_api_key: str = ""
    amadeus_api_secret: str = ""
    yelp_api_key: str = ""

    @property
    def effective_api_key(self) -> str:
        """获取有效的 API Key，兼容旧版环境变量。"""
        return (
            self.llm_api_key
            or self.openai_api_key
            or "not-needed"
        )

    @property
    def effective_base_url(self) -> str:
        """获取有效的 Base URL，兼容旧版环境变量。"""
        return (
            self.llm_base_url
            or self.openai_base_url
            or "https://api.openai.com/v1"
        )

    @property
    def effective_model(self) -> str:
        """获取有效的模型名，兼容旧版环境变量。"""
        return (
            self.llm_model
            or self.openai_model
            or "gpt-4o-mini"
        )

    def get_llm(self):
        """获取 LLM 实例（延迟初始化）。

        每次调用都从 Settings 读取最新值。Streamlit UI 侧边栏
        会动态写 os.environ，调用前应先 reset_settings()。
        """
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            api_key=self.effective_api_key,
            base_url=self.effective_base_url,
            model=self.effective_model,
            temperature=self.llm_temperature,
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """获取全局配置单例。"""
    return Settings()


def reset_settings() -> None:
    """重置配置单例（用于测试或 UI 热切换）。"""
    get_settings.cache_clear()
