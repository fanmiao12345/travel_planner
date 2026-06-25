import { useState } from 'react'
import { FileText, Download, X, RefreshCw } from 'lucide-react'
import { generateReport } from '../api/client'

interface Props {
  sessionId: string
  onClose: () => void
  onSessionExpired?: () => void
}

export default function ReportButton({ sessionId, onClose, onSessionExpired }: Props) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleGenerate = async () => {
    setLoading(true)
    setError('')
    try {
      const data = await generateReport(sessionId)
      if (data.error) {
        // 如果是 session 不存在的错误，通知父组件
        if (data.error.includes('未找到旅行计划数据') && onSessionExpired) {
          onSessionExpired()
        }
        setError(data.error)
        return
      }
      // 下载 Word 文档
      const binary = atob(data.content_base64)
      const bytes = new Uint8Array(binary.length)
      for (let i = 0; i < binary.length; i += 1) {
        bytes[i] = binary.charCodeAt(i)
      }
      const blob = new Blob([bytes], {
        type: data.mime_type || 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = data.filename || `旅行计划报告_${new Date().toISOString().slice(0, 10)}.docx`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
      onClose()
    } catch (e: any) {
      setError(e.message || '生成报告失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex items-center gap-3 p-4 bg-gray-800/50 border border-gray-700 rounded-xl">
      <FileText size={20} className="text-travel-400 shrink-0" />
      <span className="text-gray-300 text-sm">规划完成！是否生成旅行报告？</span>
      <div className="flex gap-2 ml-auto">
        <button
          onClick={handleGenerate}
          disabled={loading}
          className="flex items-center gap-1.5 px-4 py-2 bg-travel-600 text-white rounded-lg hover:bg-travel-700 disabled:opacity-50 text-sm"
        >
          <Download size={14} />
          {loading ? '生成中...' : '📄 生成报告'}
        </button>
        <button
          onClick={onClose}
          className="px-3 py-2 bg-gray-700 text-gray-300 rounded-lg hover:bg-gray-600 text-sm"
        >
          不用了
        </button>
      </div>
      {error && (
        <div className="flex items-center gap-2 ml-2">
          <span className="text-red-400 text-xs">{error}</span>
          {error.includes('未找到') && onSessionExpired && (
            <button
              onClick={onSessionExpired}
              className="text-travel-400 hover:text-travel-300 text-xs flex items-center gap-1"
            >
              <RefreshCw size={12} /> 重新规划
            </button>
          )}
        </div>
      )}
    </div>
  )
}
