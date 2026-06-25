/**
 * 类型化 API 客户端
 */

export interface TravelPlanRequest {
  query: string
  session_id?: string
}

export interface TravelResumeRequest {
  session_id: string
  response: string
}

export interface AgentStep {
  type: string          // node_start | node_complete | token | tool_call | heartbeat
  node?: string
  message?: string
  elapsed?: number
  completed?: string[]
  state?: any
  awaiting_review?: boolean
}

export interface SkillMeta {
  name: string
  description: string
  version: string
  enabled: boolean
  dependencies: string[]
}

export interface TaskMetrics {
  task_id: string
  accuracy: number
  total_latency_ms: number
  total_tokens: number
  tool_call_count: number
  tool_success_rate: number
  agent_count: number
  status?: 'completed' | 'in_progress' | 'failed'
  updated_at?: number
}

export async function submitPlan(request: TravelPlanRequest): Promise<any> {
  const resp = await fetch('/api/travel/plan', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  })
  return resp.json()
}

export function streamPlan(
  request: TravelPlanRequest,
  onStep: (step: AgentStep) => void,
  onDone: () => void,
  onError: (msg: string) => void,
): AbortController {
  const controller = new AbortController()

  ;(async () => {
    try {
      const resp = await fetch('/api/travel/plan/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
        signal: controller.signal,
      })

      const reader = resp.body?.getReader()
      if (!reader) return
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = JSON.parse(line.slice(6))
            if (data.type === '_done') {
              onDone()
              return
            }
            if (data.type === '_error') {
              onError(data.message)
              return
            }
            if (data.type === 'heartbeat') {
              continue // 心跳，忽略
            }
            if (data.type === 'session') {
              // session_id 事件，存储到 step 中
              onStep({ type: 'session', node: '', message: '', completed: [], ...data })
              continue
            }
            onStep(data)
          }
        }
      }
      onDone()
    } catch (e: any) {
      if (e.name !== 'AbortError') onError(e.message)
    }
  })()

  return controller
}

export function streamResume(
  request: TravelResumeRequest,
  onStep: (step: AgentStep) => void,
  onDone: () => void,
  onError: (msg: string) => void,
): AbortController {
  const controller = new AbortController()

  ;(async () => {
    try {
      const resp = await fetch('/api/travel/resume/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
        signal: controller.signal,
      })

      const reader = resp.body?.getReader()
      if (!reader) return
      const decoder = new TextDecoder()
      let buffer = ''
      let heartbeatCount = 0

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = JSON.parse(line.slice(6))
            if (data.type === '_done') { onDone(); return }
            if (data.type === '_error') { onError(data.message); return }
            if (data.type === 'heartbeat') {
              heartbeatCount += 1
              if (heartbeatCount >= 8) {
                onError('确认请求长时间没有完成，请刷新后重试')
                return
              }
              continue
            }
            heartbeatCount = 0
            onStep(data)
          }
        }
      }
      onDone()
    } catch (e: any) {
      if (e.name !== 'AbortError') onError(e.message)
    }
  })()

  return controller
}

export async function fetchSkills(): Promise<SkillMeta[]> {
  const resp = await fetch('/api/skills')
  return resp.json()
}

export async function toggleSkill(name: string): Promise<{ name: string; enabled: boolean }> {
  const resp = await fetch(`/api/skills/${name}/toggle`, { method: 'POST' })
  return resp.json()
}

export async function fetchMetrics(): Promise<TaskMetrics[]> {
  const resp = await fetch('/api/metrics')
  return resp.json()
}

export async function generateReport(sessionId: string): Promise<any> {
  const resp = await fetch('/api/travel/report', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId }),
  })
  return resp.json()
}

export async function fetchRouteData(sessionId: string): Promise<any> {
  const resp = await fetch('/api/travel/route-data', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId }),
  })
  return resp.json()
}
