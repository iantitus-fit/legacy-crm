import { NavLink } from 'react-router-dom'
import {
  BarChart3,
  Briefcase,
  CalendarClock,
  CalendarDays,
  Calculator,
  CheckSquare,
  FileText,
  Kanban,
  LayoutDashboard,
  LogOut,
  List,
  MessageCircle,
  Moon,
  Package,
  Receipt,
  Settings,
  Sun,
  Upload,
  UserPlus,
  Users,
  Users2,
  X,
  Zap,
} from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { useTheme } from '../context/ThemeContext'

const navSections = [
  {
    label: null,
    items: [
      { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
    ],
  },
  {
    label: 'CLIENTS',
    items: [
      { to: '/contacts', label: 'Client Profiles', icon: Users },
      { to: '/leads', label: 'Leads', icon: UserPlus },
      { to: '/pipelines/leads', label: 'Lead Pipeline', icon: Kanban },
      { to: '/pipelines/sales', label: 'Sales Pipeline', icon: Kanban },
    ],
  },
  {
    label: 'JOBS',
    items: [
      { to: '/pipelines/jobs', label: 'Job Pipeline', icon: Kanban },
      { to: '/jobs', label: 'Jobs List', icon: List },
      { to: '/estimates', label: 'Estimates', icon: Calculator },
      { to: '/invoices', label: 'Invoices', icon: Receipt },
      { to: '/materials', label: 'Materials', icon: Package },
      { to: '/templates', label: 'Templates', icon: FileText },
    ],
  },
  {
    label: 'DAILY OPS',
    items: [
      { to: '/tasks', label: 'Tasks', icon: CheckSquare },
    ],
  },
  {
    label: 'CALENDARS',
    items: [
      { to: '/calendars/appointments', label: 'Appointments', icon: CalendarDays },
      { to: '/calendars/job-schedule', label: 'Job Schedule', icon: CalendarClock },
    ],
  },
  {
    label: 'REPORTS',
    items: [
      { to: '/reports/lead-sources', label: 'Lead Sources', icon: BarChart3 },
    ],
  },
  {
    label: 'MARKETING',
    items: [
      { to: '/automations', label: 'Automations', icon: Zap },
    ],
  },
]

export default function Sidebar({ onClose }) {
  const { user, logout } = useAuth()
  const { theme, toggleTheme } = useTheme()

  const handleNavClick = () => {
    onClose?.()
  }

  return (
    <aside className="w-64 bg-sidebar flex flex-col h-screen shrink-0 border-r border-sidebar-border">
      {/* Logo */}
      <div className="px-6 py-5 border-b border-sidebar-border flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-brand-purple tracking-tight">
            Legacy CRM
          </h1>
          <p className="text-xs text-th-text-muted mt-0.5">Roofing &amp; Exteriors</p>
        </div>
        {onClose && (
          <button
            onClick={onClose}
            className="lg:hidden p-1 text-th-text-muted hover:text-th-text transition-colors"
          >
            <X size={20} />
          </button>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        {navSections.map((section, sIdx) => (
          <div key={sIdx} className={section.label ? 'mt-4' : ''}>
            {section.label && (
              <p className="px-3 mb-2 text-[10px] font-semibold uppercase tracking-wider text-sidebar-text-section">
                {section.label}
              </p>
            )}
            {section.items.map(({ to, label, icon: Icon }) => (
              <NavLink
                key={to}
                to={to}
                onClick={handleNavClick}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors ${
                    isActive
                      ? 'bg-sidebar-hover text-sidebar-text-active'
                      : 'text-sidebar-text hover:text-sidebar-text-active hover:bg-sidebar-hover'
                  }`
                }
              >
                <Icon size={18} />
                {label}
              </NavLink>
            ))}
          </div>
        ))}

        {/* Settings link at bottom of nav */}
        <div className="mt-4">
          <p className="px-3 mb-2 text-[10px] font-semibold uppercase tracking-wider text-sidebar-text-section">
            SETTINGS
          </p>
          {[
            { to: '/settings/import', label: 'Import Contacts', icon: Upload },
            { to: '/settings/employees', label: 'Employees', icon: Users },
            { to: '/settings/crews', label: 'Crews', icon: Users2 },
            { to: '/settings/pipelines', label: 'Pipeline Settings', icon: Settings },
            { to: '/settings/sms', label: 'SMS Settings', icon: MessageCircle },
          ].map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              onClick={handleNavClick}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors ${
                  isActive
                    ? 'bg-sidebar-hover text-sidebar-text-active'
                    : 'text-sidebar-text hover:text-sidebar-text-active hover:bg-sidebar-hover'
                }`
              }
            >
              <Icon size={18} />
              {label}
            </NavLink>
          ))}
        </div>
      </nav>

      {/* User info + theme toggle + logout */}
      <div className="px-3 py-4 border-t border-sidebar-border">
        <div className="flex items-center justify-between px-3">
          <div className="min-w-0">
            <p className="text-sm font-medium text-th-text truncate">
              {user?.full_name}
            </p>
            <p className="text-xs text-th-text-muted capitalize">{user?.role}</p>
          </div>
          <div className="flex items-center gap-1">
            <button
              onClick={toggleTheme}
              className="p-2 text-th-text-muted hover:text-brand-purple transition-colors rounded-lg hover:bg-sidebar-hover"
              title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}
            >
              {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
            </button>
            <button
              onClick={logout}
              className="p-2 text-th-text-muted hover:text-red-400 transition-colors rounded-lg hover:bg-sidebar-hover"
              title="Log out"
            >
              <LogOut size={16} />
            </button>
          </div>
        </div>
      </div>
    </aside>
  )
}
