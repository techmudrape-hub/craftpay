import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { 
  TrendingUp, DollarSign, 
  ArrowUpCircle, ArrowDownCircle, Clock, RefreshCw, Wallet, AlertTriangle, ShieldAlert
} from 'lucide-react'
import { formatCurrency } from '@/lib/utils'
import clientAPI from '@/api/client_api'
import { toast } from 'sonner'

const StatCard = ({ title, amount, trend, icon: Icon, color }) => (
  <Card className="craftpay-card hover:scale-[1.02] transition-all">
    <CardHeader className="flex flex-row items-center justify-between pb-2">
      <CardTitle className="text-sm font-semibold text-gray-700">{title}</CardTitle>
      <div className={`p-2 rounded-xl ${color} bg-opacity-10`}>
        <Icon className={`h-5 w-5 ${color}`} />
      </div>
    </CardHeader>
    <CardContent>
      <div className="text-2xl font-bold craftpay-gradient-text">{formatCurrency(amount)}</div>
      {trend && (
        <p className="text-xs text-muted-foreground mt-1">
          <span className={trend > 0 ? 'text-green-600' : 'text-red-600'}>
            {trend > 0 ? '+' : ''}{trend}%
          </span> from yesterday
        </p>
      )}
    </CardContent>
  </Card>
)

const TimeRangeStats = ({ title, data }) => (
  <Card className="craftpay-card">
    <CardHeader>
      <CardTitle className="text-lg font-semibold craftpay-gradient-text">{title}</CardTitle>
    </CardHeader>
    <CardContent>
      <div className="space-y-3">
        <div className="flex items-center justify-between p-3 bg-gradient-to-r from-green-50 to-emerald-50 rounded-xl border border-green-100">
          <span className="text-sm font-semibold text-gray-700">Payin</span>
          <span className="text-lg font-bold text-green-600">{formatCurrency(data.payin)}</span>
        </div>
        <div className="flex items-center justify-between p-3 bg-gradient-to-r from-blue-50 to-indigo-50 rounded-xl border border-blue-100">
          <span className="text-sm font-semibold text-gray-700">Payout</span>
          <span className="text-lg font-bold text-blue-600">{formatCurrency(data.payout)}</span>
        </div>
      </div>
    </CardContent>
  </Card>
)

