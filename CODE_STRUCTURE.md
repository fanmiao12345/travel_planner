# 代码文件职责清单

这份文档按目录说明每个代码文件的职责，方便先建立全局地图，再进入具体代码阅读。

## 根目录

- `run.py`：项目命令行入口。负责启动 Streamlit UI、运行 pytest 测试、通过 harness 执行一次命令行规划、启动独立 MCP 服务。
- `config.py`：应用配置中心。负责读取 `.env` 和环境变量，创建 OpenAI 兼容的 LLM 客户端，支持 OpenAI、Ollama、LM Studio、vLLM 等提供方。
- `requirements.txt`：Python 依赖清单。
- `.env.example`：环境变量模板，包含模型、搜索、地图、交通、餐饮等外部服务 Key。
- `README.md`：项目介绍、架构说明、启动方式和配置说明。
- `CODE_STRUCTURE.md`：当前文件，解释项目中每个代码文件的用途。
- `__init__.py`：项目根包标记文件。

## `agents/` 智能体层

- `agents/state.py`：全局旅行规划状态定义。使用 `TypedDict` 和 reducer 控制多节点写入同一字段时如何合并。
- `agents/supervisor.py`：主控调度器。负责解析用户需求、按状态路由到专业智能体、汇总最终方案，并处理人工审核。
- `agents/route_planner.py`：路线规划师。负责搜索目的地攻略、热门地点、活动时间，并调用地图路线工具安排真实行程。
- `agents/transport_advisor.py`：交通顾问。负责自驾路线、公共交通搜索、交通方式建议。
- `agents/weather_forecaster.py`：天气预报员。负责调用真实天气和空气质量工具，并生成穿衣/出行建议。
- `agents/accommodation_manager.py`：住宿管家。负责搜索住宿资料、停车、多人数入住建议。
- `agents/food_advisor.py`：美食达人。负责搜索当地美食、餐厅和多人用餐建议。
- `agents/budget_optimizer.py`：预算优化智能体。负责预算拆分、性价比比较和省钱建议。
- `agents/__init__.py`：智能体包标记文件。

## `graph/` 工作流编排层

- `graph/builder.py`：主 LangGraph 工作流构建器。注册解析、主控、专业智能体、汇总和人工审核节点，并把 ReAct agent 适配为图节点。
- `graph/subgraphs.py`：并行查询子图示例。展示如何用子图并发查询天气、交通、住宿和美食。
- `graph/checkpoints.py`：检查点和长期记忆辅助函数。封装 MemorySaver、SQLite checkpointer、状态历史查看和恢复。
- `graph/__init__.py`：图编排包标记文件。

## `harness/` 统一运行层

- `harness/travel_harness.py`：统一执行入口。封装 LangGraph `astream`、状态合并、事件流、人工审核暂停和恢复。
- `harness/__init__.py`：导出 harness 的公共类，方便 UI、CLI、测试统一导入。

## `mcp_servers/` 工具层

- `mcp_servers/search_server.py`：搜索工具服务。集成 Tavily、DuckDuckGo，提供通用搜索、目的地攻略、热门地点、活动档期和签证信息查询。
- `mcp_servers/transport_server.py`：交通工具服务。提供航班/火车样例查询、公共交通对比，以及高德/OSRM 真实自驾路线规划。
- `mcp_servers/weather_server.py`：天气工具服务。通过 Open-Meteo 查询真实天气和空气质量。
- `mcp_servers/accommodation_server.py`：住宿与餐饮样例工具。提供酒店、餐厅和美食指南查询。
- `mcp_servers/__init__.py`：MCP 工具包标记文件。

## `tools/` 本地工具层

- `tools/date_utils.py`：日期工具。统一使用 `Asia/Shanghai` 时区，提供当前日期、日期区间、天数差、周末判断等工具。
- `tools/geo_utils.py`：地理工具。提供常用城市坐标和直线距离估算，主要用于粗略判断，不替代真实地图路线。
- `tools/budget_calculator.py`：预算工具。提供每日预算计算、方案性价比排序和省钱建议。
- `tools/evidence.py`：证据抽取与质量检查工具。从 ReAct 工具返回的搜索、活动、地图、天气结果中抽取来源，给最终方案生成引用列表和证据覆盖评分。
- `tools/__init__.py`：本地工具包标记文件。

## `ui/` 前端层

- `ui/app.py`：Streamlit 主应用。负责侧边栏配置、聊天输入、调用 harness、流式展示执行细节和展示最终结果。
- `ui/components.py`：Streamlit 展示组件。封装预算图、天气卡片、交通表格、住宿/美食列表和最终方案展示。
- `ui/__init__.py`：UI 包标记文件。

## `tests/` 测试层

- `tests/test_mcp_servers.py`：工具、需求解析、harness 和配置的自动化测试。对外部服务使用 monkeypatch 测试桩，避免测试依赖网络。
- `tests/__init__.py`：测试包标记文件。
