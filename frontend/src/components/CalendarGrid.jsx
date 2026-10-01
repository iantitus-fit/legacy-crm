/** Calendar grid component with month and week views, dark-themed for Legacy CRM. */
import { useMemo, useCallback } from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import {
  format,
  startOfMonth,
  endOfMonth,
  startOfWeek,
  endOfWeek,
  eachDayOfInterval,
  isSameDay,
  isSameMonth,
  addMonths,
  subMonths,
  addWeeks,
  subWeeks,
  parseISO,
  differenceInCalendarDays,
} from 'date-fns'

const DAY_HEADERS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
const SPAN_ROW_HEIGHT = 22
const SPAN_GAP = 2

function getMonthDays(currentDate) {
  const monthStart = startOfMonth(currentDate)
  const monthEnd = endOfMonth(currentDate)
  const calendarStart = startOfWeek(monthStart)
  const calendarEnd = endOfWeek(monthEnd)
  return eachDayOfInterval({ start: calendarStart, end: calendarEnd })
}

function getWeekDays(currentDate) {
  const weekStart = startOfWeek(currentDate)
  const weekEnd = endOfWeek(currentDate)
  return eachDayOfInterval({ start: weekStart, end: weekEnd })
}

/**
 * For a given week row, finds multi-day events that overlap,
 * clamps them to week boundaries, and assigns visual slot rows.
 */
function allocateSpanSlots(weekDays, multiDayEvents) {
  const weekStart = weekDays[0]
  const weekEnd = weekDays[6]

  const spans = []

  for (const event of multiDayEvents) {
    const eventStart = parseISO(event.date)
    const eventEnd = parseISO(event.endDate)

    // Skip if event doesn't overlap this week
    if (eventEnd < weekStart || eventStart > weekEnd) continue

    // Clamp to week boundaries
    const clampedStart = eventStart < weekStart ? weekStart : eventStart
    const clampedEnd = eventEnd > weekEnd ? weekEnd : eventEnd

    const startCol = differenceInCalendarDays(clampedStart, weekStart)
    const endCol = differenceInCalendarDays(clampedEnd, weekStart)

    spans.push({
      event,
      startCol,
      endCol,
      isStart: isSameDay(clampedStart, eventStart),
      isEnd: isSameDay(clampedEnd, eventEnd),
      slot: 0,
    })
  }

  // Sort longest-first for greedy allocation
  spans.sort((a, b) => (b.endCol - b.startCol) - (a.endCol - a.startCol))

  // Greedy slot allocation
  const slotOccupancy = [] // array of Sets of occupied columns

  for (const span of spans) {
    let assignedSlot = -1
    for (let s = 0; s < slotOccupancy.length; s++) {
      let fits = true
      for (let c = span.startCol; c <= span.endCol; c++) {
        if (slotOccupancy[s].has(c)) {
          fits = false
          break
        }
      }
      if (fits) {
        assignedSlot = s
        break
      }
    }

    if (assignedSlot === -1) {
      assignedSlot = slotOccupancy.length
      slotOccupancy.push(new Set())
    }

    for (let c = span.startCol; c <= span.endCol; c++) {
      slotOccupancy[assignedSlot].add(c)
    }

    span.slot = assignedSlot
  }

  return { spans, slotCount: slotOccupancy.length }
}

function SpanningBar({ span, weekIndex, onEventClick }) {
  const { event, startCol, endCol, isStart, isEnd, slot } = span
  const color = event.color || '#F59E0B'

  const colSpan = endCol - startCol + 1
  const left = `${(startCol / 7) * 100}%`
  const width = `${(colSpan / 7) * 100}%`
  const top = slot * (SPAN_ROW_HEIGHT + SPAN_GAP)

  return (
    <button
      type="button"
      onClick={(e) => {
        e.stopPropagation()
        onEventClick(event)
      }}
      className="absolute text-left text-xs truncate transition-opacity hover:opacity-80"
      style={{
        top: `${top}px`,
        left,
        width,
        height: `${SPAN_ROW_HEIGHT}px`,
        backgroundColor: `${color}30`,
        borderLeft: isStart ? `3px solid ${color}` : 'none',
        borderRadius: `${isStart ? '4px' : '0'} ${isEnd ? '4px' : '0'} ${isEnd ? '4px' : '0'} ${isStart ? '4px' : '0'}`,
        color: '#e2e8f0',
        paddingLeft: isStart ? '6px' : '4px',
        paddingRight: '4px',
        lineHeight: `${SPAN_ROW_HEIGHT}px`,
        pointerEvents: 'auto',
      }}
      title={event.title}
    >
      {isStart && event.title}
    </button>
  )
}

