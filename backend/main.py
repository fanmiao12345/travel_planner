"""
出游计划自动规划多智能体平台 — FastAPI 入口

用法:
    python -m backend.main
    或
    uvicorn backend.main:create_app --factory --reload --host 0.0.0.0 --port 8000
"""

import uvicorn

from backend.api.app import create_app


def main() -> None:
    """启动 uvicorn 服务器。"""
    from backend.core.config import get_settings
    settings = get_settings()
    uvicorn.run(
        "backend.main:create_app",
        factory=True,
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )


if __name__ == "__main__":
    main()
