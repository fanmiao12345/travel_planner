import { Routes, Route, NavLink } from 'react-router-dom'
import { useI18n } from './i18n/context'
import Chat from './pages/Chat'
import EvalDashboard from './pages/EvalDashboard'
import SkillManager from './pages/SkillManager'
import ErrorBoundary from './components/ErrorBoundary'
import { Map, BarChart3, Puzzle } from 'lucide-react'

export default function App() {
  const { locale, toggleLocale, t } = useI18n()

  const navItems = [
    { path: '/', label: t('nav.chat'), icon: Map },
    { path: '/eval', label: t('nav.eval'), icon: BarChart3 },
    { path: '/skills', label: t('nav.skills'), icon: Puzzle },
  ]

  return (
    <ErrorBoundary>
      <div className="flex h-screen">
        {/* Sidebar */}
        <aside className="w-64 bg-gray-900 border-r border-gray-800 flex flex-col">
          <div className="p-4 border-b border-gray-800">
            <h1 className="text-xl font-bold bg-gradient-to-r from-travel-400 to-ocean-400 bg-clip-text text-transparent">
              ✈️ {t('app.title')}
            </h1>
            <p className="text-xs text-gray-500 mt-1">{t('app.subtitle')}</p>
          </div>
          <nav className="flex-1 p-3 space-y-1">
            {navItems.map((item) => (
              <NavLink
                key={item.path}
                to={item.path}
                end={item.path === '/'}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors ${
                    isActive
                      ? 'bg-travel-600/20 text-travel-400'
                      : 'text-gray-400 hover:bg-gray-800 hover:text-gray-200'
                  }`
                }
              >
                <item.icon size={18} />
                {item.label}
              </NavLink>
            ))}
          </nav>
          <div className="p-3 border-t border-gray-800">
            <button
              onClick={toggleLocale}
              className="w-full px-3 py-2 text-xs text-gray-500 hover:text-gray-300 hover:bg-gray-800 rounded-lg transition-colors"
            >
              🌐 {locale === 'zh' ? 'English' : '中文'}
            </button>
          </div>
        </aside>

        {/* Main content */}
        <main className="flex-1 overflow-hidden">
          <Routes>
            <Route path="/" element={<Chat />} />
            <Route path="/eval" element={<EvalDashboard />} />
            <Route path="/skills" element={<SkillManager />} />
          </Routes>
        </main>
      </div>
    </ErrorBoundary>
  )
}
