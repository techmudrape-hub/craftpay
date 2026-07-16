import { useState, useEffect } from 'react'
import {
  QrCode, Search, RefreshCw, CheckCircle, XCircle, Clock,
  Filter, Download, ChevronLeft, ChevronRight, AlertCircle,
  Eye, Check, X
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { toast } from 'sonner'

// ─── helpers ──────────────────────────────────────────────────────────────────
const BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5000/api'

function api(path, opts = {}) {
  const token = localStorage.getItem('qrAdminToken') || localStorage.getItem('adminToken')
  return fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}`, ...opts.headers },
    ...opts,
  }).then(r => r.json())
}

function formatCurrency(v) {
  return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', minimumFractionDigits: 2 }).format(v || 0)
}

function formatDate(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('en-IN', {
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit'
  })
}

// ─── Status Badge ─────────────────────────────────────────────────────────────
const STATUS_CFG = {
  INITIATED:      { label: 'Initiated',      cls: 'bg-slate-100 text-slate-600',    icon: Clock },
  UTR_SUBMITTED:  { label: 'UTR Submitted',  cls: 'bg-amber-100 text-amber-700',    icon: AlertCircle },
  SUCCESS:        { label: 'Success',        cls: 'bg-emerald-100 text-emerald-700', icon: CheckCircle },
  FAILED:         { label: 'Failed/Rejected', cls: 'bg-red-100 text-red-600',       icon: XCircle },
}

function StatusBadge({ status }) {
  const cfg = STATUS_CFG[status] || STATUS_CFG.INITIATED
  const Icon = cfg.icon
  return (
    <span className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold ${cfg.cls}`}>
      <Icon size={11} />
      {cfg.label}
    </span>
  )
}

// ─── Transaction Detail Modal ─────────────────────────────────────────────────
function DetailModal({ txn, onClose, onApprove, onReject }) {
  const [approving, setApproving] = useState(false)
  const [rejecting, setRejecting] = useState(false)

  if (!txn) return null

  const handleApprove = async () => {
    setApproving(true)
    const res = await api(`/qr/admin/approve/${txn.txn_id}`, { method: 'POST' })
    setApproving(false)
    if (res.success) { toast.success(res.message); onApprove() }
    else toast.error(res.message || 'Approve failed')
  }

  const handleReject = async () => {
    if (!confirm('Reject this transaction?')) return
    setRejecting(true)
    const res = await api(`/qr/admin/reject/${txn.txn_id}`, { method: 'POST' })
    setRejecting(false)
    if (res.success) { toast.success('Transaction rejected'); onReject() }
    else toast.error(res.message || 'Reject failed')
  }

  const rows = [
    ['Transaction ID', txn.txn_id],
    ['Order ID', txn.order_id],
    ['Merchant', `${txn.merchant_name || ''} (${txn.merchant_id})`],
    ['Customer', txn.customer_name || '—'],
    ['Mobile', txn.mobile || '—'],
    ['Email', txn.email || '—'],
    ['Amount', formatCurrency(txn.amount)],
    ['Charge', formatCurrency(txn.charge_amount)],
    ['Net Amount', formatCurrency(txn.net_amount)],
    ['UTR', txn.utr || '—'],
    ['Status', <StatusBadge key="s" status={txn.status} />],
    ['Created', formatDate(txn.created_at)],
    ['Completed', formatDate(txn.completed_at)],
  ]

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg">
        <div className="p-5 border-b border-slate-100 flex items-center justify-between">
          <h3 className="font-bold text-slate-900 flex items-center gap-2">
            <QrCode size={18} className="text-purple-600" />
            QR Transaction Detail
          </h3>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-100 p-1">
            <X size={18} />
          </button>
        </div>

        <div className="p-5 space-y-1 max-h-[60vh] overflow-y-auto">
          {rows.map(([label, value]) => (
            <div key={label} className="flex items-start justify-between py-2 border-b border-slate-50 last:border-0">
              <span className="text-xs text-slate-500 font-medium w-32 flex-shrink-0">{label}</span>
              <span className="text-sm text-slate-800 font-semibold text-right">{value}</span>
            </div>
          ))}
        </div>

        {['INITIATED', 'UTR_SUBMITTED'].includes(txn.status) && (
          <div className="p-5 border-t border-slate-100 flex gap-3">
            <Button
              onClick={handleReject}
              disabled={rejecting || approving}
              variant="outline"
              className="flex-1 border-red-200 text-red-600 hover:bg-red-50 rounded-xl"
            >
              {rejecting ? <RefreshCw size={14} className="animate-spin mr-2" /> : <XCircle size={14} className="mr-2" />}
              Reject
            </Button>
            <Button
              onClick={handleApprove}
              disabled={approving || rejecting || txn.status !== 'UTR_SUBMITTED'}
              className="flex-1 bg-gradient-to-r from-emerald-600 to-teal-600 text-white rounded-xl hover:from-emerald-700 hover:to-teal-700 disabled:opacity-50"
            >
              {approving ? <RefreshCw size={14} className="animate-spin mr-2" /> : <CheckCircle size={14} className="mr-2" />}
              {txn.status === 'UTR_SUBMITTED' ? 'Approve & Credit Wallet' : 'Awaiting UTR'}
            </Button>
          </div>
        )}
      </div>
    </div>
  )
}

