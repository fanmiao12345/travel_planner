# 🌍 出游计划自动规划多智能体平台

基于 **Harness + LangGraph + MCP + Streamlit** 构建的出游计划自动规划系统，覆盖多智能体协作核心知识点。

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────┐
│                Streamlit Web UI                      │
│    对话界面 + 行程卡片 + 预算图表 + 天气展示          │
└───────────────────────┬─────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────┐
│              Harness 统一运行层                       │
│  thread_id · 状态合并 · 流式事件 · interrupt/resume    │
└───────────────────────┬─────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────┐
│           🎯 Supervisor 主控智能体                    │
│     意图理解 → 路由分发 → 汇总 → 反思优化             │
└──┬──────┬──────┬──────┬──────┬──────┬───────────────┘
   │      │      │      │      │      │
   ▼      ▼      ▼      ▼      ▼      ▼
 🗺️路线  🌤️天气  🚂交通  🏨住宿  🍜美食  💰省钱
 规划师  预报员  顾问   管家   达人   精算师
   │      │      │      │      │      │
   ▼      ▼      ▼      ▼      ▼      ▼
┌─────────────────────────────────────────────────────┐
│              🔧 MCP 工具服务器集群                    │
│  天气(Open-Meteo) · 交通(Amadeus) · 住宿 · 搜索     │
└─────────────────────────────────────────────────────┘
```

## 📚 知识点覆盖

| 知识点 | 实现位置 | 说明 |
|--------|----------|------|
| **多智能体协作** | `agents/supervisor.py` | Supervisor 路由 + 6个专业 Agent |
| **工具调用 (MCP)** | `mcp_servers/` | 4个 MCP Server，FastMCP 构建 |
| **状态管理** | `agents/state.py` | TypedDict + Annotated + 自定义 Reducer |
| **路由分发** | `agents/supervisor.py` | Command(goto=...) 条件路由 |
| **人机交互** | `agents/supervisor.py` | interrupt() + Command(resume=...) |
| **反思机制** | `graph/builder.py` | 生成→审核→迭代优化循环 |
| **记忆系统** | `graph/checkpoints.py` | MemorySaver + InMemoryStore |
| **并行执行** | `graph/subgraphs.py` | asyncio.gather 并行查询 |
| **流式输出** | `ui/app.py` | astream + stream_mode |
| **统一 Harness** | `harness/travel_harness.py` | UI、CLI、测试共用同一工作流运行入口 |
| **子图嵌套** | `graph/subgraphs.py` | 子图作为节点复用 |
| **条件边** | `graph/builder.py` | add_conditional_edges |
| **图构建** | `graph/builder.py` | StateGraph 节点+边编排 |

## 🚀 快速开始

### 1. 安装依赖

```bash
cd travel_planner
pip install -r requirements.txt
```

### 2. 配置环境变量（可选）

```bash
cp .env.example .env
# 编辑 .env，填入 API Key
```

### 3. 启动应用

```bash
cd travel_planner
streamlit run ui/app.py
```

浏览器打开 http://localhost:8501 即可使用。

也可以通过 harness 直接跑一次工作流：

```bash
python run.py harness "西安3日游，一个人，预算3000元，喜欢历史"
```

## 🎮 使用示例

在聊天框输入：
- "我想从北京去成都玩3天，预算5000元"
- "从上海到三亚5天4晚，2人，预算15000元"
- "西安3日游，一个人，预算3000元，喜欢历史"

系统会自动：
1. 🗺️ 规划游玩路线
2. 🌤️ 查询天气预报
3. 🚂 搜索交通方案
4. 🏨 推荐住宿
5. 🍜 推荐美食
6. 💰 优化预算

## 📁 项目结构

```
travel_planner/
├── config.py                 # 配置管理
├── CODE_STRUCTURE.md         # 每个代码文件的职责清单
├── harness/                  # 统一运行 harness
│   └── travel_harness.py     # LangGraph 执行、流式事件、状态合并、恢复审核
├── mcp_servers/              # MCP 工具服务器
│   ├── weather_server.py     # 天气 MCP (Open-Meteo)
│   ├── transport_server.py   # 交通 MCP (航班+火车)
│   ├── accommodation_server.py # 住宿餐饮 MCP
│   └── search_server.py      # 搜索 MCP (Tavily/DuckDuckGo)
├── agents/                   # 智能体定义
│   ├── state.py              # 状态定义 (TypedDict + Reducer)
│   ├── supervisor.py         # Supervisor 主控 + 路由 + 反思
│   ├── route_planner.py      # 🗺️ 路线规划师
│   ├── transport_advisor.py  # 🚂 交通顾问
│   ├── weather_forecaster.py # 🌤️ 天气预报员
│   ├── accommodation_manager.py # 🏨 住宿管家
│   ├── food_advisor.py       # 🍜 美食达人
│   └── budget_optimizer.py   # 💰 省钱精算师
├── graph/                    # 图编排
│   ├── builder.py            # 主图构建 (StateGraph)
│   ├── subgraphs.py          # 子图 (并行查询)
│   └── checkpoints.py        # 持久化配置
├── tools/                    # 辅助工具
│   ├── date_utils.py         # 日期计算
│   ├── geo_utils.py          # 地理距离
│   └── budget_calculator.py  # 预算计算
├── ui/                       # 前端
│   ├── app.py                # Streamlit 主应用
│   └── components.py         # UI 组件
└── tests/                    # 测试
```

## 🔧 模型和 API 配置

系统使用 OpenAI 兼容接口，不限定 OpenAI 官方服务。侧边栏可以选择：

| 模式 | Base URL 示例 | API Key |
|------|---------------|---------|
| OpenAI 官方 | `https://api.openai.com/v1` | 需要 |
| Ollama 本地 | `http://127.0.0.1:11434/v1` | 通常不需要 |
| LM Studio 本地 | `http://127.0.0.1:1234/v1` | 通常不需要 |
| vLLM / Xinference | `http://127.0.0.1:8000/v1` | 取决于部署 |
| 自定义兼容接口 | 按你的网关填写 | 取决于网关 |

`.env` 里也可以配置：

```bash
LLM_PROVIDER=ollama
LLM_BASE_URL=http://127.0.0.1:11434/v1
LLM_MODEL=qwen2.5:7b
LLM_API_KEY=
```

其它服务：

| 服务 | 用途 | 说明 |
|------|------|------|
| Open-Meteo | 天气数据 | 无需 key |
| Tavily | 联网搜索 | 可选；配置后热门景点/攻略搜索更好 |
| AMap 高德地图 | 自驾路线/景点间路线 | 可选但推荐；配置后国内路线更准确 |
| Amadeus | 机票+酒店 | 可选 |
| Yelp | 餐饮数据 | 可选 |

## 🎓 学习建议

1. **配置模型提供方**：OpenAI、Ollama、LM Studio 或其它 OpenAI 兼容服务
2. **阅读 `agents/state.py`**：理解状态管理
3. **阅读 `agents/supervisor.py`**：理解路由和反思
4. **阅读 `mcp_servers/`**：理解 MCP Server 构建
5. **阅读 `harness/travel_harness.py`**：理解统一执行入口
6. **阅读 `graph/builder.py`**：理解图编排
7. **尝试修改 Agent Prompt**：观察行为变化
8. **添加新的 MCP Server**：扩展系统能力

## License

MIT
