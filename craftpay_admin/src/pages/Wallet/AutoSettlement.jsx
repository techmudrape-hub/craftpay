import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Search, User, Settings, Clock, Percent, DollarSign, History, Play, Timer, Calendar } from 'lucide-react'
import adminAPI from '@/api/admin_api'
import { toast } from 'sonner'

export default function AutoSettlement() {
  const [loading, setLoading] = useState(false)
  const [users, setUsers] = useState([])
  const [filteredUsers, setFilteredUsers] = useState([])
  const [searchTerm, setSearchTerm] = useState('')
  const [selectedUser, setSelectedUser] = useState(null)
  const [showDropdown, setShowDropdown] = useState(false)
  const [walletData, setWalletData] = useState({
    settled_balance: 0,
    unsettled_balance: 0
  })
  
  // Auto-settlement config
  const [config, setConfig] = useState({
    is_enabled: false,
    settlement_mode: 'INTERVAL',
    settlement_interval_minutes: null,
    settlement_frequency: 'DAILY',
    settlement_hour: 0,
    settlement_minute: 0,
    settlement_day: 1,
    hold_percentage: 0,
    minimum_settlement_amount: 0
  })
  
  const [logs, setLogs] = useState([])

  useEffect(() => {
    loadUsers()
  }, [])

  useEffect(() => {
    if (searchTerm) {
      const filtered = users.filter(user => 
        user.full_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        user.merchant_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
        user.email.toLowerCase().includes(searchTerm.toLowerCase())
      )
      setFilteredUsers(filtered)
    } else {
      setFilteredUsers(users)
    }
  }, [searchTerm, users])

  const loadUsers = async () => {
    try {
      const response = await adminAPI.getUsers()
      if (response.success) {
        const userList = response.users || []
        setUsers(Array.isArray(userList) ? userList : [])
        setFilteredUsers(Array.isArray(userList) ? userList : [])
      } else {
        setUsers([])
        setFilteredUsers([])
        toast.error(response.message || 'Failed to load users')
      }
    } catch (error) {
      console.error('Load users error:', error)
      setUsers([])
      setFilteredUsers([])
      toast.error('Failed to load users')
    }
  }

  const loadWalletData = async (merchantId) => {
    try {
      setLoading(true)
      const response = await adminAPI.getMerchantWalletDetails(merchantId)
      
      if (response.success && response.data) {
        setWalletData({
          settled_balance: response.data.settled_balance || 0,
          unsettled_balance: response.data.unsettled_balance || 0
        })
      } else {
        setWalletData({
          settled_balance: 0,
          unsettled_balance: 0
        })
      }
    } catch (error) {
      console.error('Wallet data error:', error)
      setWalletData({
        settled_balance: 0,
        unsettled_balance: 0
      })
    } finally {
      setLoading(false)
    }
  }

  const loadAutoSettlementConfig = async (merchantId) => {
    try {
      const response = await adminAPI.getAutoSettlementConfig(merchantId)
      
      if (response.success && response.config) {
        setConfig(response.config)
      }
    } catch (error) {
      console.error('Load config error:', error)
      toast.error('Failed to load auto-settlement config')
    }
  }

  const loadAutoSettlementLogs = async (merchantId) => {
    try {
      const response = await adminAPI.getAutoSettlementLogs(merchantId)
      
      if (response.success) {
        setLogs(response.logs || [])
      }
    } catch (error) {
      console.error('Load logs error:', error)
      toast.error('Failed to load logs')
    }
  }

  const handleUserSelect = (user) => {
    setSelectedUser(user)
    setSearchTerm(user.full_name)
    setShowDropdown(false)
    loadWalletData(user.merchant_id)
    loadAutoSettlementConfig(user.merchant_id)
    loadAutoSettlementLogs(user.merchant_id)
  }

  const handleSaveConfig = async () => {
    if (!selectedUser) {
      toast.error('Please select a user first')
      return
    }

    try {
      setLoading(true)
      const response = await adminAPI.updateAutoSettlementConfig(selectedUser.merchant_id, config)
      
      if (response.success) {
        toast.success('Auto-settlement configuration saved')
        loadAutoSettlementConfig(selectedUser.merchant_id)
      } else {
        toast.error(response.message || 'Failed to save configuration')
      }
    } catch (error) {
      console.error('Save config error:', error)
      toast.error('Failed to save configuration')
    } finally {
      setLoading(false)
    }
  }

  const handleTriggerSettlement = async () => {
    if (!selectedUser) {
      toast.error('Please select a user first')
      return
    }

    if (!config.is_enabled) {
      toast.error('Auto-settlement is not enabled for this user')
      return
    }

    try {
      setLoading(true)
      const response = await adminAPI.triggerAutoSettlement(selectedUser.merchant_id)
      
      if (response.success) {
        toast.success(`Settlement completed: ₹${response.settled_amount}`)
        loadWalletData(selectedUser.merchant_id)
        loadAutoSettlementLogs(selectedUser.merchant_id)
      } else {
        toast.error(response.message || 'Settlement failed')
      }
    } catch (error) {
      console.error('Trigger settlement error:', error)
      toast.error('Failed to trigger settlement')
    } finally {
      setLoading(false)
    }
  }

  const calculateSettlementPreview = () => {
    const unsettled = parseFloat(walletData.unsettled_balance) || 0
    const holdPct = parseFloat(config.hold_percentage) || 0
    const heldAmount = (unsettled * holdPct) / 100
    const settlementAmount = unsettled - heldAmount
    
    return {
      unsettled,
      heldAmount: heldAmount.toFixed(2),
      settlementAmount: settlementAmount.toFixed(2)
    }
  }

  const getNextSettlementTime = () => {
    if (!config.is_enabled || !config.last_settlement_at) {
      return 'Not scheduled yet'
    }

    if (config.settlement_mode === 'INTERVAL' && config.settlement_interval_minutes) {
      const lastSettlement = new Date(config.last_settlement_at)
      const nextSettlement = new Date(lastSettlement.getTime() + config.settlement_interval_minutes * 60000)
      const now = new Date()
      
      if (nextSettlement <= now) {
        return 'Due now'
      }
      
      const diffMs = nextSettlement - now
      const diffMins = Math.floor(diffMs / 60000)
      const diffHours = Math.floor(diffMins / 60)
      const remainingMins = diffMins % 60
      
      if (diffHours > 0) {
        return `In ${diffHours}h ${remainingMins}m`
      }
      return `In ${diffMins} minutes`
    }
    
    return 'Check schedule'
  }

  const preview = calculateSettlementPreview()

  return (
    <div className="p-6 space-y-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-900">Auto-Settlement</h1>
        <p className="text-gray-600 mt-2">
          Configure automatic wallet settlements for merchants
        </p>
      </div>

      {/* User Selection */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <User className="h-5 w-5 text-blue-600" />
            Select Merchant
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="relative">
            <Label htmlFor="user-search" className="text-sm font-medium mb-2 block">Search User</Label>
            <div className="relative">
              <Search className="absolute left-3 top-3 h-4 w-4 text-gray-400" />
              <Input
                id="user-search"
                placeholder="Search by name, merchant ID, or email..."
                value={searchTerm}
                onChange={(e) => {
                  setSearchTerm(e.target.value)
                  setShowDropdown(true)
                }}
                onFocus={() => setShowDropdown(true)}
                onBlur={() => setTimeout(() => setShowDropdown(false), 200)}
                className="pl-10"
              />
            </div>
            
            {showDropdown && filteredUsers.length > 0 && (
              <div className="absolute z-50 w-full mt-1 bg-white border rounded-lg shadow-lg max-h-60 overflow-auto">
                {filteredUsers.map((user) => (
                  <div
                    key={user.merchant_id}
                    className="p-3 hover:bg-blue-50 cursor-pointer border-b last:border-b-0 transition-colors"
                    onClick={() => handleUserSelect(user)}
                  >
                    <div className="font-medium text-sm">{user.full_name}</div>
                    <div className="text-xs text-gray-500">{user.merchant_id}</div>
                    <div className="text-xs text-gray-400">{user.email}</div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {selectedUser && (
            <div className="mt-4 p-4 bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200 rounded-lg">
              <div className="flex items-center justify-between">
                <div>
                  <div className="font-semibold text-base">{selectedUser.full_name}</div>
                  <div className="text-sm text-gray-600">{selectedUser.merchant_id}</div>
                </div>
                <div className="text-right">
                  <div className="text-xs text-gray-600 mb-1">Unsettled Balance</div>
                  <div className="text-2xl font-bold text-blue-600">₹{parseFloat(walletData.unsettled_balance).toFixed(2)}</div>
                  {config.is_enabled && (
                    <div className="text-xs text-green-600 mt-1 font-medium">
                      {getNextSettlementTime()}
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {selectedUser && (
        <>
          {/* Auto-Settlement Configuration */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-lg">
                <Settings className="h-5 w-5 text-purple-600" />
                Auto-Settlement Settings
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-5">
              {/* Enable/Disable */}
              <div className="flex items-center justify-between p-4 bg-gradient-to-r from-purple-50 to-pink-50 rounded-lg border border-purple-200">
                <div>
                  <Label className="text-base font-semibold">Enable Auto-Settlement</Label>
                  <p className="text-sm text-gray-600 mt-1">
                    Automatically settle wallet based on your schedule
                  </p>
                </div>
                <Switch
                  checked={config.is_enabled}
                  onCheckedChange={(checked) => setConfig({ ...config, is_enabled: checked })}
                />
              </div>

              {/* Settlement Mode */}
              <div>
                <Label className="text-sm font-medium mb-2 block">Settlement Mode</Label>
                <div className="grid grid-cols-2 gap-3">
                  <button
                    type="button"
                    onClick={() => setConfig({ ...config, settlement_mode: 'INTERVAL' })}
                    className={`p-4 rounded-lg border-2 transition-all ${
                      config.settlement_mode === 'INTERVAL'
                        ? 'border-blue-500 bg-blue-50'
                        : 'border-gray-200 hover:border-gray-300'
                    }`}
                  >
                    <Timer className={`h-6 w-6 mx-auto mb-2 ${config.settlement_mode === 'INTERVAL' ? 'text-blue-600' : 'text-gray-400'}`} />
                    <div className="font-semibold text-sm">Interval Mode</div>
                    <div className="text-xs text-gray-600 mt-1">Settle every X minutes</div>
                  </button>
                  <button
                    type="button"
                    onClick={() => setConfig({ ...config, settlement_mode: 'SCHEDULED' })}
                    className={`p-4 rounded-lg border-2 transition-all ${
                      config.settlement_mode === 'SCHEDULED'
                        ? 'border-blue-500 bg-blue-50'
                        : 'border-gray-200 hover:border-gray-300'
                    }`}
                  >
                    <Calendar className={`h-6 w-6 mx-auto mb-2 ${config.settlement_mode === 'SCHEDULED' ? 'text-blue-600' : 'text-gray-400'}`} />
                    <div className="font-semibold text-sm">Scheduled Mode</div>
                    <div className="text-xs text-gray-600 mt-1">Settle at specific time</div>
                  </button>
                </div>
              </div>

              {/* Interval Mode Settings */}
              {config.settlement_mode === 'INTERVAL' && (
                <div className="p-4 bg-blue-50 rounded-lg border border-blue-200">
                  <Label htmlFor="interval" className="text-sm font-medium flex items-center gap-2 mb-2">
                    <Clock className="h-4 w-4 text-blue-600" />
                    Settlement Interval (Minutes)
                  </Label>
                  <p className="text-xs text-gray-600 mb-3">
                    Wallet will be settled automatically every X minutes
                  </p>
                  <Input
                    id="interval"
                    type="number"
                    min="1"
                    placeholder="e.g., 2 for every 2 minutes, 60 for every hour"
                    value={config.settlement_interval_minutes || ''}
                    onChange={(e) => setConfig({ ...config, settlement_interval_minutes: parseInt(e.target.value) || null })}
                    className="bg-white"
                  />
                  {config.settlement_interval_minutes && (
                    <div className="mt-2 text-sm text-blue-700 font-medium">
                      {config.settlement_interval_minutes >= 60 
                        ? `Settles every ${Math.floor(config.settlement_interval_minutes / 60)} hour${Math.floor(config.settlement_interval_minutes / 60) > 1 ? 's' : ''} ${config.settlement_interval_minutes % 60 > 0 ? `${config.settlement_interval_minutes % 60} min` : ''}`
                        : `Settles every ${config.settlement_interval_minutes} minutes`
                      }
                    </div>
                  )}
                </div>
              )}

              {/* Scheduled Mode Settings */}
              {config.settlement_mode === 'SCHEDULED' && (
                <div className="p-4 bg-purple-50 rounded-lg border border-purple-200 space-y-4">
                  <div>
                    <Label htmlFor="frequency" className="text-sm font-medium flex items-center gap-2 mb-2">
                      <Clock className="h-4 w-4 text-purple-600" />
                      Settlement Frequency
                    </Label>
                    <Select
                      value={config.settlement_frequency}
                      onValueChange={(value) => setConfig({ ...config, settlement_frequency: value })}
                    >
                      <SelectTrigger className="bg-white">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="HOURLY">Hourly</SelectItem>
                        <SelectItem value="DAILY">Daily</SelectItem>
                        <SelectItem value="WEEKLY">Weekly</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  {config.settlement_frequency === 'WEEKLY' && (
                    <div>
                      <Label htmlFor="day" className="text-sm font-medium mb-2 block">Day of Week</Label>
                      <Select
                        value={config.settlement_day.toString()}
                        onValueChange={(value) => setConfig({ ...config, settlement_day: parseInt(value) })}
                      >
                        <SelectTrigger className="bg-white">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="1">Monday</SelectItem>
                          <SelectItem value="2">Tuesday</SelectItem>
                          <SelectItem value="3">Wednesday</SelectItem>
                          <SelectItem value="4">Thursday</SelectItem>
                          <SelectItem value="5">Friday</SelectItem>
                          <SelectItem value="6">Saturday</SelectItem>
                          <SelectItem value="7">Sunday</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  )}

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <Label htmlFor="hour" className="text-sm font-medium mb-2 block">Hour (0-23)</Label>
                      <Input
                        id="hour"
                        type="number"
                        min="0"
                        max="23"
                        value={config.settlement_hour}
                        onChange={(e) => setConfig({ ...config, settlement_hour: parseInt(e.target.value) || 0 })}
                        className="bg-white"
                      />
                    </div>
                    <div>
                      <Label htmlFor="minute" className="text-sm font-medium mb-2 block">Minute (0-59)</Label>
                      <Input
                        id="minute"
                        type="number"
                        min="0"
                        max="59"
                        value={config.settlement_minute}
                        onChange={(e) => setConfig({ ...config, settlement_minute: parseInt(e.target.value) || 0 })}
                        className="bg-white"
                      />
                    </div>
                  </div>
                </div>
              )}

              {/* Hold Percentage */}
              <div>
                <Label htmlFor="hold-percentage" className="text-sm font-medium flex items-center gap-2 mb-2">
                  <Percent className="h-4 w-4 text-orange-600" />
                  Hold Percentage (0-100%)
                </Label>
                <p className="text-xs text-gray-600 mb-2">
                  Percentage of unsettled balance to <strong>keep</strong> in unsettled wallet (0% = settle all, 100% = settle nothing)
                </p>
                <Input
                  id="hold-percentage"
                  type="number"
                  min="0"
                  max="100"
                  step="0.01"
                  value={config.hold_percentage}
                  onChange={(e) => setConfig({ ...config, hold_percentage: parseFloat(e.target.value) || 0 })}
                />
              </div>

              {/* Minimum Settlement Amount */}
              <div>
                <Label htmlFor="min-amount" className="text-sm font-medium flex items-center gap-2 mb-2">
                  <DollarSign className="h-4 w-4 text-green-600" />
                  Minimum Settlement Amount (₹)
                </Label>
                <p className="text-xs text-gray-600 mb-2">
                  Minimum unsettled balance required to trigger settlement
                </p>
                <Input
                  id="min-amount"
                  type="number"
                  min="0"
                  step="0.01"
                  value={config.minimum_settlement_amount}
                  onChange={(e) => setConfig({ ...config, minimum_settlement_amount: parseFloat(e.target.value) || 0 })}
                />
              </div>

              {/* Settlement Preview */}
              <div className="p-5 bg-gradient-to-r from-green-50 to-emerald-50 rounded-lg border-2 border-green-200">
                <h3 className="font-bold text-base mb-4 text-green-800">Settlement Preview</h3>
                <div className="space-y-3">
                  <div className="flex justify-between items-center">
                    <span className="text-sm text-gray-700">Current Unsettled Balance:</span>
                    <span className="font-bold text-lg">₹{preview.unsettled}</span>
                  </div>
                  <div className="flex justify-between items-center text-orange-600">
                    <span className="text-sm">Amount to Hold ({config.hold_percentage}%):</span>
                    <span className="font-bold text-lg">₹{preview.heldAmount}</span>
                  </div>
                  <div className="h-px bg-green-300"></div>
                  <div className="flex justify-between items-center text-green-700">
                    <span className="text-base font-semibold">Amount to Settle:</span>
                    <span className="font-bold text-2xl">₹{preview.settlementAmount}</span>
                  </div>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex gap-3 pt-2">
                <Button
                  onClick={handleSaveConfig}
                  disabled={loading}
                  className="flex-1 h-11 text-base font-semibold"
                >
                  {loading ? 'Saving...' : 'Save Configuration'}
                </Button>
                <Button
                  onClick={handleTriggerSettlement}
                  disabled={loading || !config.is_enabled}
                  variant="outline"
                  className="flex items-center gap-2 h-11 px-6 border-2"
                >
                  <Play className="h-4 w-4" />
                  Trigger Now
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Settlement Logs */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-lg">
                <History className="h-5 w-5 text-indigo-600" />
                Settlement History
              </CardTitle>
            </CardHeader>
            <CardContent>
              {logs.length === 0 ? (
                <div className="text-center py-12">
                  <History className="h-12 w-12 text-gray-300 mx-auto mb-3" />
                  <p className="text-gray-500 text-sm">No settlement logs yet</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {logs.map((log) => (
                    <div
                      key={log.id}
                      className={`p-4 rounded-lg border-2 transition-all ${
                        log.status === 'SUCCESS'
                          ? 'bg-green-50 border-green-300'
                          : log.status === 'FAILED'
                          ? 'bg-red-50 border-red-300'
                          : 'bg-gray-50 border-gray-300'
                      }`}
                    >
                      <div className="flex justify-between items-start">
                        <div className="flex-1">
                          <div className={`font-bold text-sm mb-1 ${
                            log.status === 'SUCCESS' ? 'text-green-700' : log.status === 'FAILED' ? 'text-red-700' : 'text-gray-700'
                          }`}>
                            {log.status}
                          </div>
                          <div className="text-xs text-gray-600 mb-1">{log.reason}</div>
                          {log.settlement_id && (
                            <div className="text-xs text-gray-500 font-mono">
                              ID: {log.settlement_id}
                            </div>
                          )}
                        </div>
                        <div className="text-right ml-4">
                          <div className="text-base font-bold text-gray-900">₹{parseFloat(log.settled_amount).toFixed(2)}</div>
                          <div className="text-xs text-gray-600">
                            Held: ₹{parseFloat(log.held_amount).toFixed(2)}
                          </div>
                          <div className="text-xs text-gray-500 mt-1">
                            {new Date(log.created_at).toLocaleString()}
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  )
}
