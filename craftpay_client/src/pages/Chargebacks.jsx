import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { 
  Download, FileText, AlertTriangle, Search, Filter, 
  Calendar, RefreshCw, TrendingDown, CheckCircle, History, XCircle
} from 'lucide-react'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { toast } from 'sonner'
import clientAPI from '@/api/client_api'
import { formatCurrency } from '@/lib/utils'
import { useNavigate } from 'react-router-dom'

export default function Chargebacks() {
  const navigate = useNavigate()
  const [chargebacks, setChargebacks] = useState([])
  const [stats, setStats] = useState({
    total_count: 0,
    total_amount: 0,
    month_count: 0,
    month_amount: 0,
    pending_count: 0,
    pending_amount: 0,
    accepted_count: 0,
    accepted_amount: 0
  })
  const [loading, setLoading] = useState(false)
  const [downloading, setDownloading] = useState(false)
  const [acceptingId, setAcceptingId] = useState(null)
  
  // Filters
  const [filters, setFilters] = useState({
    from_date: '',
    to_date: '',
    transaction_id: '',
    status: '',
    page: 1,
    per_page: 20
  })
  
  const [pagination, setPagination] = useState({
    page: 1,
    per_page: 20,
    total_records: 0,
    total_pages: 0,
    has_next: false,
    has_prev: false
  })

  useEffect(() => {
    loadStats()
    loadChargebacks()
  }, [])

  useEffect(() => {
    loadChargebacks()
  }, [filters])

  const loadStats = async () => {
    try {
      const response = await clientAPI.getChargebackStats()
      if (response.success) {
        setStats(response.stats || stats)
      }
    } catch (error) {
      console.error('Load stats error:', error)
    }
  }

  const loadChargebacks = async () => {
    try {
      setLoading(true)
      const response = await clientAPI.getMerchantChargebacks(filters)
      if (response.success) {
        setChargebacks(response.chargebacks || [])
        setPagination(response.pagination || pagination)
      }
    } catch (error) {
      console.error('Load chargebacks error:', error)
      toast.error('Failed to load chargebacks')
    } finally {
      setLoading(false)
    }
  }

  const handleDownloadReport = async () => {
    try {
      setDownloading(true)
      await clientAPI.downloadChargebackReport(filters)
      toast.success('Report downloaded successfully')
    } catch (error) {
      console.error('Download error:', error)
      toast.error('Failed to download report')
    } finally {
      setDownloading(false)
    }
  }

  const handleFilterChange = (key, value) => {
    setFilters(prev => ({ ...prev, [key]: value, page: 1 }))
  }

  const handlePageChange = (newPage) => {
    setFilters(prev => ({ ...prev, page: newPage }))
  }

  const handleResetFilters = () => {
    setFilters({
      from_date: '',
      to_date: '',
      transaction_id: '',
      status: '',
      page: 1,
      per_page: 20
    })
  }

  const handleAcceptChargeback = async (chargebackId) => {
    if (!confirm('Are you sure you want to accept this chargeback? The amount will be deducted from your unsettled balance.')) {
      return
    }

    try {
      setAcceptingId(chargebackId)
      const response = await clientAPI.acceptChargeback(chargebackId)
      
      if (response.success) {
        toast.success(response.message || 'Chargeback accepted successfully')
        // Reload data
        loadStats()
        loadChargebacks()
      } else {
        toast.error(response.message || 'Failed to accept chargeback')
      }
    } catch (error) {
      console.error('Accept chargeback error:', error)
      toast.error(error.message || 'Failed to accept chargeback')
    } finally {
      setAcceptingId(null)
    }
  }

  const handleViewDeductions = () => {
    navigate('/chargeback-deductions')
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold bg-gradient-to-r from-red-600 to-orange-600 bg-clip-text text-transparent">
          Chargebacks
        </h1>
        <p className="text-gray-600 mt-1">View and download your chargeback records</p>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <Card className="border-2 border-red-200 bg-gradient-to-br from-red-50 to-white">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-gray-600 flex items-center gap-2">
              <TrendingDown className="h-4 w-4 text-red-600" />
              Total Chargebacks
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-bold text-red-700">{stats.total_count}</p>
            <p className="text-xs text-gray-500 mt-2">All time</p>
          </CardContent>
        </Card>

        <Card className="border-2 border-orange-200 bg-gradient-to-br from-orange-50 to-white">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-gray-600 flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-orange-600" />
              Total Hold Amount
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-bold text-orange-700">{formatCurrency(stats.total_amount)}</p>
            <p className="text-xs text-gray-500 mt-2">All time</p>
          </CardContent>
        </Card>

        <Card className="border-2 border-yellow-200 bg-gradient-to-br from-yellow-50 to-white">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-gray-600 flex items-center gap-2">
              <Calendar className="h-4 w-4 text-yellow-600" />
              Pending Chargebacks
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-bold text-yellow-700">{stats.pending_count}</p>
            <p className="text-sm text-yellow-600 mt-2">{formatCurrency(stats.pending_amount)}</p>
          </CardContent>
        </Card>

        <Card className="border-2 border-green-200 bg-gradient-to-br from-green-50 to-white">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-gray-600 flex items-center gap-2">
              <CheckCircle className="h-4 w-4 text-green-600" />
              Accepted Chargebacks
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-bold text-green-700">{stats.accepted_count}</p>
            <p className="text-sm text-green-600 mt-2">{formatCurrency(stats.accepted_amount)}</p>
          </CardContent>
        </Card>
      </div>

      {/* Action Buttons */}
      <div className="flex gap-3">
        <Button 
          onClick={handleViewDeductions}
          className="bg-purple-600 hover:bg-purple-700"
        >
          <History className="h-4 w-4 mr-2" />
          View Deduction History
        </Button>
      </div>

      {/* Filters */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Filter className="h-5 w-5 text-blue-600" />
            Filter Chargebacks
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div>
              <Label>From Date</Label>
              <Input
                type="date"
                value={filters.from_date}
                onChange={(e) => handleFilterChange('from_date', e.target.value)}
              />
            </div>

            <div>
              <Label>To Date</Label>
              <Input
                type="date"
                value={filters.to_date}
                onChange={(e) => handleFilterChange('to_date', e.target.value)}
              />
            </div>

            <div>
              <Label>Transaction/Order ID</Label>
              <Input
                placeholder="Search..."
                value={filters.transaction_id}
                onChange={(e) => handleFilterChange('transaction_id', e.target.value)}
              />
            </div>

            <div>
              <Label>Status</Label>
              <Select value={filters.status || 'all'} onValueChange={(value) => handleFilterChange('status', value === 'all' ? '' : value)}>
                <SelectTrigger>
                  <SelectValue placeholder="All Status" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Status</SelectItem>
                  <SelectItem value="SUCCESS">SUCCESS</SelectItem>
                  <SelectItem value="PENDING">PENDING</SelectItem>
                  <SelectItem value="FAILED">FAILED</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="flex gap-2 mt-4">
            <Button onClick={loadChargebacks} variant="outline">
              <Search className="h-4 w-4 mr-2" />
              Search
            </Button>
            <Button onClick={handleResetFilters} variant="outline">
              <RefreshCw className="h-4 w-4 mr-2" />
              Reset
            </Button>
            <Button 
              onClick={handleDownloadReport} 
              disabled={downloading}
              className="bg-green-600 hover:bg-green-700 ml-auto"
            >
              {downloading ? (
                <>
                  <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                  Downloading...
                </>
              ) : (
                <>
                  <Download className="h-4 w-4 mr-2" />
                  Download Report
                </>
              )}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Chargebacks Table */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <span className="flex items-center gap-2">
              <FileText className="h-5 w-5 text-red-600" />
              Chargeback Records
            </span>
            <span className="text-sm font-normal text-gray-500">
              Total: {pagination.total_records} records
            </span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="text-center py-12">
              <RefreshCw className="h-8 w-8 animate-spin mx-auto text-purple-600" />
              <p className="mt-4 text-gray-600">Loading chargebacks...</p>
            </div>
          ) : chargebacks.length === 0 ? (
            <div className="text-center py-12 text-gray-500">
              <FileText className="h-16 w-16 mx-auto mb-4 text-gray-300" />
              <p className="text-lg font-semibold">No chargeback records found</p>
              <p className="text-sm mt-2">You don't have any chargebacks yet</p>
            </div>
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Transaction ID</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Order ID</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Amount</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Acceptance</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Payment Mode</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Customer</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Mobile</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">UTR</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Date</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200">
                    {chargebacks.map((cb) => (
                      <tr key={cb.id} className="hover:bg-gray-50">
                        <td className="px-4 py-3 text-sm font-mono">{cb.transaction_id}</td>
                        <td className="px-4 py-3 text-sm font-mono">{cb.order_id}</td>
                        <td className="px-4 py-3 text-sm font-semibold text-red-600">{formatCurrency(cb.chargeback_amount)}</td>
                        <td className="px-4 py-3 text-sm">
                          <span className={`px-2 py-1 rounded-full text-xs ${
                            cb.status === 'SUCCESS' ? 'bg-green-100 text-green-700' :
                            cb.status === 'PENDING' ? 'bg-yellow-100 text-yellow-700' :
                            'bg-red-100 text-red-700'
                          }`}>
                            {cb.status}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-sm">
                          <span className={`px-2 py-1 rounded-full text-xs ${
                            cb.acceptance_status === 'ACCEPTED' ? 'bg-green-100 text-green-700' :
                            cb.acceptance_status === 'REJECTED' ? 'bg-red-100 text-red-700' :
                            'bg-yellow-100 text-yellow-700'
                          }`}>
                            {cb.acceptance_status || 'PENDING'}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-sm">{cb.payment_mode}</td>
                        <td className="px-4 py-3 text-sm">{cb.customer_name}</td>
                        <td className="px-4 py-3 text-sm">{cb.customer_mobile}</td>
                        <td className="px-4 py-3 text-sm font-mono">{cb.utr}</td>
                        <td className="px-4 py-3 text-sm text-gray-500">{cb.chargeback_date}</td>
                        <td className="px-4 py-3 text-sm">
                          {cb.acceptance_status === 'PENDING' ? (
                            <Button
                              onClick={() => handleAcceptChargeback(cb.id)}
                              disabled={acceptingId === cb.id}
                              size="sm"
                              className="bg-green-600 hover:bg-green-700"
                            >
                              {acceptingId === cb.id ? (
                                <>
                                  <RefreshCw className="h-3 w-3 mr-1 animate-spin" />
                                  Accepting...
                                </>
                              ) : (
                                <>
                                  <CheckCircle className="h-3 w-3 mr-1" />
                                  Accept
                                </>
                              )}
                            </Button>
                          ) : cb.acceptance_status === 'ACCEPTED' ? (
                            <span className="text-xs text-green-600 flex items-center gap-1">
                              <CheckCircle className="h-3 w-3" />
                              Accepted
                            </span>
                          ) : (
                            <span className="text-xs text-red-600 flex items-center gap-1">
                              <XCircle className="h-3 w-3" />
                              Rejected
                            </span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Pagination */}
              {pagination.total_pages > 1 && (
                <div className="flex items-center justify-between mt-4 pt-4 border-t">
                  <div className="text-sm text-gray-600">
                    Page {pagination.page} of {pagination.total_pages}
                  </div>
                  <div className="flex gap-2">
                    <Button
                      onClick={() => handlePageChange(pagination.page - 1)}
                      disabled={!pagination.has_prev}
                      variant="outline"
                      size="sm"
                    >
                      Previous
                    </Button>
                    <Button
                      onClick={() => handlePageChange(pagination.page + 1)}
                      disabled={!pagination.has_next}
                      variant="outline"
                      size="sm"
                    >
                      Next
                    </Button>
                  </div>
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
