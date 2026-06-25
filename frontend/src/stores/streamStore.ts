/**
 * 全局 SSE 流式连接管理器
 *
 * 独立于 React 组件生命周期，切换页面不会中断连接。
 */

import { streamPlan, streamResume, type AgentStep } from '../api/client'

export interface StreamState {
  isPlanning: boolean
  planContent: string
  completed: string[]
  currentNode: string
  awaitingReview: boolean
  sessionId: string | null
}

type Listener = (state: StreamState) => void

const STORAGE_KEY = 'travel_stream_state'

class StreamStore {
  private state: StreamState = {
    isPlanning: false,
    planContent: '',
    completed: [],
    currentNode: '',
    awaitingReview: false,
    sessionId: null,
  }

  // 快照对象，只有状态实际变化时才创建新对象
  private snapshot: StreamState = { ...this.state }
  private listeners: Set<Listener> = new Set()
  private controller: AbortController | null = null

  constructor() {
    // 从 localStorage 恢复状态
    this.restore()
  }

  private restore() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY)
      if (raw) {
        const saved = JSON.parse(raw)
        // 只恢复非 isPlanning 状态（连接已断开）
        this.state = {
          ...this.state,
          completed: saved.completed || [],
          currentNode: saved.currentNode || '',
          awaitingReview: saved.awaitingReview || false,
          sessionId: saved.sessionId || null,
          // planContent 保留，但 isPlanning 设为 false（因为连接已断开）
          planContent: saved.planContent || '',
          isPlanning: false,
        }
        this.snapshot = { ...this.state }
      }
    } catch {}
  }

  private save() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(this.state))
    } catch {}
  }

  private notify() {
    // 创建新的快照
    this.snapshot = { ...this.state }
    this.listeners.forEach((fn) => fn(this.snapshot))
  }

  subscribe(listener: Listener): () => void {
    this.listeners.add(listener)
    // 立即通知当前状态（使用快照）
    listener(this.snapshot)
    return () => this.listeners.delete(listener)
  }

  getState(): StreamState {
    return this.snapshot
  }

  /** 开始新的规划请求 */
  startPlan(
    query: string,
    sessionId: string | undefined,
    onStep: (step: AgentStep) => void,
    onDone: () => void,
    onError: (msg: string) => void,
  ) {
    this.cancel()

    this.state = {
      isPlanning: true,
      planContent: '',
      completed: [],
      currentNode: '',
      awaitingReview: false,
      sessionId: sessionId || null,
    }
    this.save()
    this.notify()

    this.controller = streamPlan(
      { query, session_id: sessionId },
      (step) => {
        this.handleStep(step)
        onStep(step)
      },
      () => {
        this.state.isPlanning = false
        this.save()
        this.notify()
        onDone()
      },
      (msg) => {
        this.state.isPlanning = false
        this.save()
        this.notify()
        onError(msg)
      },
    )
  }

  /** 恢复审核后的请求 */
  startResume(
    sessionId: string,
    response: string,
    onStep: (step: AgentStep) => void,
    onDone: () => void,
    onError: (msg: string) => void,
  ) {
    this.cancel()

    this.state.isPlanning = true
    this.state.awaitingReview = false
    this.save()
    this.notify()

    this.controller = streamResume(
      { session_id: sessionId, response },
      (step) => {
        this.handleStep(step)
        onStep(step)
      },
      () => {
        this.state.isPlanning = false
        this.save()
        this.notify()
        onDone()
      },
      (msg) => {
        this.state.isPlanning = false
        this.save()
        this.notify()
        onError(msg)
      },
    )
  }

  private handleStep(step: AgentStep) {
    const finalPlan =
      step.update?.final_plan?.content ||
      step.state?.final_plan?.content

    if (step.type === 'session' && (step as any).session_id) {
      console.log('[StreamStore] Received session_id:', (step as any).session_id)
      this.state.sessionId = (step as any).session_id
    }
    if (step.type === 'interrupt') {
      console.log('[StreamStore] Interrupt received, sessionId:', this.state.sessionId)
      this.state.awaitingReview = true
    }
    if (step.type === 'resume_complete') {
      this.state.awaitingReview = false
    }
    if (step.node) {
      this.state.currentNode = step.node
    }
    if (step.completed) {
      this.state.completed = step.completed
    }
    if (finalPlan) {
      this.state.planContent = finalPlan
    }
    if (step.message) {
      if (finalPlan && (step.type === 'node_complete' || step.type === 'interrupt')) {
        // 最终方案正文已经从 state/update 取到了，这类节点消息只作为进度，
        // 不再追加到用户要审阅的方案里。
      } else if (step.type === 'token') {
        this.state.planContent += step.message
      } else if (step.type === 'tool_call') {
        this.state.planContent += (this.state.planContent ? '\n' : '') + step.message
      } else if (step.type === 'node_start' || step.type === 'node_complete') {
        this.state.planContent += (this.state.planContent ? '\n\n' : '') + step.message
      }
    }
    this.save()
    this.notify()
  }

  /** 取消当前请求 */
  cancel() {
    if (this.controller) {
      this.controller.abort()
      this.controller = null
    }
  }

  /** 清除所有状态 */
  clear() {
    this.cancel()
    this.state = {
      isPlanning: false,
      planContent: '',
      completed: [],
      currentNode: '',
      awaitingReview: false,
      sessionId: null,
    }
    localStorage.removeItem(STORAGE_KEY)
    this.notify()
  }

  /** 设置会话 ID */
  setSessionId(id: string | null) {
    console.log('[StreamStore] setSessionId:', id)
    this.state.sessionId = id
    this.save()
    this.notify()
  }

  /** 完成规划（外部调用，如恢复后确认） */
  finishPlan(content?: string) {
    if (content) {
      this.state.planContent = content
    }
    this.state.isPlanning = false
    this.save()
    this.notify()
  }
}

// 单例
export const streamStore = new StreamStore()
