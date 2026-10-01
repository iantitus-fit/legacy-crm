import { useEffect, useState } from 'react'
import { GripVertical, Plus, Trash2, X } from 'lucide-react'
import { listPipelines, getPipeline, addStage, updateStage, deleteStage, reorderStages } from '../api/pipeline'
import { useToast } from '../context/ToastContext'
import LoadingSpinner from '../components/LoadingSpinner'
import ConfirmDialog from '../components/ConfirmDialog'

export default function PipelineSettingsPage() {
  const { addToast } = useToast()
  const [pipelines, setPipelines] = useState([])
  const [activePipelineId, setActivePipelineId] = useState(null)
  const [stages, setStages] = useState([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  // Add stage modal
  const [showAdd, setShowAdd] = useState(false)
  const [newStageName, setNewStageName] = useState('')
  const [newStageColor, setNewStageColor] = useState('#6B7280')

  // Delete confirmation
  const [deleteTarget, setDeleteTarget] = useState(null)

  // Inline edit
  const [editingId, setEditingId] = useState(null)
  const [editName, setEditName] = useState('')
  const [editColor, setEditColor] = useState('')

  useEffect(() => {
    setLoading(true)
    listPipelines()
      .then((data) => {
        setPipelines(data.items)
        if (data.items.length > 0) {
          setActivePipelineId(data.items[0].id)
        }
      })
      .catch(() => addToast('Failed to load pipelines', 'error'))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (!activePipelineId) return
    setLoading(true)
    getPipeline(activePipelineId)
      .then((data) => {
        const sorted = [...data.stages].sort((a, b) => a.sort_order - b.sort_order)
        setStages(sorted)
      })
      .catch(() => addToast('Failed to load stages', 'error'))
      .finally(() => setLoading(false))
  }, [activePipelineId])

  const handleAddStage = async (e) => {
    e.preventDefault()
    if (!newStageName.trim()) return
    setSaving(true)
    try {
      await addStage(activePipelineId, {
        pipeline_id: activePipelineId,
        name: newStageName.trim(),
        sort_order: stages.length + 1,
        color: newStageColor,
      })
      // Refresh
      const data = await getPipeline(activePipelineId)
      setStages([...data.stages].sort((a, b) => a.sort_order - b.sort_order))
      setShowAdd(false)
      setNewStageName('')
      setNewStageColor('#6B7280')
      addToast('Stage added')
    } catch (err) {
      addToast(err.response?.data?.detail || 'Failed to add stage', 'error')
    } finally {
      setSaving(false)
    }
  }

  const handleDeleteStage = async () => {
    if (!deleteTarget) return
    try {
      await deleteStage(activePipelineId, deleteTarget.id)
      setStages((prev) => prev.filter((s) => s.id !== deleteTarget.id))
      addToast('Stage deleted')
    } catch (err) {
      addToast(err.response?.data?.detail || 'Failed to delete stage', 'error')
    } finally {
      setDeleteTarget(null)
    }
  }

  const startEdit = (stage) => {
    setEditingId(stage.id)
    setEditName(stage.name)
    setEditColor(stage.color || '#6B7280')
  }

  const saveEdit = async () => {
    if (!editingId) return
    setSaving(true)
    try {
      await updateStage(activePipelineId, editingId, {
        name: editName.trim(),
        color: editColor,
      })
      setStages((prev) =>
        prev.map((s) =>
          s.id === editingId
            ? { ...s, name: editName.trim(), color: editColor }
            : s
        )
      )
      setEditingId(null)
      addToast('Stage updated')
    } catch (err) {
      addToast(err.response?.data?.detail || 'Failed to update stage', 'error')
    } finally {
      setSaving(false)
    }
  }

  const moveStage = async (index, direction) => {
    const newStages = [...stages]
    const swapIdx = index + direction
    if (swapIdx < 0 || swapIdx >= newStages.length) return

    ;[newStages[index], newStages[swapIdx]] = [newStages[swapIdx], newStages[index]]

    const reordered = newStages.map((s, i) => ({ ...s, sort_order: i + 1 }))
    setStages(reordered)

    try {
      await reorderStages(
        activePipelineId,
        reordered.map((s) => ({ id: s.id, sort_order: s.sort_order }))
      )
    } catch {
      // Revert on error
      const data = await getPipeline(activePipelineId)
      setStages([...data.stages].sort((a, b) => a.sort_order - b.sort_order))
      addToast('Failed to reorder', 'error')
    }
  }

  if (loading && pipelines.length === 0) {
    return <LoadingSpinner centered />
  }

  return (
    <div>
      <h1 className="text-2xl font-bold text-th-text mb-6">
        Pipeline Settings
      </h1>

      {/* Pipeline tabs */}
      <div className="flex gap-2 mb-6">
        {pipelines.map((p) => (
          <button
            key={p.id}
            onClick={() => setActivePipelineId(p.id)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              activePipelineId === p.id
                ? 'bg-btn-primary-bg text-btn-primary-text'
                : 'bg-surface text-th-text-secondary hover:text-th-text hover:bg-surface-hover'
            }`}
          >
            {p.name}
          </button>
        ))}
      </div>

      {/* Stages list */}
      <div className="bg-surface rounded-xl p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-medium text-th-text-secondary uppercase tracking-wider">
            Stages
          </h2>
          <button
            onClick={() => setShowAdd(true)}
            className="flex items-center gap-1.5 text-sm text-brand-purple hover:text-brand-purple-text transition-colors"
          >
            <Plus size={14} />
            Add Stage
          </button>
        </div>

        {loading ? (
          <LoadingSpinner />
        ) : stages.length === 0 ? (
          <p className="text-th-text-muted text-sm py-4 text-center">
            No stages in this pipeline
          </p>
        ) : (
          <div className="space-y-1">
            {stages.map((stage, index) => (
              <div
                key={stage.id}
                className="flex items-center gap-3 p-3 rounded-lg hover:bg-surface-hover/50 group"
              >
                {/* Drag handle / reorder buttons */}
                <div className="flex flex-col gap-0.5 shrink-0">
                  <button
                    onClick={() => moveStage(index, -1)}
                    disabled={index === 0}
                    className="text-th-text-muted hover:text-th-text disabled:opacity-30 disabled:cursor-not-allowed text-[10px]"
                  >
                    ▲
                  </button>
                  <button
                    onClick={() => moveStage(index, 1)}
                    disabled={index === stages.length - 1}
                    className="text-th-text-muted hover:text-th-text disabled:opacity-30 disabled:cursor-not-allowed text-[10px]"
                  >
                    ▼
                  </button>
                </div>

                {/* Color swatch */}
                {editingId === stage.id ? (
                  <input
                    type="color"
                    value={editColor}
                    onChange={(e) => setEditColor(e.target.value)}
                    className="w-6 h-6 rounded cursor-pointer border-0 bg-transparent"
                  />
                ) : (
                  <div
                    className="w-4 h-4 rounded-full shrink-0 cursor-pointer"
                    style={{ backgroundColor: stage.color || '#6B7280' }}
                    onClick={() => startEdit(stage)}
                  />
                )}

                {/* Name */}
                {editingId === stage.id ? (
                  <input
                    type="text"
                    value={editName}
                    onChange={(e) => setEditName(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && saveEdit()}
                    className="flex-1 bg-surface-hover border border-th-border-secondary rounded px-2 py-1 text-sm text-th-text focus:outline-none focus:ring-2 focus:ring-brand-purple/50"
                    autoFocus
                  />
                ) : (
                  <span
                    className="flex-1 text-sm text-th-text cursor-pointer"
                    onClick={() => startEdit(stage)}
                  >
                    {stage.name}
                  </span>
                )}

                {/* Sort order */}
                <span className="text-xs text-th-text-muted font-mono shrink-0">
                  #{stage.sort_order}
                </span>

                {/* Actions */}
                {editingId === stage.id ? (
                  <div className="flex items-center gap-1">
                    <button
                      onClick={saveEdit}
                      disabled={saving}
                      className="text-xs text-brand-purple hover:text-brand-purple-text px-2 py-1"
                    >
                      Save
                    </button>
                    <button
                      onClick={() => setEditingId(null)}
                      className="text-xs text-th-text-muted hover:text-th-text px-2 py-1"
                    >
                      Cancel
                    </button>
                  </div>
                ) : (
                  <button
                    onClick={() => setDeleteTarget(stage)}
                    className="text-th-text-muted hover:text-red-400 opacity-0 group-hover:opacity-100 transition-all"
                  >
                    <Trash2 size={14} />
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Add Stage Modal */}
      {showAdd && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div
            className="absolute inset-0 bg-black/50 backdrop-blur-sm"
            onClick={() => setShowAdd(false)}
          />
          <div className="relative bg-surface rounded-xl p-6 w-full max-w-sm mx-4 shadow-2xl">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-th-text">Add Stage</h2>
              <button
                onClick={() => setShowAdd(false)}
                className="text-th-text-muted hover:text-th-text"
              >
                <X size={20} />
              </button>
            </div>
            <form onSubmit={handleAddStage} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-th-text-secondary mb-1">
                  Name
                </label>
                <input
                  type="text"
                  value={newStageName}
                  onChange={(e) => setNewStageName(e.target.value)}
                  required
                  className="w-full bg-surface-hover border border-th-border-secondary rounded-lg px-4 py-2.5 text-th-text placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-brand-purple/50"
                  placeholder="Stage name"
                  autoFocus
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-th-text-secondary mb-1">
                  Color
                </label>
                <div className="flex items-center gap-3">
                  <input
                    type="color"
                    value={newStageColor}
                    onChange={(e) => setNewStageColor(e.target.value)}
                    className="w-10 h-10 rounded cursor-pointer border-0 bg-transparent"
                  />
                  <span className="text-sm text-th-text-secondary font-mono">
                    {newStageColor}
                  </span>
                </div>
              </div>
              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowAdd(false)}
                  className="px-4 py-2 text-sm text-th-text-secondary hover:text-th-text transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={saving}
                  className="bg-btn-primary-bg hover:bg-btn-primary-hover text-btn-primary-text font-semibold px-4 py-2 rounded-lg text-sm transition-colors disabled:opacity-50"
                >
                  {saving ? 'Adding...' : 'Add Stage'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delete Confirmation */}
      <ConfirmDialog
        isOpen={!!deleteTarget}
        onConfirm={handleDeleteStage}
        onCancel={() => setDeleteTarget(null)}
        title="Delete Stage"
        message={`Are you sure you want to delete "${deleteTarget?.name}"? This cannot be undone. Stages with jobs cannot be deleted.`}
        confirmLabel="Delete"
        variant="danger"
      />
    </div>
  )
}
