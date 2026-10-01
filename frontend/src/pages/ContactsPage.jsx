import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Plus, Upload, Users, X } from 'lucide-react'
import { createContact, listContacts } from '../api/contacts'
import { useToast } from '../context/ToastContext'
import SearchInput from '../components/SearchInput'
import Pagination from '../components/Pagination'
import EmptyState from '../components/EmptyState'
import LoadingSpinner from '../components/LoadingSpinner'
import PhoneLink from '../components/PhoneLink'

const INITIAL_FORM = {
  name: '',
  company: '',
  email: '',
  phone: '',
  address: '',
  city: '',
  state: 'IN',
  zip: '',
}

export default function ContactsPage() {
  const [contacts, setContacts] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [showModal, setShowModal] = useState(false)
  const [form, setForm] = useState(INITIAL_FORM)
  const [formError, setFormError] = useState('')
  const [saving, setSaving] = useState(false)
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const { addToast } = useToast()
  const perPage = 25
  const importId = searchParams.get('import_id')

  const fetchContacts = () => {
    setLoading(true)
    listContacts({ search, page, perPage, importId })
      .then((data) => {
        setContacts(data.items)
        setTotal(data.total)
      })
      .catch(() => addToast('Failed to load contacts', 'error'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    fetchContacts()
  }, [search, page, importId])

  const handleSearch = (value) => {
    setSearch(value)
    setPage(1)
  }

  const handleCreate = async (e) => {
    e.preventDefault()
    setFormError('')
    if (!form.name.trim()) {
      setFormError('Name is required')
      return
    }
    setSaving(true)
    try {
      const contact = await createContact({
        ...form,
        email: form.email || undefined,
      })
      setShowModal(false)
      setForm(INITIAL_FORM)
      addToast('Contact created successfully')
      navigate(`/contacts/${contact.id}`)
    } catch (err) {
      setFormError(err.response?.data?.detail || 'Failed to create contact')
    } finally {
      setSaving(false)
    }
  }

  const openModal = () => {
    setForm(INITIAL_FORM)
    setFormError('')
    setShowModal(true)
  }

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-th-text">Client Profiles</h1>
        <div className="flex items-center gap-2">
          <button
            onClick={() => navigate('/settings/import')}
            className="flex items-center gap-2 bg-surface-hover hover:bg-surface-hover/70 text-th-text font-medium px-4 py-2 rounded-lg text-sm transition-colors"
          >
            <Upload size={16} />
            Import CSV
          </button>
          <button
            onClick={openModal}
            className="flex items-center gap-2 bg-btn-primary-bg hover:bg-btn-primary-hover text-btn-primary-text font-semibold px-4 py-2 rounded-lg text-sm transition-colors"
          >
            <Plus size={16} />
            Add Client
          </button>
        </div>
      </div>

      {importId && (
        <div className="flex items-center justify-between bg-brand-purple/10 text-brand-purple text-sm rounded-lg px-3 py-2 mb-4">
          <span>
            Showing contacts from a single import.
          </span>
          <button
            onClick={() => setSearchParams({})}
            className="text-xs underline hover:text-brand-purple-text"
          >
            Clear filter
          </button>
        </div>
      )}

      {/* Search */}
      <div className="mb-4 max-w-sm">
        <SearchInput
          value={search}
          onChange={handleSearch}
          placeholder="Search by name, email, phone, city..."
        />
      </div>

      {/* Table */}
      {loading ? (
        <LoadingSpinner centered />
      ) : contacts.length === 0 ? (
        <EmptyState
          icon={Users}
          title={search ? 'No contacts found' : 'No contacts yet'}
          description={
            search
              ? 'Try a different search term'
              : 'Add your first contact to get started'
          }
          action={
            !search && (
              <button
                onClick={openModal}
                className="text-brand-purple hover:text-brand-purple-text text-sm font-medium"
              >
                Add your first contact
              </button>
            )
          }
        />
      ) : (
        <>
          <div className="bg-surface rounded-xl overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-th-border">
                  <th className="text-left text-xs font-medium text-th-text-muted uppercase tracking-wider px-4 py-3">
                    Name
                  </th>
                  <th className="text-left text-xs font-medium text-th-text-muted uppercase tracking-wider px-4 py-3">
                    Email
                  </th>
                  <th className="text-left text-xs font-medium text-th-text-muted uppercase tracking-wider px-4 py-3">
                    Phone
                  </th>
                  <th className="text-left text-xs font-medium text-th-text-muted uppercase tracking-wider px-4 py-3">
                    City / State
                  </th>
                </tr>
              </thead>
              <tbody>
                {contacts.map((contact) => (
                  <tr
                    key={contact.id}
                    onClick={() => navigate(`/contacts/${contact.id}`)}
                    className="border-b border-th-border/50 last:border-0 hover:bg-surface-hover/50 cursor-pointer transition-colors"
                  >
                    <td className="px-4 py-3 text-sm font-medium text-th-text">
                      {contact.name}
                    </td>
                    <td className="px-4 py-3 text-sm text-th-text-secondary">
                      {contact.email || '—'}
                    </td>
                    <td className="px-4 py-3 text-sm text-th-text-secondary font-mono">
                      <PhoneLink phone={contact.phone} className="text-th-text-secondary" />
                    </td>
                    <td className="px-4 py-3 text-sm text-th-text-secondary">
                      {contact.city
                        ? `${contact.city}, ${contact.state || 'IN'}`
                        : contact.state || '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination
            page={page}
            perPage={perPage}
            total={total}
            onPageChange={setPage}
          />
        </>
      )}

      {/* Add Client Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div
            className="absolute inset-0 bg-black/50 backdrop-blur-sm"
            onClick={() => setShowModal(false)}
          />
          <div className="relative bg-surface rounded-xl p-6 w-full max-w-lg mx-4 shadow-2xl">
            <div className="flex items-center justify-between mb-5">
              <h2 className="text-lg font-semibold text-th-text">
                New Client
              </h2>
              <button
                onClick={() => setShowModal(false)}
                className="text-th-text-muted hover:text-th-text"
              >
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleCreate} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-th-text-secondary mb-1">
                  Name <span className="text-red-400">*</span>
                </label>
                <input
                  type="text"
                  value={form.name}
                  onChange={(e) =>
                    setForm({ ...form, name: e.target.value })
                  }
                  required
                  className="w-full bg-surface-hover border border-th-border-secondary rounded-lg px-4 py-2.5 text-th-text placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-brand-purple/50 focus:border-th-border-focus"
                  placeholder="John Smith"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-th-text-secondary mb-1">
                  Company
                </label>
                <input
                  type="text"
                  value={form.company}
                  onChange={(e) =>
                    setForm({ ...form, company: e.target.value })
                  }
                  className="w-full bg-surface-hover border border-th-border-secondary rounded-lg px-4 py-2.5 text-th-text placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-brand-purple/50 focus:border-th-border-focus"
                  placeholder="Acme Roofing"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-th-text-secondary mb-1">
                    Email
                  </label>
                  <input
                    type="email"
                    value={form.email}
                    onChange={(e) =>
                      setForm({ ...form, email: e.target.value })
                    }
                    className="w-full bg-surface-hover border border-th-border-secondary rounded-lg px-4 py-2.5 text-th-text placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-brand-purple/50 focus:border-th-border-focus"
                    placeholder="john@example.com"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-th-text-secondary mb-1">
                    Phone
                  </label>
                  <input
                    type="tel"
                    value={form.phone}
                    onChange={(e) =>
                      setForm({ ...form, phone: e.target.value })
                    }
                    className="w-full bg-surface-hover border border-th-border-secondary rounded-lg px-4 py-2.5 text-th-text placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-brand-purple/50 focus:border-th-border-focus"
                    placeholder="765-555-1234"
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-th-text-secondary mb-1">
                  Address
                </label>
                <input
                  type="text"
                  value={form.address}
                  onChange={(e) =>
                    setForm({ ...form, address: e.target.value })
                  }
                  className="w-full bg-surface-hover border border-th-border-secondary rounded-lg px-4 py-2.5 text-th-text placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-brand-purple/50 focus:border-th-border-focus"
                  placeholder="123 Main St"
                />
              </div>

              <div className="grid grid-cols-3 gap-4">
                <div>
                  <label className="block text-sm font-medium text-th-text-secondary mb-1">
                    City
                  </label>
                  <input
                    type="text"
                    value={form.city}
                    onChange={(e) =>
                      setForm({ ...form, city: e.target.value })
                    }
                    className="w-full bg-surface-hover border border-th-border-secondary rounded-lg px-4 py-2.5 text-th-text placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-brand-purple/50 focus:border-th-border-focus"
                    placeholder="Kokomo"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-th-text-secondary mb-1">
                    State
                  </label>
                  <input
                    type="text"
                    value={form.state}
                    onChange={(e) =>
                      setForm({ ...form, state: e.target.value })
                    }
                    maxLength={2}
                    className="w-full bg-surface-hover border border-th-border-secondary rounded-lg px-4 py-2.5 text-th-text placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-brand-purple/50 focus:border-th-border-focus"
                    placeholder="IN"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-th-text-secondary mb-1">
                    ZIP
                  </label>
                  <input
                    type="text"
                    value={form.zip}
                    onChange={(e) =>
                      setForm({ ...form, zip: e.target.value })
                    }
                    className="w-full bg-surface-hover border border-th-border-secondary rounded-lg px-4 py-2.5 text-th-text placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-brand-purple/50 focus:border-th-border-focus"
                    placeholder="46901"
                  />
                </div>
              </div>

              {formError && (
                <p className="text-red-400 text-sm">{formError}</p>
              )}

              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="px-4 py-2 text-sm text-th-text-secondary hover:text-th-text transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={saving}
                  className="bg-btn-primary-bg hover:bg-btn-primary-hover text-btn-primary-text font-semibold px-4 py-2 rounded-lg text-sm transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {saving ? 'Saving...' : 'Save Contact'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
