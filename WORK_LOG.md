# 2025-06-24 工作日志

## 上午完成的修复

1. **流式输出优化**
   - `parse_request_node` 和 `summarize_node` 从 `llm.ainvoke()` 改为 `llm.astream()`，实现 token 级实时输出
   - 添加 `ainvoke()` 兜底：如果 `astream()` 返回空内容，自动用非流式获取完整结果
   - 前端添加"正在思考..."动画，`isPlanning=true` 但 `planContent` 为空时显示

2. **人工审核流程修复**
   - **根本原因**：`astream_events` 不触发 `interrupt` 事件，导致前端收不到审核信号
   - **后端修复**：`astream_events` 结束后调用 `graph.aget_state()` 检查 `state.next`，非空则发送 `interrupt` 事件
   - **前端修复**：`handleStep` 处理 `interrupt` 类型，设置 `awaitingReview=true`
   - **确认方案不执行**：`handleReviewAction` 原来只更新状态不发请求，改为直接调用 `streamResume`
   - 添加确认反馈：点击后立即显示"✅ 方案已确认，正在处理..."

3. **聊天记录持久化**
   - 消息和 sessionId 保存到 `localStorage`
   - 页面加载时自动恢复
   - 新增 🗑️ 清除对话按钮（右上角）

4. **编码问题修复**
   - `routes.py` 所有 `request.json()` 改为 `json.loads(raw.decode("utf-8", errors="replace"))`，解决中文编码导致的 `UnicodeDecodeError`
   - `supervisor.py` 中文引号 `""` 替换为英文引号 `""`，修复 `SyntaxError`

5. **后端 resume 流优化**
   - 添加 15 秒心跳超时，防止连接挂起
   - 前端 `streamResume` 过滤 heartbeat 事件

---

## 下午完成的修复

6. **评估仪表盘实时记录**
   - **问题**: 评估数据只在任务完全完成后才保存，中断或失败时数据丢失
   - **后端**: `routes.py` 每完成3个步骤自动保存指标（status=in_progress），异常时保存（status=failed）
   - **数据库**: `backend/evaluation/store.py` 添加 `status` 和 `updated_at` 字段，重建 `task_metrics` 表
   - **前端**: `EvalDashboard.tsx` 每10秒刷新，显示任务状态标签（已完成/进行中/失败）

7. **报告生成 Session 丢失修复**
   - **问题**: 后端 SessionManager 内存存储，重启后丢失；前端 localStorage 保存旧 sessionId
   - **ReportButton.tsx**: 添加 `onSessionExpired` 回调
   - **Chat.tsx**: 加载时验证 session 有效性，失败时清除旧 session 并提示重新规划

8. **指标收集重复记录修复**
   - **问题**: `stream_request` 和 `routes.py` 都调用 `start_task`/`finish_task`，导致指标冲突
   - **harness/travel_harness.py**: 移除 `stream_request` 中的 `start_task`/`finish_task`
   - **routes.py**: 统一由 routes.py 负责，添加 `collector.record_tool_call(task_id)`

---

## 晚间完成的修复

9. **切换页面进度丢失修复**
   - **问题**: 模型输出时切换页面再回来，进度丢失，只剩用户问题
   - **原因**: React 组件卸载时中断 SSE 连接
   - **方案**: 创建全局 StreamStore，独立于组件生命周期
   - **新增文件**:
     - `frontend/src/stores/streamStore.ts` — 全局 SSE 流式连接管理器
     - `frontend/src/hooks/useStream.ts` — 连接 store 的 React Hook
   - **Chat.tsx**: 重写为使用全局 store，组件卸载不影响连接

10. **无限更新循环修复**
    - **问题**: Maximum update depth exceeded 错误
    - **原因**: `useSyncExternalStore` 每次都返回新对象
    - **方案**: store 使用 `snapshot` 对象，只有状态实际变化时才创建新对象

11. **确认方案会话丢失修复**
    - **问题**: 点击"确认方案"后显示"会话已丢失"
    - **原因**: 组件挂载时检查 sessionId 有效性，`/api/sessions` 返回空列表导致误删
    - **方案**: 移除 sessionId 有效性检查，session 在内存中切换页面时仍有效

12. **报告生成失败处理优化**
    - **问题**: 报告生成失败时清除 sessionId，导致后续操作失败
    - **方案**: 失败时只提示用户重试，不清除 sessionId

---

## 关键文件

### 前端
- `frontend/src/stores/streamStore.ts` — 全局 SSE 流式连接管理器（新增）
- `frontend/src/hooks/useStream.ts` — React Hook 连接 store（新增）
- `frontend/src/pages/Chat.tsx` — 主聊天页面，使用全局 store
- `frontend/src/api/client.ts` — SSE 流式客户端，TaskMetrics 接口
- `frontend/src/pages/EvalDashboard.tsx` — 评估仪表盘，实时刷新
- `frontend/src/components/ReportButton.tsx` — 报告生成，session 过期处理

### 后端
- `backend/api/routes.py` — 后端路由，指标收集逻辑
- `backend/harness/travel_harness.py` — 流式请求，指标记录
- `backend/evaluation/store.py` — 评估数据存储，表结构
- `backend/evaluation/collector.py` — 指标收集器
- `backend/session/manager.py` — 会话管理器（内存存储）

### 核心逻辑
- `agents/supervisor.py` — parse_request_node、summarize_node 流式输出
- `harness/travel_harness.py` — interrupt 检测逻辑

---

## 当前已知问题
- 后端重启后 session 丢失（内存存储），需要持久化 session
- 报告生成可能因 session 不存在而失败

---

## 启动命令
```bash
# 后端
cd D:/桌面/练习/travel_planner && ./venv/Scripts/python.exe -m backend.main

# 前端
cd D:/桌面/练习/travel_planner/frontend && pnpm dev
```
