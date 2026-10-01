import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { CheckSquare, Circle, ExternalLink, Trash2 } from 'lucide-react'
import { deleteTask, listTasks, toggleTask } from '../api/tasks'
import { listEmployees } from '../api/employees'
import { useToast } from '../context/ToastContext'
import Pagination from '../components/Pagination'
import EmptyState from '../components/EmptyState'
import ConfirmDialog from '../components/ConfirmDialog'
import LoadingSpinner from '../components/LoadingSpinner'

function entityLink(task) {
  if (!task.related_entity_type || !task.related_entity_id) return null
  const routes = {
    contact: `/contacts/${task.related_entity_id}`,
    job: `/jobs/${task.related_entity_id}`,
    estimate: `/estimates/${task.related_entity_id}`,
  }
  return routes[task.related_entity_type] || null
}

export default function TasksPage() {
  const { addToast } = useToast()
  const [tasks, setTasks] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)
  const [statusFilter, setStatusFilter] = useState('')
  const [deleteId, setDeleteId] = useState(null)
  const [employees, setEmployees] = useState([])
  const [selectedEmployeeId, setSelectedEmployeeId] = useState(null)
  const perPage = 25

  useEffect(() => {
    listEmployees({ isActive: true, perPage: 100 })
      .then((data) => setEmployees(data.items))
      .catch(() => {})
  }, [])

  const fetchTasks = () => {
    setLoading(true)
    listTasks({
      status: statusFilter || undefined,
      assignedToUserId: selectedEmployeeId || undefined,
      page,
      perPage,
    })
      .then((data) => {
        setTasks(data.items)
        setTotal(data.total)
      })
      .catch(() => addToast('Failed to load tasks', 'error'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    fetchTasks()
  }, [statusFilter, selectedEmployeeId, page])

  const handleToggle = async (taskId) => {
    try {
      await toggleTask(taskId)
      fetchTasks()
    } catch {
      addToast('Failed to update task', 'error')
    }
  }

  const handleDelete = async () => {
    if (!deleteId) return
    try {
      await deleteTask(deleteId)
      setDeleteId(null)
      addToast('Task deleted')
      fetchTasks()
    } catch {
      addToast('Failed to delete task', 'error')
    }
  }

  const formatDate = (dateStr) => {
    if (!dateStr) return null
    return new Date(dateStr + 'T00:00:00').toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
    })
  }

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold text-th-text">Tasks</h1>
          <span className="text-xs px-2 py-1 rounded-full bg-surface text-th-text-secondary font-mono">
            {total}
          </span>
        </div>
      </div>

      {/* Employee Filter Chips */}
      {employees.length > 0 && (
        <div className="flex items-center gap-2 mb-4 flex-wrap">
          <button
            onClick={() => {
              setSelectedEmployeeId(null)
              setPage(1)
            }}
            className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
              selectedEmployeeId === null
                ? 'bg-btn-primary-bg text-btn-primary-text'
                : 'bg-surface text-th-text-secondary hover:text-th-text'
            }`}
          >
            All
          </button>
          {employees.map((emp) => (
            <button
              key={emp.id}
              onClick={() => {
                setSelectedEmployeeId(emp.id === selectedEmployeeId ? null : emp.id)
                setPage(1)
              }}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
                selectedEmployeeId === emp.id
                  ? 'bg-btn-primary-bg text-btn-primary-text'
                  : 'bg-surface text-th-text-secondary hover:text-th-text'
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

      {/* Status Filter */}
      <div className="flex items-center gap-3 mb-4">
        <select
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value)
            setPage(1)
          }}
          className="bg-surface border border-th-border rounded-lg px-3 py-2 text-sm text-th-text focus:outline-none focus:ring-2 focus:ring-brand-purple/50"
        >
          <option value="">All Tasks</option>
          <option value="open">Open</option>
          <option value="completed">Completed</option>
        </select>
      </div>

      {/* Loading */}
      {loading ? (
        <LoadingSpinner centered />
      ) : tasks.length === 0 ? (
        <EmptyState
          icon={CheckSquare}
          title="No tasks found"
          description={
            statusFilter || selectedEmployeeId
              ? 'Try changing the filter'
              : 'Tasks will appear here when added to jobs'
          }
        />
      ) : (
        <div className="bg-surface rounded-xl divide-y divide-th-border">
          {tasks.map((task) => (
            <div
              key={task.id}
              className={`flex items-center gap-4 px-4 py-3 group ${
                task.is_overdue ? 'border-l-2 border-red-500' : ''
              }`}
            >
              <button
                onClick={() => handleToggle(task.id)}
                className="shrink-0"
              >
                {task.status === 'completed' ? (
                  <CheckSquare size={18} className="text-emerald-500" />
                ) : (
                  <Circle size={18} className="text-th-text-muted hover:text-brand-purple transition-colors" />
                )}
              </button>

              <div className="flex-1 min-w-0">
                <span
                  className={`text-sm ${
                    task.status === 'completed'
                      ? 'line-through text-th-text-muted'
                      : 'text-th-text'
                  }`}
                >
                  {task.title}
                </span>

                <div className="flex items-center gap-3 mt-0.5">
                  {task.job_address && (
                    <Link
                      to={`/jobs/${task.job_id}`}
                      className="text-xs text-th-text-muted hover:text-brand-purple transition-colors truncate"
                    >
                      {task.job_address}
                    </Link>
                  )}

                  {entityLink(task) && task.related_entity_label && (
                    <Link
                      to={entityLink(task)}
                      className="flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300 transition-colors"
                    >
                      <ExternalLink size={10} />
                      {task.related_entity_label}
                    </Link>
                  )}
                </div>
              </div>

              {/* Assigned user */}
              {task.assigned_to_name && !selectedEmployeeId && (
                <span className="text-xs text-th-text-muted shrink-0">
                  {task.assigned_to_name.split(' ')[0]}
                </span>
              )}

              {task.due_date && (
                <span
                  className={`text-xs font-mono shrink-0 ${
                    task.is_overdue ? 'text-red-400' : 'text-th-text-muted'
                  }`}
                >
                  {formatDate(task.due_date)}
                </span>
              )}

              <button
                onClick={() => setDeleteId(task.id)}
                className="opacity-0 group-hover:opacity-100 text-th-text-muted hover:text-red-400 transition-all shrink-0"
              >
                <Trash2 size={14} />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Pagination */}
      {total > perPage && (
        <div className="mt-4">
          <Pagination
            page={page}
            perPage={perPage}
            total={total}
            onPageChange={setPage}
          />
        </div>
      )}

      <ConfirmDialog
        isOpen={deleteId !== null}
        onConfirm={handleDelete}
        onCancel={() => setDeleteId(null)}
        title="Delete Task"
        message="Are you sure you want to delete this task?"
        confirmLabel="Delete"
        variant="danger"
      />
    </div>
  )
}
