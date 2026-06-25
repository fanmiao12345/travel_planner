import { useState, useEffect } from 'react'
import { useI18n } from '../i18n/context'
import { fetchMetrics, type TaskMetrics } from '../api/client'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'

const STATUS_LABELS: Record<string, { label: string; color: string }> = {
  completed: { label: '已完成', color: 'bg-green-500' },
  in_progress: { label: '进行中', color: 'bg-yellow-500' },
  failed: { label: '失败', color: 'bg-red-500' },
}

export default function EvalDashboard() {
  const { t } = useI18n()
  const [metrics, setMetrics] = useState<TaskMetrics[]>([])

  useEffect(() => {
    fetchMetrics().then(setMetrics).catch(() => {})
    // 每 10 秒刷新一次，以便看到进行中的任务
    const timer = setInterval(() => {
      fetchMetrics().then(setMetrics).catch(() => {})
    }, 10000)
    return () => clearInterval(timer)
  }, [])

  if (metrics.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4">
        <p className="text-gray-500 text-lg">{t('eval.noData')}</p>
        <p className="text-gray-600 text-sm">开始旅行规划后，评估数据将实时记录</p>
      </div>
    )
  }

  // 只用已完成的任务计算统计数据（status 为 completed 或 undefined 都算已完成，兼容旧数据）
  const completedMetrics = metrics.filter(m => !m.status || m.status === 'completed')
  const chartData = completedMetrics.slice(0, 20).map((m) => ({
    name: m.task_id.slice(0, 8),
    accuracy: m.accuracy,
    latency: m.total_latency_ms / 1000,
    tokens: m.total_tokens,
  }))

  return (
    <div className="p-6 space-y-6 overflow-y-auto h-full">
      <h2 className="text-2xl font-bold text-gray-100">{t('eval.title')}</h2>

      {/* Stats cards - 只统计已完成的任务 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard
          label={t('eval.accuracy')}
          value={completedMetrics.length > 0
            ? `${((completedMetrics.reduce((s, m) => s + m.accuracy, 0) / completedMetrics.length) * 100).toFixed(1)}%`
            : 'N/A'}
          color="text-travel-400"
        />
        <StatCard
          label={t('eval.latency')}
          value={completedMetrics.length > 0
            ? `${(completedMetrics.reduce((s, m) => s + m.total_latency_ms, 0) / completedMetrics.length / 1000).toFixed(1)}s`
            : 'N/A'}
          color="text-ocean-400"
        />
        <StatCard
          label={t('eval.tokens')}
          value={metrics.reduce((s, m) => s + m.total_tokens, 0).toLocaleString()}
          color="text-yellow-400"
        />
        <StatCard
          label={t('eval.toolSuccessRate')}
          value={completedMetrics.length > 0
            ? `${((completedMetrics.reduce((s, m) => s + m.tool_success_rate, 0) / completedMetrics.length) * 100).toFixed(1)}%`
            : 'N/A'}
          color="text-green-400"
        />
      </div>

      {/* Task list with status */}
      <div className="bg-gray-900 rounded-xl p-4 border border-gray-800">
        <h3 className="text-sm font-medium text-gray-400 mb-4">最近任务记录</h3>
        <div className="space-y-2 max-h-60 overflow-y-auto">
          {metrics.slice(0, 15).map((m) => {
            const status = STATUS_LABELS[m.status || 'completed']
            return (
              <div key={m.task_id} className="flex items-center justify-between p-2 bg-gray-800 rounded-lg">
                <div className="flex items-center gap-3">
                  <span className={`w-2 h-2 rounded-full ${status.color}`} />
                  <span className="text-sm text-gray-300 font-mono">{m.task_id}</span>
                </div>
                <div className="flex items-center gap-4 text-xs text-gray-500">
                  <span>{(m.total_latency_ms / 1000).toFixed(1)}s</span>
                  <span>{m.total_tokens.toLocaleString()} tokens</span>
                  <span className={`px-2 py-0.5 rounded ${
                    m.status === 'completed' ? 'bg-green-900 text-green-300' :
                    m.status === 'in_progress' ? 'bg-yellow-900 text-yellow-300' :
                    'bg-red-900 text-red-300'
                  }`}>
                    {status.label}
                  </span>
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* Accuracy chart */}
      <div className="bg-gray-900 rounded-xl p-4 border border-gray-800">
        <h3 className="text-sm font-medium text-gray-400 mb-4">{t('eval.accuracy')}</h3>
        <ResponsiveContainer width="100%" height={250}>
          <BarChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
            <XAxis dataKey="name" stroke="#6b7280" fontSize={12} />
            <YAxis stroke="#6b7280" fontSize={12} domain={[0, 1]} />
            <Tooltip
              contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #374151', borderRadius: '8px' }}
              labelStyle={{ color: '#9ca3af' }}
            />
            <Bar dataKey="accuracy" fill="#14b8a6" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Latency chart */}
      <div className="bg-gray-900 rounded-xl p-4 border border-gray-800">
        <h3 className="text-sm font-medium text-gray-400 mb-4">{t('eval.latency')} (s)</h3>
        <ResponsiveContainer width="100%" height={250}>
          <BarChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
            <XAxis dataKey="name" stroke="#6b7280" fontSize={12} />
            <YAxis stroke="#6b7280" fontSize={12} />
            <Tooltip
              contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #374151', borderRadius: '8px' }}
              labelStyle={{ color: '#9ca3af' }}
            />
            <Bar dataKey="latency" fill="#3b82f6" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

function StatCard({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div className="bg-gray-900 rounded-xl p-4 border border-gray-800">
      <p className="text-xs text-gray-500 mb-1">{label}</p>
      <p className={`text-2xl font-bold ${color}`}>{value}</p>
    </div>
  )
}
