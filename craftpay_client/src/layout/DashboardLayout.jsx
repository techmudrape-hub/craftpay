import { useState, useEffect } from 'react'
import { Outlet, useNavigate, Link, useLocation } from 'react-router-dom'
import { 
  LayoutDashboard, ArrowLeftRight, Wallet, 
  TrendingUp, Shield, Settings, 
  ChevronDown, LogOut, Bell, Search,
  FileText, Clock, DollarSign, Building,
  Lock, Key, Book, KeyRound, QrCode, CreditCard, User,
  ChevronLeft, ChevronRight, AlertTriangle, Banknote, List
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { toast } from 'sonner'
import clientAPI from '@/api/client_api'
import SessionExpiryWarning from '@/components/SessionExpiryWarning'
import PinNotification from '@/components/PinNotification'

const menuItems = [
  { 
    title: 'Dashboard', 
    icon: LayoutDashboard, 
    path: '/' 
  },
  { 
    title: 'Collections', 
    icon: FileText, 
    path: '/transactions/payin-report' 
  },
  { 
    title: 'Payouts', 
    icon: ArrowLeftRight, 
    path: '/transactions/payout-report' 
  },
  { 
    title: 'Chargebacks', 
    icon: AlertTriangle, 
    path: '/chargebacks' 
  },
  {
    title: 'Fund Manager',
    icon: TrendingUp,
    submenu: [
      { title: 'Wallet Overview', icon: Wallet, path: '/fund-manager/wallet-overview' },
      { title: 'Wallet Statement', icon: FileText, path: '/fund-manager/wallet-statement' },
      { title: 'Fund Request', icon: DollarSign, path: '/fund-manager/request' },
      { title: 'IMPS Payout', icon: Banknote, path: '/fund-manager/settle' },
      { title: 'Bank Lists', icon: List, path: '/fund-manager/bank-lists' },
    ]
  },
  { 
    title: 'Collect Payment', 
    icon: QrCode, 
    path: '/collect-payment' 
  },
  {
    title: 'Settings',
    icon: Settings,
    submenu: [
      { title: 'Reset Password', icon: Lock, path: '/settings/reset-password' },
      { title: 'Rates', icon: CreditCard, path: '/settings/rates' },
    ]
  },
  {
    title: 'Developer Zone',
    icon: Book,
    submenu: [
      { title: 'API Docs', icon: FileText, path: '/developer/api-docs' },
      { title: 'API Keys', icon: KeyRound, path: '/developer/api-keys' },
    ]
  },
]

// QR-only menu item added dynamically below

export default function DashboardLayout() {
  const navigate = useNavigate()
  const location = useLocation()
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [expandedMenus, setExpandedMenus] = useState({})
  const [qrEnabled, setQrEnabled] = useState(false)
  const [merchantInfo, setMerchantInfo] = useState({
    name: 'Merchant User',
    email: 'merchant@example.com'
  })

  useEffect(() => {
    // Load merchant info from localStorage
    const merchantName = clientAPI.getMerchantName()
    const merchantId = clientAPI.getMerchantId()
    
    if (merchantName) {
      setMerchantInfo({
        name: merchantName,
        email: merchantId || 'merchant@example.com'
      })
    }

    // Verify token on mount
    verifyAuth()

    // Check if QR is enabled for this merchant
    checkQREnabled()
  }, [])

  const checkQREnabled = async () => {
    try {
      const token = localStorage.getItem('merchantToken')
      if (!token) return
      const API_ROOT = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5000/api'
      const res = await fetch(`${API_ROOT}/merchant/qr-status`, {
        headers: { Authorization: `Bearer ${token}` }
      })
      if (!res.ok) return
      const data = await res.json()
      if (data.success) setQrEnabled(!!data.qr_enabled)
    } catch {
      // silent fail - QR menu just won't show
    }
  }

  const verifyAuth = async () => {
    try {
      await clientAPI.verifyToken()
    } catch (error) {
      console.error('Token verification failed:', error)
      handleLogout()
    }
  }

  const handleLogout = () => {
    clientAPI.logout()
    toast.success('Logged out successfully')
    navigate('/login', { replace: true })
  }

  const toggleMenu = (title) => {
    setExpandedMenus(prev => ({ ...prev, [title]: !prev[title] }))
  }

  const isActive = (path) => location.pathname === path

  return (
    <div className="flex h-screen bg-gradient-to-br from-slate-50 via-purple-50/30 to-blue-50/30">
      <SessionExpiryWarning />
      
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
          {[...menuItems, ...(qrEnabled ? [{ title: 'QR Transactions', icon: QrCode, path: '/qr-transactions' }] : [])].map((item) => (
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
                      {item.submenu.map((subItem) => (
                        <Link
                          key={subItem.path}
                          to={subItem.path}
                          className={`flex items-center gap-3 p-2.5 rounded-lg transition-all duration-200 group ${
                            isActive(subItem.path) 
                              ? 'craftpay-gradient-btn text-white shadow-lg shadow-purple-500/30 scale-[1.02]' 
                              : 'text-gray-600 hover:bg-purple-50/70 hover:text-purple-700'
                          }`}
                        >
                          <subItem.icon size={16} className="group-hover:scale-110 transition-transform duration-200" />
                          <span className="text-sm font-medium">{subItem.title}</span>
                        </Link>
                      ))}
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
                  placeholder="Search transactions, reports..."
                  className="pl-10 bg-white/70 border-purple-200/50 focus:bg-white focus:border-purple-400 rounded-xl shadow-sm"
                />
              </div>
            </div>

            {/* Right Side Actions */}
            <div className="flex items-center gap-4 ml-6">
              {/* Notifications */}
              <button className="relative p-2.5 text-gray-600 hover:text-purple-600 hover:bg-purple-50 rounded-xl transition-all shadow-sm hover:shadow-md">
                <Bell size={22} />
                <span className="absolute top-0.5 right-0.5 w-2 h-2 bg-red-500 rounded-full animate-pulse"></span>
              </button>

              {/* User Profile */}
              <div className="flex items-center gap-3 pl-4 border-l border-purple-200/50">
                <div className="text-right">
                  <p className="text-sm font-semibold text-gray-800">{merchantInfo.name}</p>
                  <p className="text-xs text-gray-500">{merchantInfo.email}</p>
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
  )
}