// ─── Main Page ────────────────────────────────────────────────────────────────
export default function QRTransactions() {
  const [transactions, setTransactions] = useState([])
  const [loading, setLoading] = useState(true)
  const [pagination, setPagination] = useState({ page: 1, per_page: 20, total: 0, total_pages: 1 })
  const [filters, setFilters] = useState({ status: '', merchant_id: '', from_date: '', to_date: '', search: '' })
  const [selected, setSelected] = useState(null)

  const load = async (page = 1) => {
    setLoading(true)
    try {
      const params = new URLSearchParams({ page, per_page: 20, ...filters })
      Object.keys(filters).forEach(k => { if (!filters[k]) params.delete(k) })
      const res = await api(`/qr/admin/transactions?${params}`)
      if (res.success) {
        setTransactions(res.transactions || [])
        setPagination(res.pagination || { page: 1, total: 0, total_pages: 1 })
      } else {
        toast.error(res.message || 'Failed to load transactions')
      }
    } catch {
      toast.error('Failed to load transactions')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load(1) }, [])

  const handleSearch = () => load(1)
  const handleFilter = (key, val) => setFilters(prev => ({ ...prev, [key]: val }))

  const handleApprove = async (txn) => {
    const res = await api(`/qr/admin/approve/${txn.txn_id}`, { method: 'POST' })
    if (res.success) { toast.success(res.message); load(pagination.page) }
    else toast.error(res.message || 'Approve failed')
  }

  const handleReject = async (txn) => {
    if (!confirm(`Reject transaction ${txn.txn_id}?`)) return
    const res = await api(`/qr/admin/reject/${txn.txn_id}`, { method: 'POST' })
    if (res.success) { toast.success('Rejected'); load(pagination.page) }
    else toast.error(res.message || 'Reject failed')
  }

  // Stats
  const stats = [
    { label: 'Total', value: pagination.total, color: 'purple' },
    { label: 'UTR Submitted', value: transactions.filter(t => t.status === 'UTR_SUBMITTED').length, color: 'amber' },
    { label: 'Success', value: transactions.filter(t => t.status === 'SUCCESS').length, color: 'emerald' },
    { label: 'Failed', value: transactions.filter(t => t.status === 'FAILED').length, color: 'red' },
  ]

  const colorMap = {
    purple: 'bg-purple-50 text-purple-700 border-purple-100',
    amber:  'bg-amber-50 text-amber-700 border-amber-100',
    emerald:'bg-emerald-50 text-emerald-700 border-emerald-100',
    red:    'bg-red-50 text-red-700 border-red-100',
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-3">
            <div className="p-2.5 bg-gradient-to-br from-purple-600 to-blue-600 rounded-xl shadow-lg shadow-purple-500/30">
              <QrCode className="h-6 w-6 text-white" />
            </div>
            QR Transactions
          </h1>
          <p className="text-slate-500 text-sm mt-1">View and approve QR payment transactions</p>
        </div>
        <Button onClick={() => load(1)} variant="outline" className="rounded-xl gap-2 border-purple-200 hover:bg-purple-50">
          <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
          Refresh
        </Button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        {stats.map(s => (
          <div key={s.label} className={`rounded-2xl border p-4 ${colorMap[s.color]}`}>
            <p className="text-xs font-semibold uppercase tracking-wide opacity-70">{s.label}</p>
            <p className="text-2xl font-bold mt-1">{s.value}</p>
          </div>
        ))}
      </div>

      {/* Filters */}
      <div className="bg-white rounded-2xl border border-slate-100 shadow-sm p-5">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
          <div className="relative lg:col-span-2">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
            <Input
              placeholder="Search TXN ID, Order ID, UTR…"
              value={filters.search}
              onChange={e => handleFilter('search', e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleSearch()}
              className="pl-9 rounded-xl border-slate-200"
            />
          </div>

          <select
            value={filters.status}
            onChange={e => handleFilter('status', e.target.value)}
            className="px-3 py-2 rounded-xl border border-slate-200 text-sm focus:outline-none focus:border-purple-400 bg-white"
          >
            <option value="">All Statuses</option>
            <option value="INITIATED">Initiated</option>
            <option value="UTR_SUBMITTED">UTR Submitted</option>
            <option value="SUCCESS">Success</option>
            <option value="FAILED">Failed</option>
          </select>

          <Input
            type="date"
            value={filters.from_date}
            onChange={e => handleFilter('from_date', e.target.value)}
            className="rounded-xl border-slate-200 text-sm"
          />
          <Input
            type="date"
            value={filters.to_date}
            onChange={e => handleFilter('to_date', e.target.value)}
            className="rounded-xl border-slate-200 text-sm"
          />
        </div>
        <div className="flex gap-2 mt-3">
          <Button onClick={handleSearch} className="bg-gradient-to-r from-purple-600 to-blue-600 text-white rounded-xl px-6">
            <Filter size={14} className="mr-2" /> Apply Filters
          </Button>
          <Button
            variant="outline"
            onClick={() => { setFilters({ status: '', merchant_id: '', from_date: '', to_date: '', search: '' }); setTimeout(() => load(1), 0) }}
            className="rounded-xl border-slate-200"
          >
            Clear
          </Button>
        </div>
      </div>

      {/* Table */}
      <div className="bg-white rounded-2xl border border-slate-100 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gradient-to-r from-slate-50 to-purple-50/30 border-b border-slate-100">
                {['TXN ID', 'Order ID', 'Merchant', 'Customer', 'Amount', 'UTR', 'Status', 'Date', 'Actions'].map(h => (
                  <th key={h} className="py-3.5 px-4 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide whitespace-nowrap">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {loading ? (
                Array.from({ length: 6 }).map((_, i) => (
                  <tr key={i} className="border-b border-slate-50">
                    {Array.from({ length: 9 }).map((_, j) => (
                      <td key={j} className="py-3 px-4">
                        <div className="h-4 bg-slate-100 rounded animate-pulse" />
                      </td>
                    ))}
                  </tr>
                ))
              ) : transactions.length === 0 ? (
                <tr>
                  <td colSpan={9} className="py-16 text-center">
                    <QrCode className="h-12 w-12 mx-auto text-slate-200 mb-3" />
                    <p className="text-slate-400 font-medium">No QR transactions found</p>
                    <p className="text-slate-300 text-xs mt-1">Try adjusting your filters</p>
                  </td>
                </tr>
              ) : (
                transactions.map(txn => (
                  <tr key={txn.txn_id} className="border-b border-slate-50 hover:bg-slate-50/50 transition-colors group">
                    <td className="py-3 px-4">
                      <span className="font-mono text-xs text-purple-700 bg-purple-50 px-2 py-1 rounded-lg">{txn.txn_id}</span>
                    </td>
                    <td className="py-3 px-4">
                      <span className="font-mono text-xs text-slate-600">{txn.order_id}</span>
                    </td>
                    <td className="py-3 px-4">
                      <p className="font-semibold text-slate-800 text-xs">{txn.merchant_name || txn.merchant_id}</p>
                    </td>
                    <td className="py-3 px-4">
                      <div>
                        <p className="text-slate-700 text-xs font-medium">{txn.customer_name || '—'}</p>
                        <p className="text-slate-400 text-xs">{txn.mobile || ''}</p>
                      </div>
                    </td>
                    <td className="py-3 px-4">
                      <p className="font-bold text-slate-800">{formatCurrency(txn.amount)}</p>
                      <p className="text-xs text-slate-400">Net: {formatCurrency(txn.net_amount)}</p>
                    </td>
                    <td className="py-3 px-4">
                      {txn.utr ? (
                        <span className="font-mono text-xs text-emerald-700 bg-emerald-50 px-2 py-1 rounded-lg">{txn.utr}</span>
                      ) : (
                        <span className="text-slate-300 text-xs italic">Pending</span>
                      )}
                    </td>
                    <td className="py-3 px-4">
                      <StatusBadge status={txn.status} />
                    </td>
                    <td className="py-3 px-4">
                      <p className="text-xs text-slate-500 whitespace-nowrap">{formatDate(txn.created_at)}</p>
                    </td>
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-1">
                        {/* View Detail */}
                        <button
                          onClick={() => setSelected(txn)}
                          className="p-1.5 rounded-lg text-slate-400 hover:text-purple-600 hover:bg-purple-50 transition-colors"
                          title="View details"
                        >
                          <Eye size={14} />
                        </button>

                        {/* Approve (only when UTR submitted) */}
                        {txn.status === 'UTR_SUBMITTED' && (
                          <button
                            onClick={() => handleApprove(txn)}
                            className="p-1.5 rounded-lg text-slate-400 hover:text-emerald-600 hover:bg-emerald-50 transition-colors"
                            title="Approve & Credit Wallet"
                          >
                            <Check size={14} />
                          </button>
                        )}

                        {/* Reject */}
                        {['INITIATED', 'UTR_SUBMITTED'].includes(txn.status) && (
                          <button
                            onClick={() => handleReject(txn)}
                            className="p-1.5 rounded-lg text-slate-400 hover:text-red-600 hover:bg-red-50 transition-colors"
                            title="Reject"
                          >
                            <X size={14} />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {pagination.total_pages > 1 && (
          <div className="flex items-center justify-between px-5 py-4 border-t border-slate-100">
            <p className="text-xs text-slate-500">
              Page {pagination.page} of {pagination.total_pages} · {pagination.total} total
            </p>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={pagination.page <= 1 || loading}
                onClick={() => load(pagination.page - 1)}
                className="rounded-xl"
              >
                <ChevronLeft size={14} />
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={pagination.page >= pagination.total_pages || loading}
                onClick={() => load(pagination.page + 1)}
                className="rounded-xl"
              >
                <ChevronRight size={14} />
              </Button>
            </div>
          </div>
        )}
      </div>

      {/* Detail Modal */}
      {selected && (
        <DetailModal
          txn={selected}
          onClose={() => setSelected(null)}
          onApprove={() => { setSelected(null); load(pagination.page) }}
          onReject={() => { setSelected(null); load(pagination.page) }}
        />
      )}
    </div>
  )
}
