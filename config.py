"""
出游计划自动规划多智能体平台 — 配置管理

知识点：环境变量加载、模型配置、单例配置
"""

import os
from pathlib import Path
from dataclasses import dataclass, field
from dotenv import load_dotenv

# 加载 .env 文件（从项目根目录）
_project_root = Path(__file__).parent
load_dotenv(_project_root / ".env")


@dataclass
class LLMConfig:
    """LLM 配置。

    这里不绑定某一个云厂商，而是统一按 OpenAI-compatible 接口读取：
    - OpenAI 官方：base_url 使用 https://api.openai.com/v1
    - 本地模型：Ollama / LM Studio / vLLM 只要暴露 /v1 接口即可
    - 第三方网关：填入网关 base_url 和模型名即可
    """
    provider: str = field(default_factory=lambda: os.getenv("LLM_PROVIDER", "openai"))
    api_key: str = field(default_factory=lambda: os.getenv("LLM_API_KEY", os.getenv("OPENAI_API_KEY", "")))
    base_url: str = field(default_factory=lambda: os.getenv("LLM_BASE_URL", os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")))
    model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", os.getenv("OPENAI_MODEL", "gpt-4o-mini")))
    temperature: float = field(default_factory=lambda: float(os.getenv("LLM_TEMPERATURE", "0.7")))


@dataclass
class AmadeusConfig:
    """Amadeus API 配置（机票+酒店）"""
    api_key: str = field(default_factory=lambda: os.getenv("AMADEUS_API_KEY", ""))
    api_secret: str = field(default_factory=lambda: os.getenv("AMADEUS_API_SECRET", ""))


@dataclass
class SearchConfig:
    """搜索 API 配置"""
    tavily_api_key: str = field(default_factory=lambda: os.getenv("TAVILY_API_KEY", ""))


@dataclass
class YelpConfig:
    """Yelp Fusion 配置（餐饮）"""
    api_key: str = field(default_factory=lambda: os.getenv("YELP_API_KEY", ""))


@dataclass
class AppConfig:
    """应用总配置。

    AppConfig 聚合所有外部服务配置。模块底部会创建一个全局 config，
    其他文件通过 `from config import config` 复用同一份配置入口。
    """
    llm: LLMConfig = field(default_factory=LLMConfig)
    amadeus: AmadeusConfig = field(default_factory=AmadeusConfig)
    search: SearchConfig = field(default_factory=SearchConfig)
    yelp: YelpConfig = field(default_factory=YelpConfig)

    def get_llm(self):
        """获取 LLM 实例（知识点：延迟初始化）

        每次调用都从环境变量读取最新值，避免 .env 加载顺序问题。
        """
        from langchain_openai import ChatOpenAI

        # 优先读运行时环境变量。UI 侧边栏会动态写 os.environ，
        # 所以这里不能只依赖 dataclass 初始化时的值。
        api_key = (
            os.getenv("LLM_API_KEY", "")
            or os.getenv("OPENAI_API_KEY", "")
            or self.llm.api_key
            or "not-needed"
        )
        base_url = (
            os.getenv("LLM_BASE_URL", "")
            or os.getenv("OPENAI_BASE_URL", "")
            or self.llm.base_url
            or "https://api.openai.com/v1"
        )
        model = (
            os.getenv("LLM_MODEL", "")
            or os.getenv("OPENAI_MODEL", "")
            or self.llm.model
            or "gpt-4o-mini"
        )
        temperature = float(os.getenv("LLM_TEMPERATURE", str(self.llm.temperature)))

        # ChatOpenAI 同时支持 OpenAI 官方和大多数 OpenAI 兼容服务。
        # 本地模型通常不校验 API Key，因此空 Key 时使用 not-needed 占位。
        return ChatOpenAI(
            api_key=api_key,
            base_url=base_url,
            model=model,
            temperature=temperature,
        )


# 全局配置单例
config = AppConfig()
