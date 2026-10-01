import { useState, useEffect, useCallback } from 'react'
import {
  format,
  startOfMonth,
  endOfMonth,
  startOfWeek,
  endOfWeek,
} from 'date-fns'
import { listCrews } from '../api/crews'
import { getCalendarJobs } from '../api/calendar'
import CalendarGrid from '../components/CalendarGrid'
import CalendarEventPopover from '../components/CalendarEventPopover'
import LoadingSpinner from '../components/LoadingSpinner'

export default function JobSchedulePage() {
  const [crews, setCrews] = useState([])
  const [selectedCrewId, setSelectedCrewId] = useState(null)
  const [currentDate, setCurrentDate] = useState(new Date())
  const [view, setView] = useState('month')
  const [events, setEvents] = useState([])
  const [loading, setLoading] = useState(true)
  const [popover, setPopover] = useState(null)

  // Fetch crews for filter chips
  useEffect(() => {
    listCrews({ isActive: true })
      .then((data) => setCrews(data.items || []))
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

  // Fetch calendar jobs
  useEffect(() => {
    setLoading(true)
    const { startDate, endDate } = getDateRange()
    getCalendarJobs({
      startDate,
      endDate,
      crewId: selectedCrewId || undefined,
    })
      .then((data) => {
        const mapped = (data.items || []).map((job) => ({
          id: job.id,
          title:
            job.display_name ||
            job.contact_name ||
            job.property_address ||
            `Job #${job.id}`,
          color: job.crew_color || '#6B7280',
          date: job.scheduled_date,
          endDate: job.scheduled_end_date,
          ...job,
        }))
        setEvents(mapped)
      })
      .catch(() => setEvents([]))
      .finally(() => setLoading(false))
  }, [currentDate, view, selectedCrewId, getDateRange])

  const handleEventClick = (event) => {
    // Position popover near center of viewport
    setPopover({
      event,
      position: {
        top: window.innerHeight / 2 - 120,
        left: window.innerWidth / 2 - 144,
      },
    })
  }

  const closePopover = () => setPopover(null)

  return (
    <div className="relative">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-th-text">Job Schedule</h1>
      </div>

      {/* Crew Filter Chips */}
      {crews.length > 0 && (
        <div className="flex items-center gap-2 mb-4 flex-wrap">
          <button
            onClick={() => setSelectedCrewId(null)}
            className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ${
              selectedCrewId === null
                ? 'bg-badge-warning-bg text-brand-purple border-brand-purple/30'
                : 'bg-surface-hover text-th-text-secondary border-th-border-secondary hover:text-th-text'
            }`}
          >
            All
          </button>
          {crews.map((crew) => (
            <button
              key={crew.id}
              onClick={() =>
                setSelectedCrewId(crew.id === selectedCrewId ? null : crew.id)
              }
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ${
                selectedCrewId === crew.id
                  ? 'bg-badge-warning-bg text-brand-purple border-brand-purple/30'
                  : 'bg-surface-hover text-th-text-secondary border-th-border-secondary hover:text-th-text'
              }`}
            >
              <div
                className="w-2 h-2 rounded-full shrink-0"
                style={{ backgroundColor: crew.color || '#6B7280' }}
              />
              {crew.name}
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
          variant="job"
        />
      )}
    </div>
  )
}
