import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Lock, User, Shield, ArrowRight, Activity, PieChart, Users } from 'lucide-react'
import { toast } from 'sonner'
import adminAPI from '@/api/admin_api'
import { usePageTitle } from '@/hooks/usePageTitle'

export default function Login() {
  usePageTitle('CraftPay Admin Login')
  const navigate = useNavigate()
  const [credentials, setCredentials] = useState({ adminId: '', password: '' })
  const [loading, setLoading] = useState(false)

  const handleLogin = async (e) => {
    e.preventDefault()
    if (!credentials.adminId || !credentials.password) {
      toast.error('Please fill all fields')
      return
    }
    setLoading(true)
    try {
      const response = await adminAPI.login(credentials.adminId, credentials.password)
      if (response.success) {
        toast.success('Login successful! Welcome back.')
        navigate('/')
      }
    } catch (error) {
      toast.error(error.message || 'Login failed. Please try again.')
      setCredentials({ ...credentials, password: '' })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
      <div className="w-full max-w-5xl bg-white rounded-[2.5rem] shadow-[0_20px_60px_-15px_rgba(0,0,0,0.1)] overflow-hidden flex flex-col lg:flex-row border border-slate-100 min-h-[600px]">
        
        {/* Left Side: Branding & Writing */}
        <div className="hidden lg:flex flex-col justify-center p-10 w-1/2 bg-gradient-to-br from-violet-100 via-indigo-50 to-purple-100 relative overflow-hidden">
          {/* Decorative shapes */}
          <div className="absolute top-0 right-0 w-[40rem] h-[40rem] bg-violet-200/50 rounded-full blur-3xl -translate-y-1/2 translate-x-1/3"></div>
          <div className="absolute bottom-0 left-0 w-[30rem] h-[30rem] bg-indigo-200/50 rounded-full blur-3xl translate-y-1/3 -translate-x-1/4"></div>
          <div className="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-[0.25] mix-blend-overlay"></div>

          <div className="relative z-10">
            <h1 className="text-4xl font-extrabold text-slate-900 tracking-tight leading-tight mb-4">
              Command Center for <span className="text-violet-600">CraftPay</span>
            </h1>
            <p className="text-base text-slate-700 mb-8 leading-relaxed max-w-md font-medium">
              Oversee your entire payment ecosystem, manage merchants, and monitor real-time analytics all in one highly secure platform.
            </p>

            <div className="space-y-4">
              <div className="flex items-center gap-4 bg-white/60 backdrop-blur-sm p-4 rounded-2xl shadow-sm border border-white/50 transition-transform hover:scale-105">
                <div className="p-3 bg-violet-100 rounded-xl text-violet-600">
                  <Activity className="w-6 h-6" />
                </div>
                <div>
                  <h3 className="font-bold text-slate-900">Real-time Monitoring</h3>
                  <p className="text-sm text-slate-600">Track all transactions as they happen.</p>
                </div>
              </div>

              <div className="flex items-center gap-4 bg-white/60 backdrop-blur-sm p-4 rounded-2xl shadow-sm border border-white/50 transition-transform hover:scale-105">
                <div className="p-3 bg-indigo-100 rounded-xl text-indigo-600">
                  <Users className="w-6 h-6" />
                </div>
                <div>
                  <h3 className="font-bold text-slate-900">Merchant Management</h3>
                  <p className="text-sm text-slate-600">Onboard and manage merchant accounts easily.</p>
                </div>
              </div>

              <div className="flex items-center gap-4 bg-white/60 backdrop-blur-sm p-4 rounded-2xl shadow-sm border border-white/50 transition-transform hover:scale-105">
                <div className="p-3 bg-purple-100 rounded-xl text-purple-600">
                  <PieChart className="w-6 h-6" />
                </div>
                <div>
                  <h3 className="font-bold text-slate-900">Advanced Analytics</h3>
                  <p className="text-sm text-slate-600">Deep insights into platform performance.</p>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Right Side: Login Form */}
        <div className="w-full lg:w-1/2 p-8 sm:p-12 flex flex-col justify-center relative bg-white">
          <div className="max-w-sm w-full mx-auto">
            
            {/* Logo */}
            <div className="flex justify-center mb-8">
              <img src="/craftpay.png" alt="CraftPay Logo" className="h-16 sm:h-20 object-contain drop-shadow-sm" />
            </div>

            <div className="text-center mb-8">
              <h2 className="text-2xl font-bold text-slate-900 mb-2">Admin Portal</h2>
              <p className="text-sm text-slate-500 font-medium">Please sign in to access the dashboard</p>
            </div>

            <form onSubmit={handleLogin} className="space-y-5">
              <div className="space-y-2">
                <Label className="text-slate-700 font-bold text-xs uppercase tracking-wider ml-1">Admin ID</Label>
                <div className="relative group">
                  <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none text-slate-400 group-focus-within:text-violet-600 transition-colors">
                    <User className="h-5 w-5" />
                  </div>
                  <Input
                    type="text"
                    placeholder="Enter your Admin ID"
                    value={credentials.adminId}
                    onChange={(e) => setCredentials({ ...credentials, adminId: e.target.value })}
                    className="pl-12 h-14 bg-slate-50 border-slate-200 text-slate-900 placeholder:text-slate-400 focus:bg-white focus:border-violet-500 focus:ring-2 focus:ring-violet-200 rounded-xl transition-all text-base shadow-sm"
                    required
                    disabled={loading}
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label className="text-slate-700 font-bold text-xs uppercase tracking-wider ml-1">Password</Label>
                <div className="relative group">
                  <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none text-slate-400 group-focus-within:text-violet-600 transition-colors">
                    <Lock className="h-5 w-5" />
                  </div>
                  <Input
                    type="password"
                    placeholder="••••••••"
                    value={credentials.password}
                    onChange={(e) => setCredentials({ ...credentials, password: e.target.value })}
                    className="pl-12 h-14 bg-slate-50 border-slate-200 text-slate-900 placeholder:text-slate-400 focus:bg-white focus:border-violet-500 focus:ring-2 focus:ring-violet-200 rounded-xl transition-all text-base shadow-sm"
                    required
                    disabled={loading}
                  />
                </div>
              </div>

              <Button
                type="submit"
                disabled={loading}
                className="w-full h-14 bg-violet-600 hover:bg-violet-700 text-white font-bold text-lg rounded-xl shadow-[0_4px_14px_0_rgba(139,92,246,0.39)] hover:shadow-[0_6px_20px_rgba(139,92,246,0.23)] transition-all mt-8 group"
              >
                {loading ? (
                  <span className="flex items-center justify-center gap-3">
                    <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white"></div>
                    Authenticating...
                  </span>
                ) : (
                  <span className="flex items-center justify-center gap-2">
                    Sign In
                    <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
                  </span>
                )}
              </Button>
            </form>

            <div className="mt-8 pt-6 border-t border-slate-100 flex items-center justify-center gap-2 text-slate-500 text-xs font-medium">
              <Shield className="w-4 h-4 text-violet-500" />
              Secure End-to-End Encrypted Session
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
