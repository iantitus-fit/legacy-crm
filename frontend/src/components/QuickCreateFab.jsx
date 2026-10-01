import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Plus, UserPlus, Calculator, CalendarPlus, CheckSquare, X } from 'lucide-react'
import QuickCreateLeadModal from './QuickCreateLeadModal'
import QuickCreateTaskModal from './QuickCreateTaskModal'
import JobPickerModal from './JobPickerModal'
import AppointmentModal from './AppointmentModal'
import { createEstimate } from '../api/estimates'
import { useToast } from '../context/ToastContext'

/**
 * Global floating action button with a quick-create menu. Mounted once
 * inside Layout so it's visible on every authed page. Clicking the FAB
 * opens a menu with 4 creation options; each option mounts its own modal.
 *
 * Flows:
 * - Lead        → QuickCreateLeadModal
 * - Estimate    → JobPickerModal → create estimate → navigate to it
 * - Appointment → AppointmentModal (existing reusable component)
 * - Task        → QuickCreateTaskModal
 */
export default function QuickCreateFab() {
  const navigate = useNavigate()
  const { addToast } = useToast()
  const [menuOpen, setMenuOpen] = useState(false)
  const [leadModal, setLeadModal] = useState(false)
  const [taskModal, setTaskModal] = useState(false)
  const [estimateJobPicker, setEstimateJobPicker] = useState(false)
  const [appointmentModal, setAppointmentModal] = useState(false)
  const menuRef = useRef(null)

  useEffect(() => {
    if (!menuOpen) return
    const handler = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setMenuOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [menuOpen])

  const openFromMenu = (opener) => {
    setMenuOpen(false)
    opener()
  }

  const handleEstimateJobPicked = async (jobId) => {
    setEstimateJobPicker(false)
    try {
      const est = await createEstimate({ job_id: jobId, name: '' })
      addToast('Estimate created')
      navigate(`/estimates/${est.id}`)
    } catch (err) {
      addToast(err?.response?.data?.detail || 'Failed to create estimate', 'error')
    }
  }

  const MENU_ITEMS = [
    { label: 'New Lead', icon: UserPlus, onClick: () => openFromMenu(() => setLeadModal(true)) },
    { label: 'New Estimate', icon: Calculator, onClick: () => openFromMenu(() => setEstimateJobPicker(true)) },
    { label: 'New Appointment', icon: CalendarPlus, onClick: () => openFromMenu(() => setAppointmentModal(true)) },
    { label: 'New Task', icon: CheckSquare, onClick: () => openFromMenu(() => setTaskModal(true)) },
  ]

  return (
    <>
      <div ref={menuRef} className="fixed bottom-6 right-6 z-40 flex flex-col items-end">
        {menuOpen && (
          <div className="mb-3 flex flex-col gap-2">
            {MENU_ITEMS.map(({ label, icon: Icon, onClick }) => (
              <button
                key={label}
                type="button"
                onClick={onClick}
                className="inline-flex items-center gap-2 px-3 py-2 bg-surface border border-th-border text-sm text-th-text rounded-full shadow-lg hover:bg-surface-hover transition-colors whitespace-nowrap"
              >
                <Icon size={16} className="text-brand-purple" />
                {label}
              </button>
            ))}
          </div>
        )}
        <button
          type="button"
          onClick={() => setMenuOpen((o) => !o)}
          className="w-14 h-14 rounded-full bg-btn-primary-bg hover:bg-btn-primary-hover text-btn-primary-text shadow-xl flex items-center justify-center transition-transform hover:scale-105"
          aria-label={menuOpen ? 'Close quick create menu' : 'Open quick create menu'}
          aria-expanded={menuOpen}
        >
          {menuOpen ? <X size={24} /> : <Plus size={24} />}
        </button>
      </div>

      {leadModal && (
        <QuickCreateLeadModal
          onClose={() => setLeadModal(false)}
          onCreated={() => navigate('/pipelines/leads')}
        />
      )}
      {taskModal && (
        <QuickCreateTaskModal
          onClose={() => setTaskModal(false)}
          onCreated={() => navigate('/tasks')}
        />
      )}
      {estimateJobPicker && (
        <JobPickerModal
          title="Select a Job for the New Estimate"
          onClose={() => setEstimateJobPicker(false)}
          onPick={handleEstimateJobPicked}
        />
      )}
      {appointmentModal && (
        <AppointmentModal
          isOpen={appointmentModal}
          onClose={() => setAppointmentModal(false)}
          onSaved={() => {
            setAppointmentModal(false)
            navigate('/calendars/appointments')
          }}
          appointment={null}
        />
      )}
    </>
  )
}
