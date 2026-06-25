import { useState, useEffect } from 'react'
import { useI18n } from '../i18n/context'
import { fetchSkills, toggleSkill, type SkillMeta } from '../api/client'
import { Puzzle, Check, X } from 'lucide-react'

export default function SkillManager() {
  const { t } = useI18n()
  const [skills, setSkills] = useState<SkillMeta[]>([])

  useEffect(() => {
    fetchSkills().then(setSkills).catch(() => {})
  }, [])

  const handleToggle = async (name: string) => {
    const result = await toggleSkill(name)
    setSkills((prev) =>
      prev.map((s) => (s.name === name ? { ...s, enabled: result.enabled } : s)),
    )
  }

  return (
    <div className="p-6 overflow-y-auto h-full">
      <h2 className="text-2xl font-bold text-gray-100 mb-6">{t('skills.title')}</h2>

      <div className="space-y-3">
        {skills.map((skill) => (
          <div
            key={skill.name}
            className={`flex items-center justify-between p-4 rounded-xl border transition-colors ${
              skill.enabled
                ? 'bg-gray-900 border-gray-700'
                : 'bg-gray-900/50 border-gray-800 opacity-60'
            }`}
          >
            <div className="flex items-center gap-3">
              <Puzzle size={20} className={skill.enabled ? 'text-travel-400' : 'text-gray-600'} />
              <div>
                <h3 className="font-medium text-gray-100">{skill.name}</h3>
                <p className="text-sm text-gray-500">{skill.description}</p>
                <div className="flex gap-3 mt-1 text-xs text-gray-600">
                  <span>{t('skills.version')}: {skill.version}</span>
                  {skill.dependencies.length > 0 && (
                    <span>{t('skills.dependencies')}: {skill.dependencies.join(', ')}</span>
                  )}
                </div>
              </div>
            </div>
            <button
              onClick={() => handleToggle(skill.name)}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                skill.enabled
                  ? 'bg-travel-600/20 text-travel-400 hover:bg-travel-600/30'
                  : 'bg-gray-800 text-gray-500 hover:bg-gray-700'
              }`}
            >
              {skill.enabled ? (
                <span className="flex items-center gap-1"><Check size={14} /> {t('skills.enabled')}</span>
              ) : (
                <span className="flex items-center gap-1"><X size={14} /> {t('skills.disabled')}</span>
              )}
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}
