import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { 
  Download, FileText, Search, Filter, RefreshCw, 
  TrendingDown, ArrowLeft, CheckCircle, XCircle, AlertCircle
} from 'lucide-react'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { toast } from 'sonner'
import clientAPI from '@/api/client_api'
import { formatCurrency } from '@/lib/utils'
import { useNavigate } from 'react-router-dom'

export default function ChargebackDeductions() {
  const navigate = useNavigate()
  const [deductions, setDeductions] = useState([])
  const [summary, setSummary] = useState({
    total_deductions: 0,
    total_deducted: 0
  })
  const [loading, setLoading] = useState(false)
  const [downloading, setDownloading] = useState(false)
  
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
    loadDeductions()
  }, [filters])

  const loadDeductions = async () => {
    try {
      setLoading(true)
      const response = await clientAPI.getChargebackDeductions(filters)
      if (response.success) {
        setDeductions(response.deductions || [])
        setPagination(response.pagination || pagination)
        setSummary(response.summary || summary)
      }
    } catch (error) {
      console.error('Load deductions error:', error)
      toast.error('Failed to load deduction history')
    } finally {
      setLoading(false)
    }
  }

  const handleDownloadReport = async () => {
    try {
      setDownloading(true)
      await clientAPI.downloadDeductionReport(filters)
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

  const handleBack = () => {
    navigate('/chargebacks')
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Button onClick={handleBack} variant="outline" size="sm">
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back to Chargebacks
        </Button>
        <div>
          <h1 className="text-3xl font-bold bg-gradient-to-r from-purple-600 to-pink-600 bg-clip-text text-transparent">
            Chargeback Deduction History
          </h1>
          <p className="text-gray-600 mt-1">View all deductions from your unsettled balance</p>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card className="border-2 border-purple-200 bg-gradient-to-br from-purple-50 to-white">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-gray-600 flex items-center gap-2">
              <TrendingDown className="h-4 w-4 text-purple-600" />
              Total Deductions
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-bold text-purple-700">{summary.total_deductions}</p>
            <p className="text-xs text-gray-500 mt-2">All time</p>
          </CardContent>
        </Card>

        <Card className="border-2 border-pink-200 bg-gradient-to-br from-pink-50 to-white">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-gray-600 flex items-center gap-2">
              <AlertCircle className="h-4 w-4 text-pink-600" />
              Total Amount Deducted
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-bold text-pink-700">{formatCurrency(summary.total_deducted)}</p>
            <p className="text-xs text-gray-500 mt-2">All time</p>
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Filter className="h-5 w-5 text-blue-600" />
            Filter Deductions
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
                  <SelectItem value="FAILED">FAILED</SelectItem>
                  <SelectItem value="INSUFFICIENT_BALANCE">INSUFFICIENT BALANCE</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="flex gap-2 mt-4">
            <Button onClick={loadDeductions} variant="outline">
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
                  Download Excel
                </>
              )}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Deductions Table */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <span className="flex items-center gap-2">
              <FileText className="h-5 w-5 text-purple-600" />
              Deduction Records
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
              <p className="mt-4 text-gray-600">Loading deductions...</p>
            </div>
          ) : deductions.length === 0 ? (
            <div className="text-center py-12 text-gray-500">
              <FileText className="h-16 w-16 mx-auto mb-4 text-gray-300" />
              <p className="text-lg font-semibold">No deduction records found</p>
              <p className="text-sm mt-2">No chargebacks have been accepted yet</p>
            </div>
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Deduction ID</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Transaction ID</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Order ID</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Deduction Amount</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Previous Balance</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">New Balance</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Customer</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Mobile</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Deduction Date</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Remarks</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200">
                    {deductions.map((ded) => (
                      <tr key={ded.id} className="hover:bg-gray-50">
                        <td className="px-4 py-3 text-sm font-mono">{ded.deduction_id}</td>
                        <td className="px-4 py-3 text-sm font-mono">{ded.transaction_id}</td>
                        <td className="px-4 py-3 text-sm font-mono">{ded.order_id}</td>
                        <td className="px-4 py-3 text-sm font-semibold text-red-600">{formatCurrency(ded.deduction_amount)}</td>
                        <td className="px-4 py-3 text-sm text-gray-600">{formatCurrency(ded.previous_unsettled_balance)}</td>
                        <td className="px-4 py-3 text-sm text-gray-600">{formatCurrency(ded.new_unsettled_balance)}</td>
                        <td className="px-4 py-3 text-sm">
                          <span className={`px-2 py-1 rounded-full text-xs flex items-center gap-1 w-fit ${
                            ded.deduction_status === 'SUCCESS' ? 'bg-green-100 text-green-700' :
                            ded.deduction_status === 'FAILED' ? 'bg-red-100 text-red-700' :
                            'bg-yellow-100 text-yellow-700'
                          }`}>
                            {ded.deduction_status === 'SUCCESS' ? (
                              <CheckCircle className="h-3 w-3" />
                            ) : ded.deduction_status === 'FAILED' ? (
                              <XCircle className="h-3 w-3" />
                            ) : (
                              <AlertCircle className="h-3 w-3" />
                            )}
                            {ded.deduction_status}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-sm">{ded.customer_name || '-'}</td>
                        <td className="px-4 py-3 text-sm">{ded.customer_mobile || '-'}</td>
                        <td className="px-4 py-3 text-sm text-gray-500">{new Date(ded.deduction_date).toLocaleString()}</td>
                        <td className="px-4 py-3 text-sm text-gray-500 max-w-xs truncate" title={ded.remarks}>
                          {ded.remarks || '-'}
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