function EventBlock({ event, onClick }) {
  const borderColor = event.color || '#F59E0B'

  return (
    <button
      type="button"
      onClick={(e) => {
        e.stopPropagation()
        onClick(event)
      }}
      className="w-full text-left rounded px-1.5 py-0.5 text-xs truncate mb-0.5 transition-opacity hover:opacity-80"
      style={{
        backgroundColor: `${borderColor}30`,
        borderLeft: `3px solid ${borderColor}`,
        color: '#e2e8f0',
      }}
      title={event.title}
    >
      {event.time && (
        <span className="font-mono text-[10px] opacity-70 mr-1">{event.time}</span>
      )}
      {event.title}
    </button>
  )
}

function DayCell({ day, currentDate, view, singleDayEvents, spanPadding, onEventClick, onDayClick }) {
  const today = new Date()
  const isToday = isSameDay(day, today)
  const isCurrentMonth = isSameMonth(day, currentDate)

  return (
    <div
      onClick={() => onDayClick && onDayClick(day)}
      className={`
        border border-th-border p-1 min-h-[100px] transition-colors
        ${view === 'week' ? 'min-h-[200px]' : ''}
        ${onDayClick ? 'cursor-pointer hover:bg-surface-hover/50' : ''}
        ${isCurrentMonth ? 'bg-surface' : 'bg-surface/40'}
      `}
    >
      <div className="flex items-center justify-end mb-1">
        <span
          className={`
            font-mono text-sm w-7 h-7 flex items-center justify-center rounded-full
            ${isToday ? 'ring-2 ring-amber-500 bg-amber-500/20 text-amber-500 font-semibold' : ''}
            ${!isToday && isCurrentMonth ? 'text-th-text' : ''}
            ${!isToday && !isCurrentMonth ? 'text-gray-600' : ''}
          `}
        >
          {format(day, 'd')}
        </span>
      </div>
      {spanPadding > 0 && <div style={{ height: `${spanPadding}px` }} />}
      <div className="space-y-0.5 overflow-hidden">
        {singleDayEvents.slice(0, view === 'week' ? 8 : 3).map((event) => (
          <EventBlock key={event.id} event={event} onClick={onEventClick} />
        ))}
        {singleDayEvents.length > (view === 'week' ? 8 : 3) && (
          <span className="text-[10px] text-gray-500 pl-1">
            +{singleDayEvents.length - (view === 'week' ? 8 : 3)} more
          </span>
        )}
      </div>
    </div>
  )
}

