import { useState, useRef, useEffect } from 'react'
import { useI18n } from '../i18n/context'
import { type AgentStep, validateSession } from '../api/client'
import { useStream } from '../hooks/useStream'
import { streamStore } from '../stores/streamStore'
import AgentProgress from '../components/AgentProgress'
import ChatMessage from '../components/ChatMessage'
import ReportButton from '../components/ReportButton'
import RouteMap from '../components/RouteMap'
import { Send, Square, Trash2 } from 'lucide-react'

const STORAGE_KEY = 'travel_chat_messages'
const SESSION_KEY = 'travel_chat_session'

function loadMessages(): Message[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : []
  } catch { return [] }
}

interface Message {
  role: 'user' | 'assistant'
  content: string
}

export default function Chat() {
  const { t } = useI18n()

  // 从全局 store 读取流式状态
  const {
    isPlanning,
    planContent,
    completed,
    currentNode,
    awaitingReview,
    sessionId,
  } = useStream()

  const [messages, setMessages] = useState<Message[]>(loadMessages)
  const [input, setInput] = useState('')
  const [showReport, setShowReport] = useState(false)
  const [lastPlanContent, setLastPlanContent] = useState('') // 保存完成前的内容
  const pendingConfirmRef = useRef(false)
  const controllerRef = useRef<AbortController | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const scrollContainerRef = useRef<HTMLDivElement>(null)
  const isAtBottomRef = useRef(true)

  // 检测用户是否在底部
  const handleScroll = () => {
    const el = scrollContainerRef.current
    if (!el) return
    isAtBottomRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 100
  }

  // 自动滚动
  useEffect(() => {
    if (isAtBottomRef.current) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages, planContent])

  // 持久化聊天记录
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(messages))
      if (sessionId) localStorage.setItem(SESSION_KEY, sessionId)
      else localStorage.removeItem(SESSION_KEY)
    } catch {}
  }, [messages, sessionId])

  // 页面加载时验证 session 是否仍然有效（后端重启会导致内存 session 丢失）
  useEffect(() => {
    if (!sessionId) return
    validateSession(sessionId).then((result) => {
      if (!result.valid) {
        // 后端 session 已丢失，清除本地状态
        streamStore.clear()
        setMessages((prev) => [...prev, {
          role: 'assistant',
          content: '⚠️ 会话已过期（后端可能已重启）。请重新提交您的旅行需求。',
        }])
      }
    }).catch(() => {
      // 网络错误，不清除状态，让用户继续操作
    })
  }, []) // 只在组件挂载时执行一次

  const handleSend = () => {
    const text = input.trim()
    if (!text || isPlanning) return
    const activeSessionId = streamStore.getState().sessionId || sessionId
    setInput('')
    setMessages((prev) => [...prev, { role: 'user', content: text }])
    isAtBottomRef.current = true

    if (awaitingReview) {
      if (!activeSessionId) {
        setMessages((prev) => [...prev, { role: 'assistant', content: '❌ 会话已丢失，请重新提交出游需求。' }])
        return
      }
      streamStore.startResume(
        activeSessionId,
        text,
        handleStep,
        handleDone,
        handleError,
      )
    } else {
      streamStore.startPlan(
        text,
        sessionId ?? undefined,
        handleStep,
        handleDone,
        handleError,
      )
    }
  }

  const handleStep = (step: AgentStep) => {
    // 无需手动更新状态，store 会自动处理
  }

  const handleDone = () => {
    const latestState = streamStore.getState()
    const activeSessionId = latestState.sessionId || sessionId
    console.log('[Chat] handleDone called, sessionId:', activeSessionId)
    const content = latestState.planContent
    if (pendingConfirmRef.current) {
      pendingConfirmRef.current = false
      setMessages((prev) => [...prev, { role: 'assistant', content: '✅ 方案已确认。' }])
    } else if (content) {
      setMessages((prev) => [...prev, { role: 'assistant', content }])
    }
    // 清除 store 中的 planContent
    streamStore.finishPlan('')
    console.log('[Chat] After finishPlan, sessionId:', streamStore.getState().sessionId)
    if (activeSessionId) {
      setShowReport(true)
    }
  }

  const handleClear = () => {
    setMessages([])
    streamStore.clear()
    setShowReport(false)
  }

  const handleError = (msg: string) => {
    pendingConfirmRef.current = false
    if (msg === 'SESSION_EXPIRED') {
      // 后端 session 已丢失，清除本地状态
      streamStore.clear()
      setMessages((prev) => [...prev, {
        role: 'assistant',
        content: '⚠️ 会话已过期（后端可能已重启）。请重新提交您的旅行需求。',
      }])
    } else {
      setMessages((prev) => [...prev, { role: 'assistant', content: `❌ ${msg}` }])
    }
  }

  const handleReviewAction = (action: string) => {
    const activeSessionId = streamStore.getState().sessionId || sessionId
    console.log('[Chat] handleReviewAction:', action, 'sessionId:', activeSessionId)
    const userMsg = action === 'confirm' ? '确认方案' : '重新规划'
    setMessages((prev) => [...prev, { role: 'user', content: userMsg }])
    isAtBottomRef.current = true

    if (!activeSessionId) {
      console.error('[Chat] sessionId is null!')
      setMessages((prev) => [...prev, { role: 'assistant', content: '❌ 会话已丢失，请重新提交出游需求。' }])
      return
    }

    if (action === 'confirm') {
      pendingConfirmRef.current = true
      setShowReport(false)
      streamStore.startResume(
        activeSessionId,
        '确认方案',
        handleStep,
        handleDone,
        handleError,
      )
    } else {
      setShowReport(false)
      streamStore.startResume(
        activeSessionId,
        '重新规划',
        handleStep,
        handleDone,
        handleError,
      )
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="p-4 border-b border-gray-800 bg-gray-900/50 flex items-center justify-between">
        <AgentProgress completed={completed} currentNode={currentNode} />
        {messages.length > 0 && (
          <button
            onClick={handleClear}
            className="p-2 text-gray-500 hover:text-red-400 hover:bg-gray-800 rounded-lg transition-colors"
            title="清除对话"
          >
            <Trash2 size={16} />
          </button>
        )}
      </div>

      {/* Messages */}
      <div ref={scrollContainerRef} onScroll={handleScroll} className="flex-1 overflow-y-auto p-4">
        {messages.length === 0 && (
          <div className="flex items-center justify-center h-full">
            <p className="text-gray-500 text-lg">{t('chat.welcome')}</p>
          </div>
        )}
        {messages.map((msg, i) => (
          <ChatMessage key={i} role={msg.role} content={msg.content} />
        ))}
        {isPlanning && planContent && (
          <ChatMessage role="assistant" content={planContent + ' ⏳'} />
        )}
        {isPlanning && !planContent && (
          <div className="flex items-center gap-2 text-gray-400 px-4 py-2">
            <div className="flex gap-1">
              <span className="w-2 h-2 bg-travel-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
              <span className="w-2 h-2 bg-travel-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
              <span className="w-2 h-2 bg-travel-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
            </div>
            <span className="text-sm">正在思考...</span>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* 报告 & 地图 */}
      {showReport && !isPlanning && sessionId && (
        <div className="px-4 py-3 space-y-3 border-t border-gray-800">
          <ReportButton
            sessionId={sessionId}
            onClose={() => setShowReport(false)}
            onSessionExpired={() => {
              // 不清除 sessionId，只提示用户重试
              setMessages((prev) => [...prev, {
                role: 'assistant',
                content: '⚠️ 报告生成失败，请稍后重试。如果问题持续，请重新提交旅行需求。'
              }])
            }}
          />
          <RouteMap sessionId={sessionId} />
        </div>
      )}

      {/* Review buttons */}
      {awaitingReview && !isPlanning && (
        <div className="px-4 py-2 flex gap-2 border-t border-gray-800">
          <button
            onClick={() => handleReviewAction('confirm')}
            className="px-4 py-2 bg-travel-600 text-white rounded-lg hover:bg-travel-700 text-sm"
          >
            {t('chat.confirm')}
          </button>
          <button
            onClick={() => handleReviewAction('restart')}
            className="px-4 py-2 bg-gray-700 text-gray-300 rounded-lg hover:bg-gray-600 text-sm"
          >
            {t('chat.restart')}
          </button>
        </div>
      )}

      {/* Input */}
      <div className="p-4 border-t border-gray-800 bg-gray-900/50">
        <div className="flex gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
            placeholder={t('chat.placeholder')}
            className="flex-1 bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-gray-100 placeholder-gray-500 focus:outline-none focus:border-travel-500"
            disabled={isPlanning}
          />
          <button
            onClick={handleSend}
            disabled={isPlanning || !input.trim()}
            className="px-4 py-3 bg-travel-600 text-white rounded-xl hover:bg-travel-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isPlanning ? <Square size={20} /> : <Send size={20} />}
          </button>
        </div>
      </div>
    </div>
  )
}
