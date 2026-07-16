import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Lock, User, QrCode, ShieldCheck } from 'lucide-react'
import { toast } from 'sonner'
import { usePageTitle } from '@/hooks/usePageTitle'

const BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5000/api'

export default function QRLogin() {
  usePageTitle('QR Admin Login')
  const navigate = useNavigate()
  const [credentials, setCredentials] = useState({ 
    adminId: '', 
    password: ''
  })
  const [loading, setLoading] = useState(false)

  const handleLogin = async (e) => {
    e.preventDefault()
    
    if (!credentials.adminId || !credentials.password) {
      toast.error('Please fill all fields')
      return
    }

    setLoading(true)
    try {
      const response = await fetch(`${BASE}/qr/admin/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(credentials)
      })
      const data = await response.json()

      if (data.success) {
        localStorage.setItem('qrAdminToken', data.token)
        localStorage.setItem('qrAdminId', data.adminId)
        toast.success('Login successful! Welcome QR Admin.')
        navigate('/qrlogin/panel')
      } else {
        throw new Error(data.message || 'Login failed')
      }
    } catch (error) {
      toast.error(error.message || 'Login failed. Please try again.')
      setCredentials({ ...credentials, password: '' })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-900 via-purple-900 to-indigo-900 p-4">
      <div className="w-full max-w-4xl grid grid-cols-1 md:grid-cols-2 gap-0 items-stretch shadow-2xl rounded-2xl overflow-hidden bg-white">
        
        {/* Left Side */}
        <div className="hidden md:flex flex-col justify-between p-10 bg-gradient-to-br from-purple-600 to-blue-600 text-white">
          <div>
            <div className="flex items-center gap-2 mb-8">
              <div className="w-12 h-12 bg-white/20 backdrop-blur-md rounded-xl flex items-center justify-center">
                <QrCode className="h-7 w-7 text-white" />
              </div>
              <span className="text-white font-bold text-xl tracking-wide">QR Portal</span>
            </div>
            
            <h1 className="text-4xl font-extrabold mb-4 leading-tight">
              Manage QR<br />Routing & TXNs
            </h1>
            <p className="text-white/80 text-base leading-relaxed mb-8">
              Dedicated portal for managing merchant QR allocations and approving collected payments securely.
            </p>
          </div>
          <div className="border-t border-white/20 pt-6">
            <div className="flex items-center gap-3">
              <ShieldCheck className="w-8 h-8 opacity-80" />
              <p className="text-sm opacity-80 font-medium">Restricted Access Area</p>
            </div>
          </div>
        </div>

        {/* Right Side */}
        <div className="flex items-center justify-center p-8 md:p-12">
          <div className="w-full max-w-sm">
            <div className="text-center mb-8">
              <div className="inline-flex items-center justify-center w-16 h-16 bg-purple-100 rounded-full mb-4">
                <QrCode className="h-8 w-8 text-purple-600" />
              </div>
              <h2 className="text-3xl font-bold text-gray-900 mb-2">QR Admin</h2>
              <p className="text-gray-500 text-sm">Sign in to the dedicated QR console</p>
            </div>

            <form onSubmit={handleLogin} className="space-y-5">
              <div className="space-y-2">
                <Label htmlFor="adminId" className="text-gray-700 font-semibold text-sm">
                  Admin ID
                </Label>
                <div className="relative">
                  <User className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-gray-400" />
                  <Input
                    id="adminId"
                    type="text"
                    placeholder="Enter ID"
                    value={credentials.adminId}
                    onChange={(e) => setCredentials({ ...credentials, adminId: e.target.value })}
                    className="pl-10 h-12 bg-gray-50 border-gray-200 focus:border-purple-500 focus:ring-purple-500 rounded-xl"
                    required
                    disabled={loading}
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="password" className="text-gray-700 font-semibold text-sm">
                  Password
                </Label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-gray-400" />
                  <Input
                    id="password"
                    type="password"
                    placeholder="••••••••"
                    value={credentials.password}
                    onChange={(e) => setCredentials({ ...credentials, password: e.target.value })}
                    className="pl-10 h-12 bg-gray-50 border-gray-200 focus:border-purple-500 focus:ring-purple-500 rounded-xl"
                    required
                    disabled={loading}
                  />
                </div>
              </div>

              <Button 
                type="submit" 
                disabled={loading}
                className="w-full h-12 bg-gradient-to-r from-purple-600 to-blue-600 text-white font-bold text-base rounded-xl shadow-lg hover:shadow-purple-500/30 transition-all mt-6"
              >
                {loading ? 'Authenticating...' : 'Sign In'}
              </Button>
            </form>
          </div>
        </div>
      </div>
    </div>
  )
}
