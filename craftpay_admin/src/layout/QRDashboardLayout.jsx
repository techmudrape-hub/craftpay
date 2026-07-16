import { useState } from 'react'
import { Outlet, useNavigate, Link, useLocation } from 'react-router-dom'
import { 
  LogOut, ChevronDown, ChevronLeft, ChevronRight, QrCode, FileText, Wallet, User
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { toast } from 'sonner'

const menuItems = [
  {
    title: 'QR Collection',
    icon: QrCode,
    submenu: [
      { title: 'QR Service Routing', icon: QrCode, path: '/qrlogin/panel/service-routing' },
      { title: 'QR Transactions', icon: FileText, path: '/qrlogin/panel/transactions' },
    ]
  },
  {
    title: 'Payin Transactions',
    icon: FileText,
    path: '/qrlogin/panel/payin-transactions'
  },
  {
    title: 'Settle Wallet',
    icon: Wallet,
    path: '/qrlogin/panel/settle-wallet'
  },
  {
    title: 'User Transaction Summary',
    icon: User,
    path: '/qrlogin/panel/user-transaction-summary'
  }
]

export default function QRDashboardLayout() {
  const navigate = useNavigate()
  const location = useLocation()
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [expandedMenus, setExpandedMenus] = useState({ 'QR Collection': true })
  
  const handleLogout = () => {
    localStorage.removeItem('qrAdminToken')
    localStorage.removeItem('qrAdminId')
    toast.success('Logged out successfully')
    navigate('/qrlogin', { replace: true })
  }

  const toggleMenu = (title) => {
    setExpandedMenus(prev => ({ ...prev, [title]: !prev[title] }))
  }

  const isActive = (path) => location.pathname === path

  return (
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
                        const ItemComponent = Link
                        return (
                          <ItemComponent
                            key={subItem.path}
                            to={subItem.path}
                            className={`flex items-center gap-3 p-2.5 rounded-lg transition-all duration-200 group ${
                              isActive(subItem.path) 
                                ? 'orchpay-gradient-btn text-white shadow-lg shadow-purple-500/30 scale-[1.02]' 
                                : 'text-gray-600 hover:bg-purple-50/70 hover:text-purple-700'
                            }`}
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
                  className={`w-full flex items-center ${sidebarOpen ? 'justify-start' : 'justify-center'} p-3 rounded-xl transition-all duration-200 group relative overflow-hidden ${
                    isActive(item.path)
                      ? 'bg-purple-100/50 text-purple-700'
                      : 'hover:bg-purple-50/70 text-gray-700 hover:text-purple-700'
                  }`}
                  title={!sidebarOpen ? item.title : ''}
                >
                  <div className={`flex items-center gap-3 relative z-10 ${!sidebarOpen && 'justify-center w-full'}`}>
                    <div className={`p-2 rounded-lg transition-all ${
                      isActive(item.path)
                        ? 'bg-gradient-to-br from-purple-500 to-blue-500 text-white shadow-lg shadow-purple-500/30'
                        : 'bg-gradient-to-br from-purple-50 to-blue-50 group-hover:from-purple-100 group-hover:to-blue-100'
                    }`}>
                      <item.icon size={18} className={`${isActive(item.path) ? 'text-white' : 'text-purple-600 group-hover:text-purple-700'} transition-colors`} />
                    </div>
                    {sidebarOpen && <span className={`font-semibold text-sm ${isActive(item.path) ? 'text-purple-700' : ''}`}>{item.title}</span>}
                  </div>
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
            <div className="flex-1 font-semibold text-xl text-purple-700">QR Administrator Portal</div>

            {/* Right Side Actions */}
            <div className="flex items-center gap-4 ml-6">
              {/* User Profile */}
              <div className="flex items-center gap-3 pl-4 border-l border-purple-200/50">
                <div className="text-right">
                  <p className="text-sm font-semibold text-gray-800">QR Admin</p>
                  <p className="text-xs text-gray-500">{localStorage.getItem('qrAdminId') || 'Admin'}</p>
                </div>
                <div className="w-11 h-11 orchpay-gradient-btn rounded-xl flex items-center justify-center text-white font-semibold shadow-lg shadow-purple-500/30">
                  <QrCode size={20} />
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
