import { useState, useEffect } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Lock, User, Shield, ArrowRight, Zap, Globe, DollarSign } from 'lucide-react'
import { toast } from 'sonner'
import clientAPI from '@/api/client_api'
import { usePageTitle } from '@/hooks/usePageTitle'

export default function Login() {
  usePageTitle('CraftPay Merchant Login')
  const navigate = useNavigate()
  const location = useLocation()
  const [credentials, setCredentials] = useState({ merchantId: '', password: '' })
  const [loading, setLoading] = useState(false)
  const from = location.state?.from?.pathname || '/'

  useEffect(() => {
    if (clientAPI.isAuthenticated()) {
      navigate(from, { replace: true })
    }
  }, [navigate, from])

  const handleLogin = async (e) => {
    e.preventDefault()
    if (!credentials.merchantId || !credentials.password) {
      toast.error('Please fill all fields')
      return
    }
    setLoading(true)
    try {
      const response = await clientAPI.login(credentials.merchantId, credentials.password)
      if (response.success) {
        toast.success(`Welcome back, ${response.merchantName}!`)
        navigate(from, { replace: true })
      }
    } catch (error) {
      toast.error(error.message || 'Login failed. Please check your credentials.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
      <div className="w-full max-w-5xl bg-white rounded-[2.5rem] shadow-[0_20px_60px_-15px_rgba(0,0,0,0.1)] overflow-hidden flex flex-col lg:flex-row-reverse border border-slate-100 min-h-[600px]">
        
        {/* Right Side (Visual): Branding & Writing */}
        <div className="hidden lg:flex flex-col justify-center p-10 w-1/2 bg-gradient-to-br from-indigo-100 via-purple-50 to-violet-100 relative overflow-hidden">
          {/* Decorative shapes */}
          <div className="absolute top-0 left-0 w-[40rem] h-[40rem] bg-indigo-200/50 rounded-full blur-3xl -translate-y-1/2 -translate-x-1/3"></div>
          <div className="absolute bottom-0 right-0 w-[30rem] h-[30rem] bg-violet-200/50 rounded-full blur-3xl translate-y-1/3 translate-x-1/4"></div>
          <div className="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-[0.25] mix-blend-overlay"></div>

          <div className="relative z-10">
            <h1 className="text-4xl font-extrabold text-slate-900 tracking-tight leading-tight mb-4">
              Grow Your Business with <span className="text-indigo-600">CraftPay</span>
            </h1>
            <p className="text-base text-slate-700 mb-8 leading-relaxed max-w-md font-medium">
              Seamlessly accept payments, manage your settlements, and scale your operations with our premium merchant portal.
            </p>

            <div className="space-y-4">
              <div className="flex items-center gap-4 bg-white/60 backdrop-blur-sm p-4 rounded-2xl shadow-sm border border-white/50 transition-transform hover:scale-105">
                <div className="p-3 bg-indigo-100 rounded-xl text-indigo-600">
                  <Zap className="w-6 h-6" />
                </div>
                <div>
                  <h3 className="font-bold text-slate-900">Lightning Fast</h3>
                  <p className="text-sm text-slate-600">Instant settlements to your bank account.</p>
                </div>
              </div>

              <div className="flex items-center gap-4 bg-white/60 backdrop-blur-sm p-4 rounded-2xl shadow-sm border border-white/50 transition-transform hover:scale-105">
                <div className="p-3 bg-violet-100 rounded-xl text-violet-600">
                  <Globe className="w-6 h-6" />
                </div>
                <div>
                  <h3 className="font-bold text-slate-900">Global Reach</h3>
                  <p className="text-sm text-slate-600">Accept payments from anywhere in the world.</p>
                </div>
              </div>

              <div className="flex items-center gap-4 bg-white/60 backdrop-blur-sm p-4 rounded-2xl shadow-sm border border-white/50 transition-transform hover:scale-105">
                <div className="p-3 bg-purple-100 rounded-xl text-purple-600">
                  <DollarSign className="w-6 h-6" />
                </div>
                <div>
                  <h3 className="font-bold text-slate-900">Low Fees</h3>
                  <p className="text-sm text-slate-600">Industry-leading rates to maximize your profit.</p>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Left Side (Form): Login */}
        <div className="w-full lg:w-1/2 p-8 sm:p-12 flex flex-col justify-center relative bg-white">
          <div className="max-w-sm w-full mx-auto">
            
            {/* Logo */}
            <div className="flex justify-center mb-8">
              <img src="/craftpay.png" alt="CraftPay Logo" className="h-16 sm:h-20 object-contain drop-shadow-sm" />
            </div>

            <div className="text-center mb-8">
              <h2 className="text-2xl font-bold text-slate-900 mb-2">Merchant Portal</h2>
              <p className="text-sm text-slate-500 font-medium">Please sign in to access your account</p>
            </div>

            <form onSubmit={handleLogin} className="space-y-5">
              <div className="space-y-2">
                <Label className="text-slate-700 font-bold text-xs uppercase tracking-wider ml-1">Merchant ID</Label>
                <div className="relative group">
                  <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none text-slate-400 group-focus-within:text-indigo-600 transition-colors">
                    <User className="h-5 w-5" />
                  </div>
                  <Input
                    type="text"
                    placeholder="Enter your Merchant ID"
                    value={credentials.merchantId}
                    onChange={(e) => setCredentials({ ...credentials, merchantId: e.target.value })}
                    className="pl-12 h-14 bg-slate-50 border-slate-200 text-slate-900 placeholder:text-slate-400 focus:bg-white focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200 rounded-xl transition-all text-base shadow-sm"
                    required
                    disabled={loading}
                  />
                </div>
              </div>

              <div className="space-y-2">
                <div className="flex justify-between items-center ml-1">
                  <Label className="text-slate-700 font-bold text-xs uppercase tracking-wider">Password</Label>
                </div>
                <div className="relative group">
                  <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none text-slate-400 group-focus-within:text-indigo-600 transition-colors">
                    <Lock className="h-5 w-5" />
                  </div>
                  <Input
                    type="password"
                    placeholder="••••••••"
                    value={credentials.password}
                    onChange={(e) => setCredentials({ ...credentials, password: e.target.value })}
                    className="pl-12 h-14 bg-slate-50 border-slate-200 text-slate-900 placeholder:text-slate-400 focus:bg-white focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200 rounded-xl transition-all text-base shadow-sm"
                    required
                    disabled={loading}
                  />
                </div>
              </div>

              <div className="flex items-center justify-between text-sm pl-1">
                <label className="flex items-center gap-2 cursor-pointer group">
                  <input type="checkbox" className="w-4 h-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500/50 focus:ring-offset-0 transition-all" disabled={loading} />
                  <span className="text-slate-600 font-medium group-hover:text-slate-900 transition-colors">Remember me</span>
                </label>
                <a href="#" className="text-indigo-600 hover:text-indigo-700 font-semibold transition-colors">
                  Forgot Password?
                </a>
              </div>

              <Button
                type="submit"
                disabled={loading}
                className="w-full h-14 bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-lg rounded-xl shadow-[0_4px_14px_0_rgba(79,70,229,0.39)] hover:shadow-[0_6px_20px_rgba(79,70,229,0.23)] transition-all mt-8 group"
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
              <Shield className="w-4 h-4 text-indigo-500" />
              Secure End-to-End Encrypted Session
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
