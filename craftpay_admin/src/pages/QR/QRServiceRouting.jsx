import { useState, useEffect, useRef } from 'react'
import { Upload, QrCode, Trash2, Plus, Check, X, ChevronDown, AlertCircle, RefreshCw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { toast } from 'sonner'
import adminAPI from '@/api/admin_api'

// ─── helpers ──────────────────────────────────────────────────────────────────
const BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5000/api'

function api(path, opts = {}) {
  const token = localStorage.getItem('qrAdminToken') || localStorage.getItem('adminToken')
  return fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}`, ...opts.headers },
    ...opts,
  }).then(r => r.json())
}

function apiForm(path, formData) {
  const token = localStorage.getItem('qrAdminToken') || localStorage.getItem('adminToken')
  return fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: formData,
  }).then(r => r.json())
}

function apiDelete(path) {
  const token = localStorage.getItem('qrAdminToken') || localStorage.getItem('adminToken')
  return fetch(`${BASE}${path}`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${token}` },
  }).then(r => r.json())
}

// ─── Status Badge ─────────────────────────────────────────────────────────────
const EnabledBadge = ({ enabled }) => (
  <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold ${
    enabled ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-500'
  }`}>
    <span className={`w-1.5 h-1.5 rounded-full ${enabled ? 'bg-emerald-500' : 'bg-slate-400'}`} />
    {enabled ? 'Enabled' : 'Disabled'}
  </span>
)

// ─── QR Code Card ─────────────────────────────────────────────────────────────
function QRCodeCard({ qr, onDelete }) {
  const [deleting, setDeleting] = useState(false)

  const handleDelete = async () => {
    if (!confirm(`Delete QR code "${qr.name}"? This will remove routing for all merchants using it.`)) return
    setDeleting(true)
    try {
      const res = await apiDelete(`/qr/admin/qr-codes/${qr.id}`)
      if (res.success) { toast.success('QR code deleted'); onDelete(qr.id) }
      else toast.error(res.message || 'Delete failed')
    } catch { toast.error('Delete failed') }
    finally { setDeleting(false) }
  }

  return (
    <div className="relative group bg-white rounded-2xl border border-slate-100 shadow-sm hover:shadow-md transition-all duration-200 overflow-hidden">
      <div className="aspect-square bg-gradient-to-br from-slate-50 to-purple-50 flex items-center justify-center p-4">
        {qr.qr_image_url ? (
          <img src={qr.qr_image_url} alt={qr.name} className="w-full h-full object-contain rounded-lg" />
        ) : (
          <QrCode className="w-16 h-16 text-slate-300" />
        )}
      </div>
      <div className="p-3">
        <p className="font-semibold text-slate-800 text-sm truncate" title={qr.name}>{qr.name}</p>
        <p className="text-xs text-slate-400 mt-0.5">{new Date(qr.created_at).toLocaleDateString('en-IN')}</p>
      </div>
      {/* Delete overlay */}
      <button
        onClick={handleDelete}
        disabled={deleting}
        className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity bg-red-500 text-white rounded-lg p-1.5 hover:bg-red-600 shadow-lg"
        title="Delete QR"
      >
        {deleting ? <RefreshCw size={12} className="animate-spin" /> : <Trash2 size={12} />}
      </button>
    </div>
  )
}

// ─── Upload QR Form ───────────────────────────────────────────────────────────
function UploadQRForm({ onUploaded }) {
  const [name, setName] = useState('')
  const [file, setFile] = useState(null)
  const [preview, setPreview] = useState(null)
  const [uploading, setUploading] = useState(false)
  const fileRef = useRef()

  const handleFile = (f) => {
    if (!f) return
    setFile(f)
    const reader = new FileReader()
    reader.onload = (e) => setPreview(e.target.result)
    reader.readAsDataURL(f)
  }

  const handleDrop = (e) => {
    e.preventDefault()
    const f = e.dataTransfer.files[0]
    if (f) handleFile(f)
  }

  const submit = async () => {
    if (!name.trim()) { toast.error('Please enter a name'); return }
    if (!file) { toast.error('Please select a QR image'); return }
    setUploading(true)
    try {
      const fd = new FormData()
      fd.append('name', name.trim())
      fd.append('qr_image', file)
      const res = await apiForm('/qr/admin/qr-codes', fd)
      if (res.success) {
        toast.success(`QR "${name}" uploaded!`)
        onUploaded(res.qr_code)
        setName(''); setFile(null); setPreview(null)
      } else {
        toast.error(res.message || 'Upload failed')
      }
    } catch { toast.error('Upload failed') }
    finally { setUploading(false) }
  }

  return (
    <div className="bg-white rounded-2xl border border-purple-100 shadow-sm p-6 space-y-4">
      <h3 className="font-bold text-slate-800 flex items-center gap-2">
        <div className="p-1.5 bg-purple-100 rounded-lg"><Plus size={16} className="text-purple-600" /></div>
        Upload New QR
      </h3>

      <Input
        placeholder="QR name (e.g., HDFC UPI)"
        value={name}
        onChange={e => setName(e.target.value)}
        className="rounded-xl border-slate-200"
      />

      <div
        onDrop={handleDrop}
        onDragOver={e => e.preventDefault()}
        onClick={() => fileRef.current?.click()}
        className="border-2 border-dashed border-purple-200 rounded-xl p-6 text-center cursor-pointer hover:border-purple-400 hover:bg-purple-50/50 transition-all"
      >
        {preview ? (
          <img src={preview} alt="preview" className="h-32 mx-auto object-contain rounded-lg" />
        ) : (
          <>
            <Upload className="w-8 h-8 mx-auto text-purple-400 mb-2" />
            <p className="text-sm text-slate-500">Drop QR image here or <span className="text-purple-600 font-semibold">click to browse</span></p>
            <p className="text-xs text-slate-400 mt-1">PNG, JPG, JPEG, WEBP</p>
          </>
        )}
        <input ref={fileRef} type="file" className="hidden" accept="image/*" onChange={e => handleFile(e.target.files[0])} />
      </div>

      <Button
        onClick={submit}
        disabled={uploading}
        className="w-full bg-gradient-to-r from-purple-600 to-blue-600 text-white rounded-xl hover:from-purple-700 hover:to-blue-700"
      >
        {uploading ? <><RefreshCw size={16} className="animate-spin mr-2" />Uploading…</> : <><Upload size={16} className="mr-2" />Upload QR Code</>}
      </Button>
    </div>
  )
}

// ─── Merchant Routing Row ─────────────────────────────────────────────────────
function MerchantRow({ merchant, qrCodes, onSaved }) {
  const [selectedQR, setSelectedQR] = useState(merchant.qr_code_id || '')
  const [enabled, setEnabled] = useState(!!merchant.is_enabled)
  const [saving, setSaving] = useState(false)
  const [showDropdown, setShowDropdown] = useState(false)
  const dropRef = useRef()

  const selectedQRName = qrCodes.find(q => q.id === Number(selectedQR))?.name || 'Select QR Code'

  useEffect(() => {
    const handler = (e) => { if (dropRef.current && !dropRef.current.contains(e.target)) setShowDropdown(false) }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const save = async () => {
    if (!selectedQR) { toast.error('Please select a QR code'); return }
    setSaving(true)
    try {
      const res = await api('/qr/admin/merchant-routing', {
        method: 'POST',
        body: JSON.stringify({
          merchant_id: merchant.merchant_id,
          qr_code_id: Number(selectedQR),
          is_enabled: enabled
        })
      })
      if (res.success) {
        toast.success(res.message)
        onSaved()
      } else {
        toast.error(res.message || 'Save failed')
      }
    } catch { toast.error('Save failed') }
    finally { setSaving(false) }
  }

  return (
    <tr className="border-b border-slate-50 hover:bg-slate-50/50 transition-colors">
      <td className="py-3 px-4">
        <div>
          <p className="font-semibold text-slate-800 text-sm">{merchant.full_name}</p>
          <p className="text-xs text-slate-400">{merchant.merchant_id}</p>
        </div>
      </td>
      <td className="py-3 px-4">
        <p className="text-xs text-slate-500 truncate max-w-[160px]">{merchant.email}</p>
      </td>
      <td className="py-3 px-4">
        {/* QR Code Dropdown */}
        <div className="relative" ref={dropRef}>
          <button
            onClick={() => setShowDropdown(v => !v)}
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-slate-200 bg-white text-sm hover:border-purple-400 transition-colors min-w-[160px]"
          >
            <QrCode size={14} className="text-purple-500 flex-shrink-0" />
            <span className="truncate flex-1 text-left">{selectedQRName}</span>
            <ChevronDown size={14} className="text-slate-400 flex-shrink-0" />
          </button>
          {showDropdown && (
            <div className="absolute top-full left-0 mt-1 bg-white rounded-xl border border-slate-100 shadow-lg z-50 min-w-[200px] max-h-48 overflow-y-auto">
              {qrCodes.length === 0 && (
                <p className="p-3 text-sm text-slate-400 text-center">No QR codes uploaded</p>
              )}
              {qrCodes.map(qr => (
                <button
                  key={qr.id}
                  onClick={() => { setSelectedQR(qr.id); setShowDropdown(false) }}
                  className={`w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-purple-50 transition-colors text-left ${
                    Number(selectedQR) === qr.id ? 'bg-purple-50 text-purple-700 font-semibold' : 'text-slate-700'
                  }`}
                >
                  <QrCode size={12} />
                  {qr.name}
                  {Number(selectedQR) === qr.id && <Check size={12} className="ml-auto text-purple-600" />}
                </button>
              ))}
            </div>
          )}
        </div>
      </td>
      <td className="py-3 px-4">
        {/* Enable Toggle */}
        <button
          onClick={() => setEnabled(v => !v)}
          className={`relative w-12 h-6 rounded-full transition-colors duration-200 ${
            enabled ? 'bg-emerald-500' : 'bg-slate-300'
          }`}
        >
          <span className={`absolute top-1 left-1 w-4 h-4 bg-white rounded-full shadow transition-transform duration-200 ${
            enabled ? 'translate-x-6' : ''
          }`} />
        </button>
      </td>
      <td className="py-3 px-4">
        <EnabledBadge enabled={!!merchant.qr_enabled} />
      </td>
      <td className="py-3 px-4">
        <Button
          onClick={save}
          disabled={saving}
          size="sm"
          className="bg-gradient-to-r from-purple-600 to-blue-600 text-white rounded-lg hover:from-purple-700 hover:to-blue-700 text-xs px-3"
        >
          {saving ? <RefreshCw size={12} className="animate-spin" /> : <Check size={12} className="mr-1" />}
          {saving ? 'Saving…' : 'Save'}
        </Button>
      </td>
    </tr>
  )
}

// ─── Main Page ────────────────────────────────────────────────────────────────
export default function QRServiceRouting() {
  const [qrCodes, setQrCodes] = useState([])
  const [merchants, setMerchants] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')

  const load = async () => {
    setLoading(true)
    try {
      const [qrRes, routingRes] = await Promise.all([
        api('/qr/admin/qr-codes'),
        api('/qr/admin/merchant-routing')
      ])
      if (qrRes.success) setQrCodes(qrRes.qr_codes || [])
      if (routingRes.success) setMerchants(routingRes.merchants || [])
    } catch (e) {
      toast.error('Failed to load data')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const filteredMerchants = merchants.filter(m =>
    !search || m.full_name?.toLowerCase().includes(search.toLowerCase()) ||
    m.merchant_id?.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-3">
            <div className="p-2.5 bg-gradient-to-br from-purple-600 to-blue-600 rounded-xl shadow-lg shadow-purple-500/30">
              <QrCode className="h-6 w-6 text-white" />
            </div>
            QR Service Routing
          </h1>
          <p className="text-slate-500 text-sm mt-1">Upload QR codes and enable them per merchant</p>
        </div>
        <Button onClick={load} variant="outline" className="rounded-xl gap-2 border-purple-200 hover:bg-purple-50">
          <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
          Refresh
        </Button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: QR Codes List + Upload */}
        <div className="space-y-4">
          {/* Upload Form */}
          <UploadQRForm onUploaded={(code) => setQrCodes(prev => [code, ...prev])} />

          {/* Existing QR Codes */}
          <div className="bg-white rounded-2xl border border-slate-100 shadow-sm p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-bold text-slate-800 text-sm">
                Uploaded QR Codes
                <span className="ml-2 px-2 py-0.5 bg-purple-100 text-purple-700 rounded-full text-xs">{qrCodes.length}</span>
              </h3>
            </div>
            {loading ? (
              <div className="grid grid-cols-2 gap-3">
                {[1,2,3,4].map(i => (
                  <div key={i} className="aspect-square bg-slate-100 rounded-2xl animate-pulse" />
                ))}
              </div>
            ) : qrCodes.length === 0 ? (
              <div className="py-10 text-center">
                <QrCode className="h-12 w-12 mx-auto text-slate-200 mb-3" />
                <p className="text-slate-400 text-sm">No QR codes uploaded yet</p>
              </div>
            ) : (
              <div className="grid grid-cols-2 gap-3">
                {qrCodes.map(qr => (
                  <QRCodeCard
                    key={qr.id}
                    qr={qr}
                    onDelete={(id) => setQrCodes(prev => prev.filter(q => q.id !== id))}
                  />
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right: Merchant Routing Table */}
        <div className="lg:col-span-2 bg-white rounded-2xl border border-slate-100 shadow-sm overflow-hidden">
          <div className="p-5 border-b border-slate-100 flex items-center justify-between">
            <h3 className="font-bold text-slate-800">
              Merchant QR Routing
              <span className="ml-2 px-2 py-0.5 bg-purple-100 text-purple-700 rounded-full text-xs">{merchants.length}</span>
            </h3>
            <Input
              placeholder="Search merchants…"
              value={search}
              onChange={e => setSearch(e.target.value)}
              className="w-48 rounded-xl border-slate-200 text-sm"
            />
          </div>

          {loading ? (
            <div className="p-8 text-center">
              <RefreshCw className="h-8 w-8 mx-auto text-purple-400 animate-spin mb-2" />
              <p className="text-slate-400 text-sm">Loading merchants…</p>
            </div>
          ) : filteredMerchants.length === 0 ? (
            <div className="p-12 text-center">
              <AlertCircle className="h-12 w-12 mx-auto text-slate-200 mb-3" />
              <p className="text-slate-400 text-sm">{search ? 'No merchants match your search' : 'No merchants found'}</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-slate-50">
                    <th className="py-3 px-4 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide">Merchant</th>
                    <th className="py-3 px-4 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide">Email</th>
                    <th className="py-3 px-4 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide">Assign QR</th>
                    <th className="py-3 px-4 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide">Enable</th>
                    <th className="py-3 px-4 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide">Status</th>
                    <th className="py-3 px-4 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredMerchants.map(m => (
                    <MerchantRow
                      key={m.merchant_id}
                      merchant={m}
                      qrCodes={qrCodes}
                      onSaved={load}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
