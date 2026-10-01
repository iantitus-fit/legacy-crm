import { useState, useEffect, useCallback } from 'react'
import { Plus } from 'lucide-react'
import {
  format,
  startOfMonth,
  endOfMonth,
  startOfWeek,
  endOfWeek,
} from 'date-fns'
import { listEmployees } from '../api/employees'
import { getCalendarAppointments } from '../api/calendar'
import CalendarGrid from '../components/CalendarGrid'
import CalendarEventPopover from '../components/CalendarEventPopover'
import AppointmentModal from '../components/AppointmentModal'
import LoadingSpinner from '../components/LoadingSpinner'

export default function AppointmentsPage() {
  const [employees, setEmployees] = useState([])
  const [selectedEmployeeId, setSelectedEmployeeId] = useState(null)
  const [currentDate, setCurrentDate] = useState(new Date())
  const [view, setView] = useState('month')
  const [events, setEvents] = useState([])
  const [loading, setLoading] = useState(true)
  const [popover, setPopover] = useState(null)
  const [showModal, setShowModal] = useState(false)

  // Fetch employees for filter chips
  useEffect(() => {
    listEmployees({ isActive: true, perPage: 100 })
      .then((data) => setEmployees(data.items || []))
      .catch(() => {})
  }, [])

  // Calculate date range based on view
  const getDateRange = useCallback(() => {
    if (view === 'month') {
      const monthStart = startOfMonth(currentDate)
      const monthEnd = endOfMonth(currentDate)
      return {
        startDate: format(startOfWeek(monthStart), 'yyyy-MM-dd'),
        endDate: format(endOfWeek(monthEnd), 'yyyy-MM-dd'),
      }
    }
    return {
      startDate: format(startOfWeek(currentDate), 'yyyy-MM-dd'),
      endDate: format(endOfWeek(currentDate), 'yyyy-MM-dd'),
    }
  }, [currentDate, view])

  // Fetch calendar appointments
  const fetchAppointments = useCallback(() => {
    setLoading(true)
    const { startDate, endDate } = getDateRange()
    getCalendarAppointments({
      startDate,
      endDate,
      assignedToUserId: selectedEmployeeId || undefined,
    })
      .then((data) => {
        const mapped = (data.items || []).map((appt) => ({
          id: appt.id,
          title: appt.title || 'Untitled Appointment',
          color: appt.assigned_to_color || '#6B7280',
          date: appt.appointment_date,
          time: appt.appointment_time,
          ...appt,
        }))
        setEvents(mapped)
      })
      .catch(() => setEvents([]))
      .finally(() => setLoading(false))
  }, [currentDate, view, selectedEmployeeId, getDateRange])

  useEffect(() => {
    fetchAppointments()
  }, [fetchAppointments])

  const handleEventClick = (event) => {
    setPopover({
      event,
      position: {
        top: window.innerHeight / 2 - 120,
        left: window.innerWidth / 2 - 144,
      },
    })
  }

  const closePopover = () => setPopover(null)

  const handleAppointmentSaved = () => {
    setShowModal(false)
    fetchAppointments()
  }

  return (
    <div className="relative">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-th-text">Appointments</h1>
        <button
          onClick={() => setShowModal(true)}
          className="flex items-center gap-2 px-4 py-2 bg-btn-primary-bg text-btn-primary-text rounded-lg font-medium text-sm hover:bg-btn-primary-hover transition-colors"
        >
          <Plus size={16} />
          Add Appointment
        </button>
      </div>

      {/* Employee Filter Chips */}
      {employees.length > 0 && (
        <div className="flex items-center gap-2 mb-4 flex-wrap">
          <button
            onClick={() => setSelectedEmployeeId(null)}
            className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ${
              selectedEmployeeId === null
                ? 'bg-badge-warning-bg text-brand-purple border-brand-purple/30'
                : 'bg-surface-hover text-th-text-secondary border-th-border-secondary hover:text-th-text'
            }`}
          >
            All
          </button>
          {employees.map((emp) => (
            <button
              key={emp.id}
              onClick={() =>
                setSelectedEmployeeId(
                  emp.id === selectedEmployeeId ? null : emp.id
                )
              }
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ${
                selectedEmployeeId === emp.id
                  ? 'bg-badge-warning-bg text-brand-purple border-brand-purple/30'
                  : 'bg-surface-hover text-th-text-secondary border-th-border-secondary hover:text-th-text'
              }`}
            >
              <div
                className="w-2 h-2 rounded-full shrink-0"
                style={{ backgroundColor: emp.color || '#6B7280' }}
              />
              {emp.full_name.split(' ')[0]}
            </button>
          ))}
        </div>
      )}

      {/* Calendar */}
      {loading ? (
        <LoadingSpinner centered />
      ) : (
        <CalendarGrid
          currentDate={currentDate}
          view={view}
          events={events}
          onEventClick={handleEventClick}
          onNavigate={setCurrentDate}
          onViewChange={setView}
        />
      )}

      {/* Event Popover */}
      {popover && (
        <CalendarEventPopover
          event={popover.event}
          position={popover.position}
          onClose={closePopover}
          variant="appointment"
        />
      )}

      {/* Appointment Modal */}
      {showModal && (
        <AppointmentModal
          onClose={() => setShowModal(false)}
          onSaved={handleAppointmentSaved}
        />
      )}
    </div>
  )
}
