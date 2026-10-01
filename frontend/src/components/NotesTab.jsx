import { useCallback, useEffect, useState } from 'react'
import { MessageSquare, Pencil, Trash2 } from 'lucide-react'
import { createNote, deleteNote, listNotes, updateNote } from '../api/notes'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'

const NOTE_TYPES = [
  { key: 'company', label: 'Company Notes' },
  { key: 'client', label: 'Client Notes' },
  { key: 'crew', label: 'Crew Notes' },
]

function timeAgo(dateStr) {
  const now = new Date()
  const date = new Date(dateStr)
  const seconds = Math.floor((now - date) / 1000)
  if (seconds < 60) return 'just now'
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  if (days < 7) return `${days}d ago`
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

export default function NotesTab({ entityType, entityId }) {
  const { user } = useAuth()
  const { addToast } = useToast()
  const [activeNoteType, setActiveNoteType] = useState('company')
  const [notes, setNotes] = useState([])
  const [counts, setCounts] = useState({ company: 0, client: 0, crew: 0 })
  const [content, setContent] = useState('')
  const [loading, setLoading] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [editingId, setEditingId] = useState(null)
  const [editContent, setEditContent] = useState('')

  const fetchNotes = useCallback(async () => {
    setLoading(true)
    try {
      const data = await listNotes({
        entityType,
        entityId,
        noteType: activeNoteType,
      })
      setNotes(data.items)
    } catch {
      addToast('Failed to load notes', 'error')
    } finally {
      setLoading(false)
    }
  }, [entityType, entityId, activeNoteType, addToast])

  const fetchCounts = useCallback(async () => {
    try {
      const results = await Promise.all(
        NOTE_TYPES.map((t) =>
          listNotes({ entityType, entityId, noteType: t.key, perPage: 1 })
        )
      )
      const newCounts = {}
      NOTE_TYPES.forEach((t, i) => {
        newCounts[t.key] = results[i].total
      })
      setCounts(newCounts)
    } catch {
      // silently fail
    }
  }, [entityType, entityId])

  useEffect(() => {
    fetchNotes()
  }, [fetchNotes])

  useEffect(() => {
    fetchCounts()
  }, [fetchCounts])

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!content.trim()) return
    setSubmitting(true)
    try {
      await createNote({
        entity_type: entityType,
        entity_id: entityId,
        note_type: activeNoteType,
        content: content.trim(),
      })
      setContent('')
      addToast('Note added')
      fetchNotes()
      fetchCounts()
    } catch {
      addToast('Failed to add note', 'error')
    } finally {
      setSubmitting(false)
    }
  }

  const handleUpdate = async (noteId) => {
    if (!editContent.trim()) return
    try {
      await updateNote(noteId, { content: editContent.trim() })
      setEditingId(null)
      setEditContent('')
      addToast('Note updated')
      fetchNotes()
    } catch {
      addToast('Failed to update note', 'error')
    }
  }

  const handleDelete = async (noteId) => {
    try {
      await deleteNote(noteId)
      addToast('Note deleted')
      fetchNotes()
      fetchCounts()
    } catch {
      addToast('Failed to delete note', 'error')
    }
  }

  const startEdit = (note) => {
    setEditingId(note.id)
    setEditContent(note.content)
  }

  return (
    <div>
      {/* Sub-tab bar */}
      <div className="flex gap-2 mb-4">
        {NOTE_TYPES.map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setActiveNoteType(key)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              activeNoteType === key
                ? 'bg-badge-warning-bg text-brand-purple'
                : 'bg-surface-hover text-th-text-secondary hover:text-th-text'
            }`}
          >
            {label}
            {counts[key] > 0 && (
              <span
                className={`text-xs px-1.5 py-0.5 rounded-full ${
                  activeNoteType === key
                    ? 'bg-badge-warning-bg text-brand-purple-text'
                    : 'bg-th-border-secondary text-th-text-muted'
                }`}
              >
                {counts[key]}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Add note form */}
      <form onSubmit={handleSubmit} className="mb-6">
        <textarea
          value={content}
          onChange={(e) => setContent(e.target.value)}
          placeholder={`Add a ${activeNoteType} note...`}
          rows={3}
          className="w-full bg-surface-hover border border-th-border-secondary rounded-lg px-3 py-2 text-sm text-th-text placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-brand-purple/50 focus:border-th-border-focus resize-none"
        />
        <div className="flex justify-end mt-2">
          <button
            type="submit"
            disabled={submitting || !content.trim()}
            className="bg-btn-primary-bg hover:bg-btn-primary-hover text-btn-primary-text font-semibold px-4 py-1.5 rounded-lg text-sm transition-colors disabled:opacity-50"
          >
            {submitting ? 'Adding...' : 'Add Note'}
          </button>
        </div>
      </form>

      {/* Notes list */}
      {loading ? (
        <div className="text-center py-8">
          <p className="text-th-text-muted text-sm">Loading notes...</p>
        </div>
      ) : notes.length === 0 ? (
        <div className="flex flex-col items-center py-8 text-center">
          <MessageSquare size={24} className="text-th-text-muted mb-2" />
          <p className="text-th-text-muted text-sm">
            No {activeNoteType} notes yet
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {notes.map((note) => (
            <div
              key={note.id}
              className="bg-surface-hover/50 rounded-lg p-4 border border-th-border-secondary/50"
            >
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-th-text">
                    {note.created_by_name || 'Unknown'}
                  </span>
                  <span className="text-xs text-th-text-muted">
                    {note.created_at ? timeAgo(note.created_at) : ''}
                  </span>
                </div>
                {user && note.created_by_user_id === user.id && (
                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => startEdit(note)}
                      className="p-1 text-th-text-muted hover:text-th-text transition-colors"
                      title="Edit"
                    >
                      <Pencil size={14} />
                    </button>
                    <button
                      onClick={() => handleDelete(note.id)}
                      className="p-1 text-th-text-muted hover:text-red-400 transition-colors"
                      title="Delete"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                )}
              </div>
              {editingId === note.id ? (
                <div>
                  <textarea
                    value={editContent}
                    onChange={(e) => setEditContent(e.target.value)}
                    rows={3}
                    className="w-full bg-surface-hover border border-th-border-secondary rounded-lg px-3 py-2 text-sm text-th-text focus:outline-none focus:ring-2 focus:ring-brand-purple/50 focus:border-th-border-focus resize-none"
                  />
                  <div className="flex gap-2 mt-2">
                    <button
                      onClick={() => handleUpdate(note.id)}
                      className="bg-btn-primary-bg hover:bg-btn-primary-hover text-btn-primary-text font-semibold px-3 py-1 rounded text-sm transition-colors"
                    >
                      Save
                    </button>
                    <button
                      onClick={() => {
                        setEditingId(null)
                        setEditContent('')
                      }}
                      className="text-th-text-secondary hover:text-th-text px-3 py-1 text-sm transition-colors"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <p className="text-sm text-th-text whitespace-pre-wrap">
                  {note.content}
                </p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