export default function Dashboard() {
  const [loading, setLoading] = useState(true)
  const [walletData, setWalletData] = useState({
    balance: 0,
    netPayin: 0,
    grossPayin: 0,
    payinCharges: 0,
    totalPayout: 0,
    settled_balance: 0,
    unsettled_balance: 0,
    cyber_hold_amount: 0,
    total_hold_amount: 0
  })
  const [payinStats, setPayinStats] = useState({
    success: { count: 0, amount: 0 },
    pending: { count: 0, amount: 0 },
    failed: { count: 0, amount: 0 }
  })
  const [payoutStats, setPayoutStats] = useState({
    success: { count: 0, amount: 0 },
    pending: { count: 0, amount: 0 },
    failed: { count: 0, amount: 0 },
    queued: { count: 0, amount: 0 }
  })
  const [chargebackStats, setChargebackStats] = useState({
    total_amount: 0
  })
  const [timeRangeData, setTimeRangeData] = useState({
    today: { payin: 0, payout: 0 },
    yesterday: { payin: 0, payout: 0 },
    last7days: { payin: 0, payout: 0 },
    last30days: { payin: 0, payout: 0 },
  })

  useEffect(() => {
    loadDashboardData()
  }, [])

  const loadDashboardData = async () => {
    try {
      setLoading(true)
      
      // Fetch wallet data, payin stats, payout stats, and chargeback stats in parallel
      const [walletResponse, payinStatsResponse, payoutStatsResponse, chargebackStatsResponse] = await Promise.all([
        clientAPI.getWalletOverview(),
        clientAPI.getPayinStats(),
        clientAPI.getPayoutStats(),
        clientAPI.getChargebackStats()
      ])
      
      if (walletResponse.success && walletResponse.data) {
        setWalletData({
          balance: walletResponse.data.balance || 0,
          netPayin: walletResponse.data.payin_amount || 0,  // Net PayIN (after charges)
          grossPayin: walletResponse.data.gross_payin || 0,  // Gross PayIN (before charges)
          payinCharges: walletResponse.data.payin_charges || 0,  // Total charges
          totalPayout: walletResponse.data.total_settlements || 0,
          settled_balance: walletResponse.data.settled_balance || 0,  // NEW: Settled amount
          unsettled_balance: walletResponse.data.unsettled_balance || 0,  // NEW: Unsettled amount
          cyber_hold_amount: walletResponse.data.cyber_hold_amount || 0,
          total_hold_amount: walletResponse.data.total_hold_amount || 0
        })
      }
      
      if (payinStatsResponse.success) {
        setPayinStats(payinStatsResponse.stats || {
          success: { count: 0, amount: 0 },
          pending: { count: 0, amount: 0 },
          failed: { count: 0, amount: 0 }
        })
        
        // Update time range data with payin data
        if (payinStatsResponse.timeRanges) {
          setTimeRangeData(prev => ({
            today: { ...prev.today, payin: payinStatsResponse.timeRanges.today.payin },
            yesterday: { ...prev.yesterday, payin: payinStatsResponse.timeRanges.yesterday.payin },
            last7days: { ...prev.last7days, payin: payinStatsResponse.timeRanges.last7days.payin },
            last30days: { ...prev.last30days, payin: payinStatsResponse.timeRanges.last30days.payin },
          }))
        }
      }
      
      if (payoutStatsResponse.success) {
        setPayoutStats(payoutStatsResponse.stats || {
          success: { count: 0, amount: 0 },
          pending: { count: 0, amount: 0 },
          failed: { count: 0, amount: 0 },
          queued: { count: 0, amount: 0 }
        })
        
        // Update time range data with payout data
        if (payoutStatsResponse.timeRanges) {
          setTimeRangeData(prev => ({
            today: { ...prev.today, payout: payoutStatsResponse.timeRanges.today.payout },
            yesterday: { ...prev.yesterday, payout: payoutStatsResponse.timeRanges.yesterday.payout },
            last7days: { ...prev.last7days, payout: payoutStatsResponse.timeRanges.last7days.payout },
            last30days: { ...prev.last30days, payout: payoutStatsResponse.timeRanges.last30days.payout },
          }))
        }
      }

      if (chargebackStatsResponse.success) {
        setChargebackStats(chargebackStatsResponse.stats || { total_amount: 0 })
      }
    } catch (error) {
      toast.error('Failed to load dashboard data')
      console.error('Dashboard data error:', error)
    } finally {
      setLoading(false)
    }
  }

  const stats = {
    settled: walletData.balance,
    unsettled: payinStats.pending.amount,
    total: walletData.balance + payinStats.pending.amount,
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-purple-600 mx-auto"></div>
          <p className="mt-4 text-gray-600 font-medium">Loading dashboard...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold craftpay-gradient-text">
            Dashboard
          </h1>
          <p className="text-gray-600 mt-1">Welcome back! Here's your payment overview</p>
        </div>
        <Button onClick={loadDashboardData} className="craftpay-gradient-btn flex items-center gap-2 shadow-lg">
          <RefreshCw className="h-4 w-4" />
          Refresh
        </Button>
      </div>

      {/* Main Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* First Box: Net PayIN with deductions */}
        <Card className="craftpay-card hover:scale-[1.02] transition-all border-2 border-green-200">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-semibold text-gray-700">Net PayIN</CardTitle>
            <div className="p-2 rounded-xl bg-green-100">
              <TrendingUp className="h-5 w-5 text-green-600" />
            </div>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-700">{formatCurrency(walletData.netPayin)}</div>
            <p className="text-xs text-gray-500 mt-2 font-medium">
              Gross: {formatCurrency(walletData.grossPayin)} - Charges: {formatCurrency(walletData.payinCharges)}
            </p>
          </CardContent>
        </Card>

        {/* Second Box: Total PayIN (Gross) */}
        <Card className="craftpay-card hover:scale-[1.02] transition-all border-2 border-blue-200">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-semibold text-gray-700">Total PayIN</CardTitle>
            <div className="p-2 rounded-xl bg-blue-100">
              <DollarSign className="h-5 w-5 text-blue-600" />
            </div>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-blue-700">{formatCurrency(walletData.grossPayin)}</div>
            <p className="text-xs text-gray-500 mt-2 font-medium">
              Gross amount before charges
            </p>
          </CardContent>
        </Card>

        {/* Third Box: Total Payout */}
        <Card className="craftpay-card hover:scale-[1.02] transition-all border-2 border-purple-200">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-semibold text-gray-700">Total Payout</CardTitle>
            <div className="p-2 rounded-xl bg-purple-100">
              <ArrowDownCircle className="h-5 w-5 text-purple-600" />
            </div>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-purple-700">{formatCurrency(walletData.totalPayout)}</div>
            <p className="text-xs text-gray-500 mt-2 font-medium">
              Total settled to bank
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Wallet Balance Cards - Settled, Unsettled, Chargebacks, Cyber Hold, Total Hold */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <Card className="craftpay-card border-2 border-green-200 bg-gradient-to-br from-green-50 to-white hover:scale-[1.02] transition-all">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-semibold text-gray-700 flex items-center gap-2">
              <div className="p-2 rounded-xl bg-green-100">
                <Wallet className="h-4 w-4 text-green-600" />
              </div>
              Settled Balance
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-bold text-green-700">
              {formatCurrency(walletData.settled_balance)}
            </p>
            <p className="text-xs text-gray-500 mt-2 font-medium">Available for payout - approved by admin</p>
          </CardContent>
        </Card>

        <Card className="craftpay-card border-2 border-orange-200 bg-gradient-to-br from-orange-50 to-white hover:scale-[1.02] transition-all">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-semibold text-gray-700 flex items-center gap-2">
              <div className="p-2 rounded-xl bg-orange-100">
                <Clock className="h-4 w-4 text-orange-600" />
              </div>
              Unsettled Balance
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-bold text-orange-700">
              {formatCurrency(walletData.unsettled_balance)}
            </p>
            <p className="text-xs text-gray-500 mt-2 font-medium">Pending admin settlement approval</p>
          </CardContent>
        </Card>




      </div>

      {/* Payin/Payout Tabs */}
      <Tabs defaultValue="payin" className="w-full">
        <TabsList className="grid w-full max-w-md grid-cols-2 glass-effect">
          <TabsTrigger value="payin" className="data-[state=active]:craftpay-gradient-btn data-[state=active]:text-white">Payin</TabsTrigger>
          <TabsTrigger value="payout" className="data-[state=active]:craftpay-gradient-btn data-[state=active]:text-white">Payout</TabsTrigger>
        </TabsList>
        
        <TabsContent value="payin" className="space-y-4 mt-6">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <TimeRangeStats title="Today" data={timeRangeData.today} />
            <TimeRangeStats title="Yesterday" data={timeRangeData.yesterday} />
            <TimeRangeStats title="Last 7 Days" data={timeRangeData.last7days} />
            <TimeRangeStats title="Last 30 Days" data={timeRangeData.last30days} />
          </div>

          <Card className="craftpay-card">
            <CardHeader>
              <CardTitle className="craftpay-gradient-text">Payin Transactions</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="p-4 bg-gradient-to-br from-green-50 to-emerald-50 rounded-xl border-2 border-green-200 hover:scale-105 transition-transform">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-semibold text-gray-700">Success</p>
                      <p className="text-2xl font-bold text-green-600">{payinStats.success.count}</p>
                    </div>
                    <div className="p-2 rounded-xl bg-green-100">
                      <ArrowUpCircle className="h-8 w-8 text-green-600" />
                    </div>
                  </div>
                  <p className="text-xs text-gray-600 mt-2 font-medium">{formatCurrency(payinStats.success.amount)}</p>
                </div>
                <div className="p-4 bg-gradient-to-br from-yellow-50 to-amber-50 rounded-xl border-2 border-yellow-200 hover:scale-105 transition-transform">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-semibold text-gray-700">Pending</p>
                      <p className="text-2xl font-bold text-yellow-600">{payinStats.pending.count}</p>
                    </div>
                    <div className="p-2 rounded-xl bg-yellow-100">
                      <Clock className="h-8 w-8 text-yellow-600" />
                    </div>
                  </div>
                  <p className="text-xs text-gray-600 mt-2 font-medium">{formatCurrency(payinStats.pending.amount)}</p>
                </div>
                <div className="p-4 bg-gradient-to-br from-red-50 to-rose-50 rounded-xl border-2 border-red-200 hover:scale-105 transition-transform">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-semibold text-gray-700">Failed</p>
                      <p className="text-2xl font-bold text-red-600">{payinStats.failed.count}</p>
                    </div>
                    <div className="p-2 rounded-xl bg-red-100">
                      <ArrowDownCircle className="h-8 w-8 text-red-600" />
                    </div>
                  </div>
                  <p className="text-xs text-gray-600 mt-2 font-medium">{formatCurrency(payinStats.failed.amount)}</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="payout" className="space-y-4 mt-6">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <TimeRangeStats title="Today" data={timeRangeData.today} />
            <TimeRangeStats title="Yesterday" data={timeRangeData.yesterday} />
            <TimeRangeStats title="Last 7 Days" data={timeRangeData.last7days} />
            <TimeRangeStats title="Last 30 Days" data={timeRangeData.last30days} />
          </div>

          <Card className="craftpay-card">
            <CardHeader>
              <CardTitle className="craftpay-gradient-text">Payout Transactions</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div className="p-4 bg-gradient-to-br from-green-50 to-emerald-50 rounded-xl border-2 border-green-200 hover:scale-105 transition-transform">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-semibold text-gray-700">Success</p>
                      <p className="text-2xl font-bold text-green-600">{payoutStats.success.count}</p>
                    </div>
                    <div className="p-2 rounded-xl bg-green-100">
                      <ArrowUpCircle className="h-8 w-8 text-green-600" />
                    </div>
                  </div>
                  <p className="text-xs text-gray-600 mt-2 font-medium">{formatCurrency(payoutStats.success.amount)}</p>
                </div>
                <div className="p-4 bg-gradient-to-br from-blue-50 to-indigo-50 rounded-xl border-2 border-blue-200 hover:scale-105 transition-transform">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-semibold text-gray-700">Queued</p>
                      <p className="text-2xl font-bold text-blue-600">{payoutStats.queued.count}</p>
                    </div>
                    <div className="p-2 rounded-xl bg-blue-100">
                      <Clock className="h-8 w-8 text-blue-600" />
                    </div>
                  </div>
                  <p className="text-xs text-gray-600 mt-2 font-medium">{formatCurrency(payoutStats.queued.amount)}</p>
                </div>
                <div className="p-4 bg-gradient-to-br from-yellow-50 to-amber-50 rounded-xl border-2 border-yellow-200 hover:scale-105 transition-transform">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-semibold text-gray-700">Pending</p>
                      <p className="text-2xl font-bold text-yellow-600">{payoutStats.pending.count}</p>
                    </div>
                    <div className="p-2 rounded-xl bg-yellow-100">
                      <Clock className="h-8 w-8 text-yellow-600" />
                    </div>
                  </div>
                  <p className="text-xs text-gray-600 mt-2 font-medium">{formatCurrency(payoutStats.pending.amount)}</p>
                </div>
                <div className="p-4 bg-gradient-to-br from-red-50 to-rose-50 rounded-xl border-2 border-red-200 hover:scale-105 transition-transform">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-semibold text-gray-700">Failed</p>
                      <p className="text-2xl font-bold text-red-600">{payoutStats.failed.count}</p>
                    </div>
                    <div className="p-2 rounded-xl bg-red-100">
                      <ArrowDownCircle className="h-8 w-8 text-red-600" />
                    </div>
                  </div>
                  <p className="text-xs text-gray-600 mt-2 font-medium">{formatCurrency(payoutStats.failed.amount)}</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