export default function CalendarGrid({
  currentDate,
  view = 'month',
  events = [],
  onEventClick,
  onDayClick,
  onNavigate,
  onViewChange,
}) {
  const days = useMemo(() => {
    return view === 'month' ? getMonthDays(currentDate) : getWeekDays(currentDate)
  }, [currentDate, view])

  // Classify events into multi-day and single-day
  const { multiDayEvents, singleDayEvents } = useMemo(() => {
    const multi = []
    const single = []
    for (const event of events) {
      if (event.endDate && event.endDate !== event.date) {
        multi.push(event)
      } else {
        single.push(event)
      }
    }
    return { multiDayEvents: multi, singleDayEvents: single }
  }, [events])

  // Chunk days into week rows (groups of 7)
  const weekRows = useMemo(() => {
    const rows = []
    for (let i = 0; i < days.length; i += 7) {
      rows.push(days.slice(i, i + 7))
    }
    return rows
  }, [days])

  // Compute spanning bar layout for each week row
  const weekSpanData = useMemo(() => {
    return weekRows.map((weekDays) => allocateSpanSlots(weekDays, multiDayEvents))
  }, [weekRows, multiDayEvents])

  // Map of day key -> single-day events for that day
  const singleEventsByDay = useMemo(() => {
    const map = new Map()
    days.forEach((day) => {
      const key = format(day, 'yyyy-MM-dd')
      const dayEvents = singleDayEvents.filter((event) => {
        const eventDate = parseISO(event.date)
        return isSameDay(day, eventDate)
      })
      map.set(key, dayEvents)
    })
    return map
  }, [days, singleDayEvents])

  const handlePrev = useCallback(() => {
    const newDate = view === 'month' ? subMonths(currentDate, 1) : subWeeks(currentDate, 1)
    onNavigate(newDate)
  }, [currentDate, view, onNavigate])

  const handleNext = useCallback(() => {
    const newDate = view === 'month' ? addMonths(currentDate, 1) : addWeeks(currentDate, 1)
    onNavigate(newDate)
  }, [currentDate, view, onNavigate])

  const handleToday = useCallback(() => {
    onNavigate(new Date())
  }, [onNavigate])

  const headerLabel =
    view === 'month'
      ? format(currentDate, 'MMMM yyyy')
      : `${format(startOfWeek(currentDate), 'MMM d')} – ${format(endOfWeek(currentDate), 'MMM d, yyyy')}`

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handlePrev}
            className="p-1.5 rounded-lg bg-surface-hover text-th-text hover:bg-th-border-secondary hover:text-th-text transition-colors"
          >
            <ChevronLeft className="w-5 h-5" />
          </button>
          <button
            type="button"
            onClick={handleNext}
            className="p-1.5 rounded-lg bg-surface-hover text-th-text hover:bg-th-border-secondary hover:text-th-text transition-colors"
          >
            <ChevronRight className="w-5 h-5" />
          </button>
          <button
            type="button"
            onClick={handleToday}
            className="px-3 py-1.5 rounded-lg bg-surface-hover text-th-text text-sm font-medium hover:bg-th-border-secondary hover:text-th-text transition-colors"
          >
            Today
          </button>
          <h2 className="text-xl font-semibold text-white ml-2">{headerLabel}</h2>
        </div>
        <div className="flex rounded-lg overflow-hidden border border-th-border">
          <button
            type="button"
            onClick={() => onViewChange('month')}
            className={`px-4 py-1.5 text-sm font-medium transition-colors ${
              view === 'month'
                ? 'bg-btn-primary-bg text-btn-primary-text'
                : 'bg-surface-hover text-th-text hover:bg-th-border-secondary hover:text-th-text'
            }`}
          >
            Month
          </button>
          <button
            type="button"
            onClick={() => onViewChange('week')}
            className={`px-4 py-1.5 text-sm font-medium transition-colors ${
              view === 'week'
                ? 'bg-btn-primary-bg text-btn-primary-text'
                : 'bg-surface-hover text-th-text hover:bg-th-border-secondary hover:text-th-text'
            }`}
          >
            Week
          </button>
        </div>
      </div>

      <div className="grid grid-cols-7 border-b border-th-border">
        {DAY_HEADERS.map((dayName, i) => (
          <div
            key={dayName}
            className="py-2 text-center text-xs font-semibold text-gray-400 uppercase tracking-wider"
          >
            {view === 'week' && days[i] ? (
              <div className="flex flex-col items-center gap-0.5">
                <span>{dayName}</span>
                <span
                  className={`font-mono text-sm ${
                    isSameDay(days[i], new Date())
                      ? 'text-amber-500 font-semibold'
                      : 'text-th-text'
                  }`}
                >
                  {format(days[i], 'd')}
                </span>
              </div>
            ) : (
              dayName
            )}
          </div>
        ))}
      </div>

      <div
        className="flex-1 grid"
        style={{ gridTemplateRows: `repeat(${weekRows.length}, 1fr)` }}
      >
        {weekRows.map((weekDays, weekIndex) => {
          const { spans, slotCount } = weekSpanData[weekIndex]
          const spanPadding = slotCount > 0 ? slotCount * (SPAN_ROW_HEIGHT + SPAN_GAP) : 0

          return (
            <div key={weekIndex} className="grid grid-cols-7 relative">
              {/* Spanning bar layer — positioned above day cells */}
              {slotCount > 0 && (
                <div
                  className="absolute inset-x-0 z-10"
                  style={{
                    top: '36px',
                    pointerEvents: 'none',
                  }}
                >
                  {spans.map((span) => (
                    <SpanningBar
                      key={`span-${span.event.id}-${weekIndex}`}
                      span={span}
                      weekIndex={weekIndex}
                      onEventClick={onEventClick}
                    />
                  ))}
                </div>
              )}

              {/* Day cells */}
              {weekDays.map((day) => {
                const key = format(day, 'yyyy-MM-dd')
                return (
                  <DayCell
                    key={key}
                    day={day}
                    currentDate={currentDate}
                    view={view}
                    singleDayEvents={singleEventsByDay.get(key) || []}
                    spanPadding={spanPadding}
                    onEventClick={onEventClick}
                    onDayClick={onDayClick}
                  />
                )
              })}
            </div>
          )
        })}
      </div>
    </div>
  )
}
