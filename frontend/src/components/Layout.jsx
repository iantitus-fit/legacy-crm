import { useState } from 'react'
import { Outlet } from 'react-router-dom'
import { Menu } from 'lucide-react'
import Sidebar from './Sidebar'
import QuickCreateFab from './QuickCreateFab'
import GlobalSearch from './GlobalSearch'
import AIPanelButton from './AIPanelButton'

export default function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(false)

  return (
    <div className="flex h-screen bg-page">
      {/* Desktop sidebar — always visible on lg+ */}
      <div className="hidden lg:block">
        <Sidebar />
      </div>

      {/* Mobile/tablet sidebar overlay */}
      {sidebarOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div
            className="absolute inset-0 bg-black/50"
            onClick={() => setSidebarOpen(false)}
          />
          <div className="relative z-50 h-full w-64">
            <Sidebar onClose={() => setSidebarOpen(false)} />
          </div>
        </div>
      )}

      {/* Main content */}
      <div className="flex-1 flex flex-col overflow-hidden bg-page-secondary">
        {/* Top bar with hamburger + search */}
        <div className="sticky top-0 z-30 bg-page-secondary px-4 md:px-6 py-3 flex items-center gap-3">
          <button
            onClick={() => setSidebarOpen(true)}
            className="lg:hidden p-2 text-th-text-secondary hover:text-th-text bg-surface rounded-lg transition-colors"
          >
            <Menu size={20} />
          </button>
          <div className="flex-1 max-w-xl">
            <GlobalSearch />
          </div>
          <AIPanelButton mode="global" variant="header" />
        </div>

        <main className="flex-1 overflow-y-auto px-4 md:px-6 pb-4 md:pb-6">
          <Outlet />
        </main>
      </div>

      <QuickCreateFab />
    </div>
  )
}
