"""
出游计划自动规划平台 — 快速启动脚本

用法：
    python run.py          # 启动 Streamlit Web UI
    python run.py test     # 运行组件测试
    python run.py harness "西安3日游，一个人，预算3000元"  # 通过 harness 跑工作流
    python run.py mcp      # 启动 MCP 服务器（独立模式）
"""

import sys
import os
import subprocess

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# 确保在项目根目录运行
# 这样无论用户从哪里执行 python run.py，相对路径都能稳定指向项目目录。
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ".")


def run_ui():
    """启动 Streamlit Web UI"""
    print("🌍 启动出游计划自动规划平台...")
    print("📡 访问地址: http://localhost:8501")
    print("💡 首次启动较慢，请耐心等待...")
    subprocess.run([sys.executable, "-m", "streamlit", "run", "ui/app.py",
                    "--server.headless", "true"])


def run_test():
    """运行组件测试"""
    # 统一委托给 pytest，避免 run.py 内部再维护一套手写测试逻辑。
    subprocess.run([sys.executable, "-m", "pytest"], check=True)


def run_harness(prompt: str):
    """通过统一 harness 执行一次规划请求"""
    import asyncio

    async def main():
        from harness import TravelPlannerHarness

        harness = TravelPlannerHarness(thread_id="cli-harness-session")
        print("=== Harness 工作流执行 ===")

        # harness.stream_request 会把 LangGraph 的更新转换成更稳定的事件：
        # 节点开始、节点完成、人工审核暂停、流程结束。
        async for event in harness.stream_request(prompt):
            if event.event_type == "node_start":
                print(f"[START] {event.node_name}")
            elif event.event_type == "node_complete":
                print(f"[DONE]  {event.node_name} ({event.elapsed:.2f}s)")
            elif event.event_type == "interrupt":
                print("[WAIT]  等待人工审核")
            elif event.event_type == "end":
                state = event.final_state
                final_plan = state.get("final_plan", {}).get("content", "")
                print("\n=== 最终方案摘要 ===")
                print(final_plan[:1200] or "暂无最终方案")

    asyncio.run(main())


def run_mcp_server(server_name: str = "weather"):
    """启动独立的 MCP 服务器"""
    # 独立启动 MCP 服务主要用于学习/调试。正常 UI 运行时，
    # Agent 直接导入这些工具函数，不需要用户手动启动每个 server。
    servers = {
        "weather": "mcp_servers.weather_server",
        "transport": "mcp_servers.transport_server",
        "accommodation": "mcp_servers.accommodation_server",
        "search": "mcp_servers.search_server",
    }
    if server_name not in servers:
        print(f"Unknown server: {server_name}")
        print(f"Available: {', '.join(servers.keys())}")
        return
    print(f"Starting MCP server: {server_name}")
    subprocess.run([sys.executable, "-m", servers[server_name]])


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "ui"

    if cmd == "ui":
        run_ui()
    elif cmd == "test":
        run_test()
    elif cmd == "harness":
        prompt = " ".join(sys.argv[2:]).strip() or "西安3日游，一个人，预算3000元，喜欢历史"
        run_harness(prompt)
    elif cmd.startswith("mcp"):
        server = sys.argv[2] if len(sys.argv) > 2 else "weather"
        run_mcp_server(server)
    else:
        print(__doc__)
