import { useState, useEffect, useRef } from 'react'
import { Outlet, useNavigate, Link, useLocation } from 'react-router-dom'
import { 
  LayoutDashboard, Users, ArrowLeftRight, Wallet, 
  TrendingUp, Shield, Settings, Activity, 
  ChevronDown, LogOut, Menu, X, Bell, Search,
  UserPlus, List, Route, MessageSquare,
  FileText, Clock, DollarSign, Building,
  Lock, Key, CreditCard, Briefcase, Package, User,
  ChevronLeft, ChevronRight, AlertTriangle, RefreshCw, QrCode
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import adminAPI from '@/api/admin_api'
import { toast } from 'sonner'
import PinNotification from '@/components/PinNotification'

const menuItems = [
  { 
    title: 'Dashboard', 
    icon: LayoutDashboard, 
    path: '/' 
  },
  {
    title: 'User',
    icon: Users,
    submenu: [
      { title: 'User Onboarding', icon: UserPlus, path: '/user/onboarding' },
      { title: 'User List', icon: List, path: '/user/list' },
      { title: 'Service Routing', icon: Route, path: '/user/service-routing' },
      { title: 'OTP Service', icon: MessageSquare, path: '/user/otp-service', disabled: true },
    ]
  },
  {
    title: 'Transactions',
    icon: ArrowLeftRight,
    submenu: [
      { title: 'Payin Report', icon: FileText, path: '/transactions/payin-report' },
      { title: 'Payout Report', icon: FileText, path: '/transactions/payout-report' },
      { title: 'Pending Payin', icon: Clock, path: '/transactions/pending-payin' },
      { title: 'Pending Payout', icon: Clock, path: '/transactions/pending-payout' },
    ]
  },
  { 
    title: 'Manual Reconciliation', 
    icon: RefreshCw, 
    path: '/manual-reconciliation' 
  },
  { 
    title: 'Chargeback Manager', 
    icon: AlertTriangle, 
    path: '/chargeback-manager' 
  },
  { 
    title: 'User Transaction Summary', 
    icon: User, 
    path: '/user-transaction-summary' 
  },
  {
    title: 'Fund Manager',
    icon: TrendingUp,
    submenu: [
      { title: 'Topup Fund', icon: DollarSign, path: '/fund-manager/topup' },
      { title: 'Fetch Fund', icon: Package, path: '/fund-manager/fetch' },
      { title: 'Fund Requests', icon: FileText, path: '/fund-manager/requests' },
      { title: 'Settle Wallet', icon: Wallet, path: '/wallet/settle' },
      { title: 'Auto-Settlement', icon: Clock, path: '/wallet/auto-settlement' },
      { title: 'Wallet Overview', icon: Wallet, path: '/wallet/overview' },
      { title: 'Wallet Statement', icon: FileText, path: '/wallet/statement' },
    ]
  },
  { 
    title: 'Personal Payout', 
    icon: DollarSign, 
    path: '/payout/personal' 
  },
  {
    title: 'Security',
    icon: Shield,
    submenu: [
      { title: 'Change Password', icon: Lock, path: '/security/change-password' },
      { title: 'Change PIN', icon: Key, path: '/security/change-pin' },
      { title: 'IP Security', icon: Shield, path: '/security/ip-security' },
    ]
  },
  {
    title: 'Settings',
    icon: Settings,
    submenu: [
      { title: 'Add/Update Bank', icon: Building, path: '/settings/bank' },
      { title: 'Manage Services', icon: Briefcase, path: '/settings/services', disabled: true },
      { title: 'Commercials', icon: CreditCard, path: '/settings/commercials' },
    ]
  },
  { 
    title: 'Activity Logs', 
    icon: Activity, 
    path: '/activity-logs' 
  },
  {
    title: 'QR Collection',
    icon: QrCode,
    submenu: [
      { title: 'QR Service Routing', icon: QrCode, path: '/qr/service-routing' },
      { title: 'QR Transactions', icon: FileText, path: '/qr/transactions' },
    ]
  },
]

export default function DashboardLayout() {
  const navigate = useNavigate()
  const location = useLocation()
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [expandedMenus, setExpandedMenus] = useState({})
  const [showNotifications, setShowNotifications] = useState(false)
  const [pendingFundRequests, setPendingFundRequests] = useState([])
  const [notificationCount, setNotificationCount] = useState(0)
  
  // Session expiry state - 15 MINUTES PRODUCTION
  const [showWarning, setShowWarning] = useState(false)
  const [countdown, setCountdown] = useState(20)
  const [refreshing, setRefreshing] = useState(false)
  const lastActivityRef = useRef(Date.now())
  const checkIntervalRef = useRef(null)
  const countdownIntervalRef = useRef(null)
  
  const SESSION_TIMEOUT = 15 * 60 * 1000 // 15 minutes
  const WARNING_TIME = 14 * 60 * 1000 + 40 * 1000 // 14 minutes 40 seconds
  const COUNTDOWN_DURATION = 20 // 20 seconds countdown

  // const SESSION_TIMEOUT = 20000 // 15 minutes
  // const WARNING_TIME = 10000 // 14 minutes 40 seconds
  // const COUNTDOWN_DURATION = 10 // 20 seconds countdown
  
  useEffect(() => {
    console.log('✅ Session monitoring started - 15 minutes timeout')
    lastActivityRef.current = Date.now()
    
    // Load pending fund requests
    loadPendingFundRequests()
    
    // Refresh fund requests every 30 seconds
    const fundRequestInterval = setInterval(() => {
      loadPendingFundRequests()
    }, 30000)
    
    // Check every second
    checkIntervalRef.current = setInterval(() => {
      const elapsed = Date.now() - lastActivityRef.current
      
      if (elapsed >= WARNING_TIME && !showWarning) {
        console.log('🚨 SHOWING WARNING - Session expiring in 20 seconds')
        setShowWarning(true)
        setCountdown(COUNTDOWN_DURATION)
      }
    }, 1000)
    
    const handleActivity = () => {
      if (!showWarning) {
        lastActivityRef.current = Date.now()
      }
    }
    
    const events = ['mousedown', 'keydown', 'scroll', 'click']
    events.forEach(e => window.addEventListener(e, handleActivity, { passive: true }))
    
    return () => {
      if (checkIntervalRef.current) clearInterval(checkIntervalRef.current)
      if (countdownIntervalRef.current) clearInterval(countdownIntervalRef.current)
      if (fundRequestInterval) clearInterval(fundRequestInterval)
      events.forEach(e => window.removeEventListener(e, handleActivity))
    }
  }, [showWarning])
  
  // Separate effect for countdown
  useEffect(() => {
    if (showWarning && countdown > 0) {
      countdownIntervalRef.current = setInterval(() => {
        setCountdown(prev => {
          console.log('⏳ Countdown:', prev - 1)
          if (prev <= 1) {
            clearInterval(countdownIntervalRef.current)
            handleSessionExpired()
            return 0
          }
          return prev - 1
        })
      }, 1000)
      
      return () => {
        if (countdownIntervalRef.current) {
          clearInterval(countdownIntervalRef.current)
        }
      }
    }
  }, [showWarning])
  
  const handleSessionExpired = async () => {
    console.log('🔴 SESSION EXPIRED - Logging out')
    setShowWarning(false)
    
    // Clear all intervals
    if (checkIntervalRef.current) clearInterval(checkIntervalRef.current)
    if (countdownIntervalRef.current) clearInterval(countdownIntervalRef.current)
    
    try {
      // Logout and clear storage
      await adminAPI.logout()
    } catch (error) {
      console.error('Logout error:', error)
    }
    
    // Force navigation to login
    toast.error('Session expired. Please login again.')
    navigate('/login', { replace: true })
  }
  
  const handleRefreshSession = async () => {
    setRefreshing(true)
    if (countdownIntervalRef.current) {
      clearInterval(countdownIntervalRef.current)
    }
    try {
      const response = await adminAPI.verifyToken()
      if (response.success) {
        lastActivityRef.current = Date.now()
        setShowWarning(false)
        setCountdown(COUNTDOWN_DURATION)
        toast.success('Session refreshed!')
      } else {
        throw new Error('Token verification failed')
      }
    } catch (error) {
      console.error('Session refresh error:', error)
      await adminAPI.logout()
      toast.error('Session refresh failed. Please login again.')
      navigate('/login', { replace: true })
    } finally {
      setRefreshing(false)
    }
  }
  
  const handleCloseSession = async () => {
    console.log('🔴 USER CLOSED SESSION - Logging out')
    if (countdownIntervalRef.current) {
      clearInterval(countdownIntervalRef.current)
    }
    if (checkIntervalRef.current) {
      clearInterval(checkIntervalRef.current)
    }
    setShowWarning(false)
    setCountdown(COUNTDOWN_DURATION)
    
    try {
      await adminAPI.logout()
    } catch (error) {
      console.error('Logout error:', error)
    }
    
    toast.info('Logged out')
    navigate('/login', { replace: true })
  }

  const handleLogout = async () => {
    console.log('🔴 MANUAL LOGOUT')
    
    // Clear all intervals
    if (checkIntervalRef.current) clearInterval(checkIntervalRef.current)
    if (countdownIntervalRef.current) clearInterval(countdownIntervalRef.current)
    
    try {
      await adminAPI.logout()
      toast.success('Logged out successfully')
    } catch (error) {
      console.error('Logout error:', error)
    } finally {
      navigate('/login', { replace: true })
    }
  }

  const loadPendingFundRequests = async () => {
    try {
      const response = await adminAPI.getFundRequests('PENDING')
      if (response.success) {
        const requests = response.data || []
        setPendingFundRequests(requests)
        setNotificationCount(requests.length)
      }
    } catch (error) {
      console.error('Load fund requests error:', error)
    }
  }

  const handleNotificationClick = () => {
    setShowNotifications(!showNotifications)
  }

  const handleViewAllRequests = () => {
    setShowNotifications(false)
    navigate('/fund-manager/requests')
  }

  const formatCurrency = (amount) => {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 2
    }).format(amount || 0)
  }

  const formatDateTime = (dateString) => {
    if (!dateString) return '-'
    return new Date(dateString).toLocaleString('en-IN', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  const toggleMenu = (title) => {
    setExpandedMenus(prev => ({ ...prev, [title]: !prev[title] }))
  }

  const isActive = (path) => location.pathname === path

  return (
    <>
      {/* Session Warning Dialog - INLINE */}
      <Dialog open={showWarning} onOpenChange={() => {}}>
        <DialogContent className="sm:max-w-md" hideClose>
          <DialogHeader>
            <div className="flex items-center gap-3 mb-2">
              <div className="p-3 bg-orange-100 rounded-full">
                <AlertTriangle className="h-6 w-6 text-orange-600" />
              </div>
              <DialogTitle className="text-xl">Session Expiring Soon</DialogTitle>
            </div>
            <DialogDescription className="text-base pt-2">
              Your session will expire in {countdown} seconds
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-col items-center justify-center py-6">
            <div className="text-6xl font-bold text-orange-600">{countdown}</div>
            <div className="text-sm text-gray-500 mt-2">seconds remaining</div>
          </div>
          <DialogFooter className="flex gap-2">
            <Button variant="outline" onClick={handleCloseSession} disabled={refreshing} className="flex-1">
              <X className="h-4 w-4 mr-2" />
              Close
            </Button>
            <Button onClick={handleRefreshSession} disabled={refreshing} className="flex-1 bg-orange-500 hover:bg-orange-600">
              <RefreshCw className={`h-4 w-4 mr-2 ${refreshing ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      
      <div className="flex h-screen bg-gradient-to-br from-slate-50 via-purple-50/30 to-blue-50/30">
        {/* Sidebar */}
      <aside className={`${sidebarOpen ? 'w-72' : 'w-20'} glass-effect border-r border-purple-100/50 shadow-2xl transition-all duration-300 flex flex-col relative overflow-hidden`}>
        {/* Animated Background Accent */}
        <div className="absolute top-0 left-0 w-full h-1 animated-gradient"></div>
        
        {sidebarOpen ? (
          <>
            {/* Logo Section - Open */}
            <div className="p-6 border-b border-purple-100/50 flex items-center justify-between bg-white/50">
              <div className="flex items-center gap-3">
                <img src="/craftpay.png" alt="CraftPay" className="h-10 w-auto" />
              </div>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setSidebarOpen(!sidebarOpen)}
                className="text-gray-600 hover:text-purple-600 hover:bg-purple-50 transition-all rounded-xl"
                title="Close sidebar"
              >
                <ChevronLeft size={20} />
              </Button>
            </div>
          </>
        ) : (
          <>
            {/* Logo Section - Closed */}
            <div className="p-4 border-b border-purple-100/50 flex flex-col items-center gap-3 bg-white/50">
              <img src="/craftpay.png" alt="CraftPay" className="h-10 w-10 object-contain" />
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setSidebarOpen(!sidebarOpen)}
                className="text-gray-600 hover:text-purple-600 hover:bg-purple-50 transition-all p-2 rounded-xl"
                title="Open sidebar"
              >
                <ChevronRight size={20} />
              </Button>
            </div>
          </>
        )}

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto p-4 space-y-2 scrollbar-thin">
          {menuItems.map((item) => (
            <div key={item.title} className="animate-slide-in">
              {item.submenu ? (
                <div>
                  <button
                    onClick={() => toggleMenu(item.title)}
                    className={`w-full flex items-center ${sidebarOpen ? 'justify-between' : 'justify-center'} p-3 rounded-xl transition-all duration-200 hover:bg-purple-50/70 text-gray-700 hover:text-purple-700 group relative overflow-hidden`}
                    title={!sidebarOpen ? item.title : ''}
                  >
                    <div className={`flex items-center gap-3 relative z-10 ${!sidebarOpen && 'justify-center'}`}>
                      <div className="p-2 rounded-lg bg-gradient-to-br from-purple-50 to-blue-50 group-hover:from-purple-100 group-hover:to-blue-100 transition-all">
                        <item.icon size={18} className="text-purple-600 group-hover:text-purple-700 transition-colors" />
                      </div>
                      {sidebarOpen && <span className="font-semibold text-sm">{item.title}</span>}
                    </div>
                    {sidebarOpen && (
                      <ChevronDown
                        size={16}
                        className={`transition-transform duration-300 relative z-10 text-purple-600 ${expandedMenus[item.title] ? 'rotate-180' : ''}`}
                      />
                    )}
                  </button>
                  {expandedMenus[item.title] && sidebarOpen && (
                    <div className="ml-8 mt-2 space-y-1 animate-slide-in border-l-2 border-purple-100 pl-3">
                      {item.submenu.map((subItem) => {
                        const isDisabled = subItem.disabled
                        const ItemComponent = isDisabled ? 'div' : Link
                        
                        return (
                          <ItemComponent
                            key={subItem.path}
                            {...(!isDisabled && { to: subItem.path })}
                            className={`flex items-center gap-3 p-2.5 rounded-lg transition-all duration-200 group ${
                              isDisabled
                                ? 'opacity-40 blur-[0.5px] cursor-not-allowed pointer-events-none'
                                : isActive(subItem.path) 
                                  ? 'craftpay-gradient-btn text-white shadow-lg shadow-purple-500/30 scale-[1.02]' 
                                  : 'text-gray-600 hover:bg-purple-50/70 hover:text-purple-700'
                            }`}
                            {...(isDisabled && { title: 'Coming Soon' })}
                          >
                            <subItem.icon size={16} className="group-hover:scale-110 transition-transform duration-200" />
                            <span className="text-sm font-medium">{subItem.title}</span>
                          </ItemComponent>
                        )
                      })}
                    </div>
                  )}
                </div>
              ) : (
                <Link
                  to={item.path}
                  className={`flex items-center gap-3 p-3 rounded-xl transition-all duration-200 group ${
                    isActive(item.path) 
                      ? 'craftpay-gradient-btn text-white shadow-lg shadow-purple-500/30 scale-[1.02]' 
                      : 'text-gray-700 hover:bg-purple-50/70 hover:text-purple-700'
                  } ${!sidebarOpen && 'justify-center'}`}
                  title={!sidebarOpen ? item.title : ''}
                >
                  <div className={`p-2 rounded-lg transition-all ${
                    isActive(item.path) 
                      ? 'bg-white/20' 
                      : 'bg-gradient-to-br from-purple-50 to-blue-50 group-hover:from-purple-100 group-hover:to-blue-100'
                  }`}>
                    <item.icon size={18} className={`transition-colors ${
                      isActive(item.path) 
                        ? 'text-white' 
                        : 'text-purple-600 group-hover:text-purple-700'
                    }`} />
                  </div>
                  {sidebarOpen && <span className="font-semibold text-sm">{item.title}</span>}
                </Link>
              )}
            </div>
          ))}
        </nav>
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col overflow-hidden">
        {/* Top Navigation Bar */}
        <header className="glass-effect border-b border-purple-100/50 shadow-sm">
          <div className="flex items-center justify-between px-6 py-4">
            {/* Search Bar */}
            <div className="flex-1 max-w-xl">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-purple-400" />
                <Input
                  placeholder="Search transactions, users, reports..."
                  className="pl-10 bg-white/70 border-purple-200/50 focus:bg-white focus:border-purple-400 rounded-xl shadow-sm"
                />
              </div>
            </div>

            {/* Right Side Actions */}
            <div className="flex items-center gap-4 ml-6">
              {/* Notifications */}
              <div className="relative">
                <button 
                  onClick={handleNotificationClick}
                  className="relative p-2.5 text-gray-600 hover:text-purple-600 hover:bg-purple-50 rounded-xl transition-all shadow-sm hover:shadow-md"
                >
                  <Bell size={22} />
                  {notificationCount > 0 && (
                    <span className="absolute top-0.5 right-0.5 w-5 h-5 craftpay-gradient-btn text-white text-xs rounded-full flex items-center justify-center font-semibold animate-pulse">
                      {notificationCount > 9 ? '9+' : notificationCount}
                    </span>
                  )}
                </button>

                {/* Notification Dropdown */}
                {showNotifications && (
                  <div className="absolute right-0 mt-2 w-96 glass-effect rounded-2xl shadow-2xl border border-purple-100/50 z-50 max-h-96 overflow-hidden">
                    <div className="p-4 border-b border-purple-100/50 craftpay-gradient-btn text-white">
                      <h3 className="font-semibold">Pending Fund Requests</h3>
                      <p className="text-xs text-white/90 mt-1">{notificationCount} pending request{notificationCount !== 1 ? 's' : ''}</p>
                    </div>
                    
                    <div className="max-h-80 overflow-y-auto">
                      {pendingFundRequests.length === 0 ? (
                        <div className="p-8 text-center text-gray-500">
                          <Bell className="h-12 w-12 mx-auto mb-3 text-gray-300" />
                          <p>No pending fund requests</p>
                        </div>
                      ) : (
                        pendingFundRequests.map((request) => (
                          <div 
                            key={request.request_id}
                            className="p-4 border-b border-purple-50 hover:bg-purple-50/50 transition-colors cursor-pointer"
                            onClick={handleViewAllRequests}
                          >
                            <div className="flex items-start justify-between">
                              <div className="flex-1">
                                <p className="font-semibold text-gray-800">{request.merchant_name || request.merchant_id}</p>
                                <p className="text-sm text-gray-600 mt-1">{request.remarks || 'Fund request'}</p>
                                <p className="text-xs text-gray-500 mt-1">{formatDateTime(request.created_at)}</p>
                              </div>
                              <div className="text-right ml-3">
                                <p className="font-bold orchpay-gradient-text">{formatCurrency(request.amount)}</p>
                                <span className="inline-block mt-1 px-2 py-1 text-xs bg-yellow-100 text-yellow-700 rounded-full">
                                  Pending
                                </span>
                              </div>
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                    
                    {pendingFundRequests.length > 0 && (
                      <div className="p-3 border-t border-purple-100/50 bg-white/50">
                        <button
                          onClick={handleViewAllRequests}
                          className="w-full text-center text-sm orchpay-gradient-text hover:opacity-80 font-semibold"
                        >
                          View All Requests →
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* User Profile */}
              <div className="flex items-center gap-3 pl-4 border-l border-purple-200/50">
                <div className="text-right">
                  <p className="text-sm font-semibold text-gray-800">Admin User</p>
                  <p className="text-xs text-gray-500">{adminAPI.getAdminId() || 'admin@orchpay.com'}</p>
                </div>
                <div className="w-11 h-11 craftpay-gradient-btn rounded-xl flex items-center justify-center text-white font-semibold shadow-lg shadow-purple-500/30">
                  <User size={20} />
                </div>
              </div>

              {/* Logout Button */}
              <Button
                onClick={handleLogout}
                variant="ghost"
                className="flex items-center gap-2 text-red-600 hover:bg-red-50 hover:text-red-700 rounded-xl transition-all duration-200 px-4 py-2 shadow-sm hover:shadow-md"
              >
                <LogOut size={18} />
                <span className="font-semibold text-sm">Logout</span>
              </Button>
            </div>
          </div>
        </header>

        {/* PIN Notification Banner */}
        <PinNotification />

        {/* Page Content */}
        <div className="flex-1 overflow-y-auto p-6 scrollbar-thin">
          <div className="animate-slide-in">
            <Outlet />
          </div>
        </div>
      </main>
      </div>
    </>
  )
}
