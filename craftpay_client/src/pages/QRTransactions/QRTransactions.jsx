import { useState, useEffect } from 'react'
import {
  QrCode, Search, RefreshCw, CheckCircle, XCircle, Clock,
  AlertCircle, ChevronLeft, ChevronRight, Filter
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { toast } from 'sonner'

const API_ROOT = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5000/api'

function getHeaders() {
  const token = localStorage.getItem('merchantToken')
  return { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` }
}

function formatCurrency(v) {
  return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', minimumFractionDigits: 2 }).format(v || 0)
}

function formatDate(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('en-IN', {
    day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit'
  })
}

const STATUS_CFG = {
  INITIATED:     { label: 'Initiated',      cls: 'bg-slate-100 text-slate-600',    icon: Clock },
  UTR_SUBMITTED: { label: 'UTR Submitted',  cls: 'bg-amber-100 text-amber-700',    icon: AlertCircle },
  SUCCESS:       { label: 'Success',        cls: 'bg-emerald-100 text-emerald-700', icon: CheckCircle },
  FAILED:        { label: 'Failed',         cls: 'bg-red-100 text-red-600',         icon: XCircle },
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

export default function QRTransactions() {
  const [transactions, setTransactions] = useState([])
  const [loading, setLoading] = useState(true)
  const [pagination, setPagination] = useState({ page: 1, per_page: 20, total: 0, total_pages: 1 })
  const [filters, setFilters] = useState({ status: '', from_date: '', to_date: '', search: '' })

  const load = async (page = 1) => {
    setLoading(true)
    try {
      const params = new URLSearchParams({ page, per_page: 20 })
      if (filters.status) params.set('status', filters.status)
      const res = await fetch(`${API_ROOT}/merchant/qr-transactions?${params}`, { headers: getHeaders() })
      const data = await res.json()
      if (data.success) {
        setTransactions(data.transactions || [])
        setPagination(data.pagination || { page: 1, total: 0, total_pages: 1 })
      } else {
        toast.error(data.message || 'Failed to load transactions')
      }
    } catch {
      toast.error('Failed to load QR transactions')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load(1) }, [])

  const stats = [
    { label: 'Total', value: pagination.total, color: 'purple' },
    { label: 'Awaiting Approval', value: transactions.filter(t => t.status === 'UTR_SUBMITTED').length, color: 'amber' },
    { label: 'Success', value: transactions.filter(t => t.status === 'SUCCESS').length, color: 'emerald' },
    { label: 'Initiated', value: transactions.filter(t => t.status === 'INITIATED').length, color: 'slate' },
  ]

  const colorMap = {
    purple: 'from-purple-50 to-purple-100 text-purple-700 border-purple-200',
    amber:  'from-amber-50 to-amber-100 text-amber-700 border-amber-200',
    emerald:'from-emerald-50 to-emerald-100 text-emerald-700 border-emerald-200',
    slate:  'from-slate-50 to-slate-100 text-slate-600 border-slate-200',
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
          <p className="text-slate-500 text-sm mt-1">All your QR payment collection transactions</p>
        </div>
        <Button onClick={() => load(1)} variant="outline" className="rounded-xl gap-2 border-purple-200 hover:bg-purple-50">
          <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
          Refresh
        </Button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        {stats.map(s => (
          <div key={s.label} className={`rounded-2xl border bg-gradient-to-br p-4 ${colorMap[s.color]}`}>
            <p className="text-xs font-semibold uppercase tracking-wide opacity-70">{s.label}</p>
            <p className="text-2xl font-bold mt-1">{s.value}</p>
          </div>
        ))}
      </div>

      {/* Filter Bar */}
      <div className="bg-white rounded-2xl border border-slate-100 shadow-sm p-4">
        <div className="flex flex-wrap gap-3">
          <select
            value={filters.status}
            onChange={e => setFilters(f => ({ ...f, status: e.target.value }))}
            className="px-3 py-2 rounded-xl border border-slate-200 text-sm focus:outline-none focus:border-purple-400 bg-white"
          >
            <option value="">All Statuses</option>
            <option value="INITIATED">Initiated</option>
            <option value="UTR_SUBMITTED">UTR Submitted</option>
            <option value="SUCCESS">Success</option>
            <option value="FAILED">Failed</option>
          </select>
          <Button onClick={() => load(1)} className="bg-gradient-to-r from-purple-600 to-blue-600 text-white rounded-xl px-5">
            <Filter size={14} className="mr-2" /> Filter
          </Button>
          <Button variant="outline" onClick={() => { setFilters({ status: '', from_date: '', to_date: '', search: '' }); setTimeout(() => load(1), 0) }} className="rounded-xl border-slate-200">
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
                {['TXN ID', 'Order ID', 'Customer', 'Amount', 'Net Amount', 'UTR', 'Status', 'Date', 'Completed'].map(h => (
                  <th key={h} className="py-3.5 px-4 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide whitespace-nowrap">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {loading ? (
                Array.from({ length: 5 }).map((_, i) => (
                  <tr key={i} className="border-b border-slate-50">
                    {Array.from({ length: 9 }).map((_, j) => (
                      <td key={j} className="py-3 px-4"><div className="h-4 bg-slate-100 rounded animate-pulse" /></td>
                    ))}
                  </tr>
                ))
              ) : transactions.length === 0 ? (
                <tr>
                  <td colSpan={9} className="py-16 text-center">
                    <div className="flex flex-col items-center gap-3">
                      <div className="w-16 h-16 rounded-2xl bg-purple-50 flex items-center justify-center">
                        <QrCode className="h-8 w-8 text-purple-300" />
                      </div>
                      <div>
                        <p className="font-semibold text-slate-600">No QR transactions found</p>
                        <p className="text-slate-400 text-xs mt-1">QR payments made via API will appear here</p>
                      </div>
                    </div>
                  </td>
                </tr>
              ) : (
                transactions.map(txn => (
                  <tr key={txn.txn_id} className="border-b border-slate-50 hover:bg-purple-50/20 transition-colors">
                    <td className="py-3 px-4">
                      <span className="font-mono text-xs text-purple-700 bg-purple-50 px-2 py-1 rounded-lg">{txn.txn_id}</span>
                    </td>
                    <td className="py-3 px-4">
                      <span className="font-mono text-xs text-slate-600">{txn.order_id}</span>
                    </td>
                    <td className="py-3 px-4">
                      <div>
                        <p className="text-slate-700 text-xs font-medium">{txn.customer_name || '—'}</p>
                        <p className="text-slate-400 text-xs">{txn.mobile || ''}</p>
                      </div>
                    </td>
                    <td className="py-3 px-4 font-bold text-slate-800">{formatCurrency(txn.amount)}</td>
                    <td className="py-3 px-4 font-semibold text-emerald-700">{formatCurrency(txn.net_amount)}</td>
                    <td className="py-3 px-4">
                      {txn.utr ? (
                        <span className="font-mono text-xs text-emerald-700 bg-emerald-50 px-2 py-1 rounded-lg">{txn.utr}</span>
                      ) : (
                        <span className="text-slate-300 text-xs italic">Not submitted</span>
                      )}
                    </td>
                    <td className="py-3 px-4"><StatusBadge status={txn.status} /></td>
                    <td className="py-3 px-4 text-xs text-slate-500 whitespace-nowrap">{formatDate(txn.created_at)}</td>
                    <td className="py-3 px-4 text-xs text-slate-500 whitespace-nowrap">{formatDate(txn.completed_at)}</td>
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
              Page {pagination.page} of {pagination.total_pages} · {pagination.total} total transactions
            </p>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" disabled={pagination.page <= 1 || loading} onClick={() => load(pagination.page - 1)} className="rounded-xl">
                <ChevronLeft size={14} />
              </Button>
              <Button variant="outline" size="sm" disabled={pagination.page >= pagination.total_pages || loading} onClick={() => load(pagination.page + 1)} className="rounded-xl">
                <ChevronRight size={14} />
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
