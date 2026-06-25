import { useI18n } from '../i18n/context'
import { Check, Loader2, Clock } from 'lucide-react'

const AGENT_NODES = [
  'route_planner',
  'weather_forecaster',
  'transport_advisor',
  'accommodation_manager',
  'food_advisor',
  'budget_optimizer',
]

interface Props {
  completed: string[]
  currentNode?: string
}

export default function AgentProgress({ completed, currentNode }: Props) {
  const { t } = useI18n()

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
      {AGENT_NODES.map((node) => {
        const isDone = completed.includes(node)
        const isActive = currentNode === node

        return (
          <div
            key={node}
            className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-all ${
              isDone
                ? 'bg-travel-600/20 text-travel-400 border border-travel-600/30'
                : isActive
                ? 'bg-ocean-600/20 text-ocean-400 border border-ocean-600/30 animate-pulse'
                : 'bg-gray-800/50 text-gray-500 border border-gray-800'
            }`}
          >
            {isDone ? (
              <Check size={16} className="text-travel-400" />
            ) : isActive ? (
              <Loader2 size={16} className="text-ocean-400 animate-spin" />
            ) : (
              <Clock size={16} />
            )}
            <span className="truncate">{t(`agents.${node}`)}</span>
          </div>
        )
      })}
    </div>
  )
}
