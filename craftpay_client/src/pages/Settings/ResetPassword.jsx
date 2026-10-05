import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Lock, Eye, EyeOff, Shield, Key, CheckCircle2, XCircle, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import clientAPI from '@/api/client_api'

const TABS = [
  { id: 'change-password', label: 'Change Password', icon: Lock },
  { id: 'change-pin', label: 'Change PIN', icon: Key },
  { id: 'delete-pin', label: 'Delete PIN', icon: Trash2 },
]

// ────────────────────────────────────────────────
// Change Password Panel
// ────────────────────────────────────────────────
function ChangePasswordPanel() {
  const [formData, setFormData] = useState({
    currentPassword: '',
    newPassword: '',
    confirmPassword: ''
  })
  const [showPasswords, setShowPasswords] = useState({
    current: false,
    new: false,
    confirm: false
  })
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!formData.currentPassword || !formData.newPassword || !formData.confirmPassword) {
      toast.error('All fields are required')
      return
    }
    if (formData.newPassword !== formData.confirmPassword) {
      toast.error('New passwords do not match')
      return
    }
    if (formData.newPassword.length < 8) {
      toast.error('Password must be at least 8 characters')
      return
    }
    try {
      setLoading(true)
      const response = await clientAPI.changePassword(
        formData.currentPassword,
        formData.newPassword,
        formData.confirmPassword
      )
      if (response.success) {
        toast.success('Password changed successfully!')
        setFormData({ currentPassword: '', newPassword: '', confirmPassword: '' })
      }
    } catch (error) {
      toast.error(error.message || 'Failed to change password')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Card className="border-0 shadow-none">
      <CardHeader className="px-0 pt-0">
        <CardTitle className="flex items-center gap-2 text-lg text-gray-800">
          <div className="p-2 rounded-lg bg-gradient-to-br from-blue-50 to-cyan-50">
            <Lock className="h-5 w-5 text-blue-600" />
          </div>
          Update Your Password
        </CardTitle>
      </CardHeader>
      <CardContent className="px-0">
        <form onSubmit={handleSubmit} className="space-y-5 max-w-lg">
          {/* Current Password */}
          <div className="space-y-2">
            <Label htmlFor="currentPassword">Current Password *</Label>
            <div className="relative">
              <Input
                id="currentPassword"
                type={showPasswords.current ? 'text' : 'password'}
                value={formData.currentPassword}
                onChange={(e) => setFormData({ ...formData, currentPassword: e.target.value })}
                placeholder="Enter current password"
                className="pr-10"
              />
              <button
                type="button"
                onClick={() => setShowPasswords({ ...showPasswords, current: !showPasswords.current })}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-700"
              >
                {showPasswords.current ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            </div>
          </div>

          {/* New Password */}
          <div className="space-y-2">
            <Label htmlFor="newPassword">New Password *</Label>
            <div className="relative">
              <Input
                id="newPassword"
                type={showPasswords.new ? 'text' : 'password'}
                value={formData.newPassword}
                onChange={(e) => setFormData({ ...formData, newPassword: e.target.value })}
                placeholder="Enter new password (min 8 characters)"
                className="pr-10"
              />
              <button
                type="button"
                onClick={() => setShowPasswords({ ...showPasswords, new: !showPasswords.new })}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-700"
              >
                {showPasswords.new ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            </div>
          </div>

          {/* Confirm Password */}
          <div className="space-y-2">
            <Label htmlFor="confirmPassword">Confirm New Password *</Label>
            <div className="relative">
              <Input
                id="confirmPassword"
                type={showPasswords.confirm ? 'text' : 'password'}
                value={formData.confirmPassword}
                onChange={(e) => setFormData({ ...formData, confirmPassword: e.target.value })}
                placeholder="Re-enter new password"
                className="pr-10"
              />
              <button
                type="button"
                onClick={() => setShowPasswords({ ...showPasswords, confirm: !showPasswords.confirm })}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-700"
              >
                {showPasswords.confirm ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            </div>
          </div>

          {/* Requirements */}
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <p className="text-sm font-semibold text-blue-900 mb-2">Password Requirements:</p>
            <ul className="text-sm text-blue-800 space-y-1 list-disc list-inside">
              <li>Minimum 8 characters</li>
              <li>Must be different from current password</li>
            </ul>
          </div>

          <div className="flex gap-3">
            <Button
              type="submit"
              disabled={loading}
              className="bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-700 hover:to-cyan-700"
            >
              {loading ? 'Changing Password...' : 'Change Password'}
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={() => setFormData({ currentPassword: '', newPassword: '', confirmPassword: '' })}
            >
              Reset
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  )
}

// ────────────────────────────────────────────────
// Change PIN Panel
// ────────────────────────────────────────────────
function ChangePinPanel() {
  const [tpins, setTpins] = useState({ current: '', new: '', confirm: '' })
  const [loading, setLoading] = useState(false)
  const [hasPinSet, setHasPinSet] = useState(false)
  const [checkingPin, setCheckingPin] = useState(true)
  const [validations, setValidations] = useState({
    length: false,
    numeric: false,
    notSequential: false,
    notRepeated: false,
  })

  useEffect(() => {
    checkPinStatus()
  }, [])

  const checkPinStatus = async () => {
    setCheckingPin(true)
    try {
      const response = await clientAPI.checkPinStatus()
      setHasPinSet(response.hasPinSet)
    } catch {
      setHasPinSet(false)
    } finally {
      setCheckingPin(false)
    }
  }

  const validatePin = (pin) => {
    const isSequential = ['012345', '123456', '234567', '345678', '456789', '567890'].includes(pin)
    const isRepeated = pin.length === 6 && new Set(pin).size === 1
    setValidations({
      length: pin.length === 6,
      numeric: /^\d+$/.test(pin),
      notSequential: !isSequential,
      notRepeated: !isRepeated,
    })
  }

  const handleTpinInput = (field, value) => {
    const numericValue = value.replace(/\D/g, '').slice(0, 6)
    setTpins({ ...tpins, [field]: numericValue })
    if (field === 'new') validatePin(numericValue)
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (tpins.new !== tpins.confirm) {
      toast.error('New PINs do not match!')
      return
    }
    if (!Object.values(validations).every(v => v)) {
      toast.error('Please meet all PIN requirements')
      return
    }
    setLoading(true)
    try {
      const response = await clientAPI.changePin(
        hasPinSet ? tpins.current : null,
        tpins.new,
        tpins.confirm
      )
      if (response.success) {
        toast.success(response.message || (hasPinSet ? 'PIN changed successfully!' : 'PIN set successfully!'))
        setTpins({ current: '', new: '', confirm: '' })
        setValidations({ length: false, numeric: false, notSequential: false, notRepeated: false })
        setHasPinSet(true)
        localStorage.setItem('hasPinSet', 'true')
        window.dispatchEvent(new Event('pinSet'))
      }
    } catch (error) {
      toast.error(error.message || 'Failed to change PIN')
    } finally {
      setLoading(false)
    }
  }

  if (checkingPin) {
    return (
      <div className="flex items-center justify-center h-40">
        <div className="text-center">
          <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-purple-600 mx-auto" />
          <p className="mt-3 text-gray-600 text-sm">Checking PIN status...</p>
        </div>
      </div>
    )
  }

  return (
    <Card className="border-0 shadow-none">
      <CardHeader className="px-0 pt-0">
        <CardTitle className="flex items-center gap-2 text-lg text-gray-800">
          <div className="p-2 rounded-lg bg-gradient-to-br from-purple-50 to-indigo-50">
            <Key className="h-5 w-5 text-purple-600" />
          </div>
          {hasPinSet ? 'Update Your Transaction TPIN' : 'Set Your Transaction TPIN'}
        </CardTitle>
      </CardHeader>
      <CardContent className="px-0">
        <form onSubmit={handleSubmit} className="space-y-4 max-w-lg">
          {hasPinSet && (
            <div>
              <Label>Current TPIN *</Label>
              <Input
                type="password"
                maxLength={6}
                value={tpins.current}
                onChange={(e) => handleTpinInput('current', e.target.value)}
                placeholder="Enter 6-digit TPIN"
                required
                disabled={loading}
                className="mt-1"
              />
            </div>
          )}
          <div>
            <Label>New TPIN *</Label>
            <Input
              type="password"
              maxLength={6}
              value={tpins.new}
              onChange={(e) => handleTpinInput('new', e.target.value)}
              placeholder="Enter 6-digit TPIN"
              required
              disabled={loading}
              className="mt-1"
            />
          </div>
          <div>
            <Label>Confirm New TPIN *</Label>
            <Input
              type="password"
              maxLength={6}
              value={tpins.confirm}
              onChange={(e) => handleTpinInput('confirm', e.target.value)}
              placeholder="Re-enter 6-digit TPIN"
              required
              disabled={loading}
              className="mt-1"
            />
            {tpins.confirm && tpins.new !== tpins.confirm && (
              <p className="text-sm text-red-600 mt-1">PINs do not match</p>
            )}
          </div>

          <div className="p-4 bg-blue-50 rounded-lg text-sm">
            <p className="font-medium mb-3 text-blue-900">PIN Requirements:</p>
            <div className="space-y-2">
              {[
                { key: 'length', label: 'Must be exactly 6 digits' },
                { key: 'numeric', label: 'Only numeric characters allowed' },
                { key: 'notSequential', label: 'Avoid sequential numbers (123456)' },
                { key: 'notRepeated', label: 'Avoid repeated numbers (111111)' },
              ].map(({ key, label }) => (
                <div key={key} className={`flex items-center gap-2 ${validations[key] ? 'text-green-700' : 'text-gray-600'}`}>
                  {validations[key] ? <CheckCircle2 size={16} /> : <XCircle size={16} />}
                  <span>{label}</span>
                </div>
              ))}
            </div>
          </div>

          <Button
            type="submit"
            className="w-full bg-gradient-to-r from-purple-600 to-purple-700 hover:from-purple-700 hover:to-purple-800"
            disabled={loading}
          >
            {loading
              ? hasPinSet ? 'Changing PIN...' : 'Setting PIN...'
              : hasPinSet ? 'Change TPIN' : 'Set TPIN'}
          </Button>
        </form>
      </CardContent>
    </Card>
  )
}

// ────────────────────────────────────────────────
// Delete PIN Panel
// ────────────────────────────────────────────────
function DeletePinPanel() {
  const [hasPinSet, setHasPinSet] = useState(false)
  const [checkingPin, setCheckingPin] = useState(true)
  const [showConfirmDialog, setShowConfirmDialog] = useState(false)
  const [deleting, setDeleting] = useState(false)

  useEffect(() => {
    checkPinStatus()
  }, [])

  const checkPinStatus = async () => {
    setCheckingPin(true)
    try {
      const response = await clientAPI.checkPinStatus()
      setHasPinSet(response.hasPinSet)
    } catch {
      setHasPinSet(false)
    } finally {
      setCheckingPin(false)
    }
  }

  const handleDeletePin = async () => {
    setDeleting(true)
    try {
      const response = await clientAPI.deletePin()
      if (response.success) {
        toast.success('PIN deleted successfully!')
        setShowConfirmDialog(false)
        setHasPinSet(false)
        localStorage.setItem('hasPinSet', 'false')
        window.dispatchEvent(new Event('pinDeleted'))
      }
    } catch (error) {
      toast.error(error.message || 'Failed to delete PIN')
    } finally {
      setDeleting(false)
    }
  }

  if (checkingPin) {
    return (
      <div className="flex items-center justify-center h-40">
        <div className="text-center">
          <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-red-600 mx-auto" />
          <p className="mt-3 text-gray-600 text-sm">Checking PIN status...</p>
        </div>
      </div>
    )
  }

  return (
    <>
      <Dialog open={showConfirmDialog} onOpenChange={setShowConfirmDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Transaction PIN</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete your transaction PIN? You will need to set a new PIN before viewing credentials again.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowConfirmDialog(false)} disabled={deleting}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleDeletePin} disabled={deleting}>
              {deleting ? 'Deleting...' : 'Delete PIN'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Card className="border-0 shadow-none">
        <CardHeader className="px-0 pt-0">
          <CardTitle className="flex items-center gap-2 text-lg text-gray-800">
            <div className="p-2 rounded-lg bg-gradient-to-br from-red-50 to-orange-50">
              <Trash2 className="h-5 w-5 text-red-600" />
            </div>
            Delete Transaction PIN
          </CardTitle>
        </CardHeader>
        <CardContent className="px-0">
          {hasPinSet ? (
            <div className="max-w-lg space-y-5">
              <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                <p className="text-sm font-semibold text-red-900 mb-1">Warning</p>
                <p className="text-sm text-red-800">
                  Deleting your TPIN will restrict you from performing sensitive actions (e.g. viewing API keys, making payouts) until a new PIN is set.
                </p>
              </div>
              <Button
                variant="destructive"
                onClick={() => setShowConfirmDialog(true)}
                className="flex items-center gap-2"
              >
                <Trash2 size={16} />
                Delete PIN
              </Button>
            </div>
          ) : (
            <div className="max-w-lg">
              <div className="bg-gray-50 border border-gray-200 rounded-lg p-6 text-center">
                <Key className="h-10 w-10 text-gray-400 mx-auto mb-3" />
                <p className="text-gray-600 font-medium">No PIN Set</p>
                <p className="text-sm text-gray-500 mt-1">
                  You don't have a transaction PIN configured. Go to the <strong>Change PIN</strong> tab to set one.
                </p>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </>
  )
}

// ────────────────────────────────────────────────
// Main Reset Password Page
// ────────────────────────────────────────────────
export default function ResetPassword() {
  const [activeTab, setActiveTab] = useState('change-password')

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center gap-3">
        <div className="p-2.5 rounded-xl bg-gradient-to-br from-purple-100 to-blue-100">
          <Shield className="h-7 w-7 text-purple-600" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Reset Password</h1>
          <p className="text-sm text-gray-500">Manage your password and transaction PIN</p>
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="flex gap-1 p-1 bg-gray-100/80 rounded-xl w-fit">
        {TABS.map((tab) => {
          const Icon = tab.icon
          const isActive = activeTab === tab.id
          return (
            <button
              key={tab.id}
              id={`tab-${tab.id}`}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-semibold transition-all duration-200 ${
                isActive
                  ? 'bg-white text-purple-700 shadow-sm'
                  : 'text-gray-500 hover:text-gray-700 hover:bg-white/50'
              }`}
            >
              <Icon size={15} />
              {tab.label}
            </button>
          )
        })}
      </div>

      {/* Tab Content */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
        {activeTab === 'change-password' && <ChangePasswordPanel />}
        {activeTab === 'change-pin' && <ChangePinPanel />}
        {activeTab === 'delete-pin' && <DeletePinPanel />}
      </div>
    </div>
  )
}
