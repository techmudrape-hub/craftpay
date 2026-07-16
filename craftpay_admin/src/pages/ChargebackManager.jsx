import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { 
  Upload, Download, FileText, AlertCircle, CheckCircle, 
  Search, Filter, Calendar, RefreshCw, FileSpreadsheet
} from 'lucide-react'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { toast } from 'sonner'
import adminAPI from '@/api/admin_api'
import { formatCurrency } from '@/lib/utils'

export default function ChargebackManager() {
  const [merchants, setMerchants] = useState([])
  const [selectedMerchant, setSelectedMerchant] = useState('')
  const [file, setFile] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [uploads, setUploads] = useState([])
  const [chargebacks, setChargebacks] = useState([])
  const [loading, setLoading] = useState(false)
  
  // Hold settings
  const [cyberHold, setCyberHold] = useState('')
  const [totalHold, setTotalHold] = useState('')
  const [savingHolds, setSavingHolds] = useState(false)
  
  // Filters
  const [filters, setFilters] = useState({
    merchant_id: '',
    from_date: '',
    to_date: '',
    transaction_id: '',
    acceptance_status: '',
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
    loadMerchants()
    loadUploads()
    loadChargebacks()
  }, [])

  useEffect(() => {
    loadChargebacks()
  }, [filters])

  const loadMerchants = async () => {
    try {
      const response = await adminAPI.getChargebackMerchants()
      if (response.success) {
        setMerchants(response.merchants || [])
      }
    } catch (error) {
      console.error('Load merchants error:', error)
      toast.error('Failed to load merchants')
    }
  }

  useEffect(() => {
    if (selectedMerchant) {
      loadMerchantHolds()
    } else {
      setCyberHold('')
      setTotalHold('')
    }
  }, [selectedMerchant])

  const loadMerchantHolds = async () => {
    try {
      const response = await adminAPI.getMerchantHolds(selectedMerchant)
      if (response.success) {
        setCyberHold(response.cyber_hold_amount || 0)
        setTotalHold(response.total_hold_amount || 0)
      }
    } catch (error) {
      console.error('Load holds error:', error)
    }
  }

  const handleSaveHolds = async () => {
    if (!selectedMerchant) return
    
    try {
      setSavingHolds(true)
      const response = await adminAPI.updateMerchantHolds({
        merchant_id: selectedMerchant,
        cyber_hold_amount: cyberHold,
        total_hold_amount: totalHold
      })
      
      if (response.success) {
        toast.success(response.message || 'Holds updated successfully')
      } else {
        toast.error(response.message || 'Failed to update holds')
      }
    } catch (error) {
      console.error('Save holds error:', error)
      toast.error('Failed to update holds')
    } finally {
      setSavingHolds(false)
    }
  }

  const loadUploads = async () => {
    try {
      const response = await adminAPI.getChargebackUploads(filters)
      if (response.success) {
        setUploads(response.uploads || [])
      }
    } catch (error) {
      console.error('Load uploads error:', error)
    }
  }

  const loadChargebacks = async () => {
    try {
      setLoading(true)
      const response = await adminAPI.getAdminChargebacks(filters)
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

  const handleFileChange = (e) => {
    const selectedFile = e.target.files[0]
    if (selectedFile) {
      if (selectedFile.type !== 'text/csv' && !selectedFile.name.endsWith('.csv')) {
        toast.error('Please select a CSV file')
        return
      }
      setFile(selectedFile)
    }
  }

  const handleUpload = async () => {
    if (!selectedMerchant) {
      toast.error('Please select a merchant')
      return
    }
    
    if (!file) {
      toast.error('Please select a CSV file')
      return
    }

    try {
      setUploading(true)
      const formData = new FormData()
      formData.append('file', file)
      formData.append('merchant_id', selectedMerchant)

      const response = await adminAPI.uploadChargebackCSV(formData)
      
      if (response.success) {
        toast.success(response.message)
        setFile(null)
        setSelectedMerchant('')
        // Reset file input
        document.getElementById('csv-file-input').value = ''
        // Reload data
        loadUploads()
        loadChargebacks()
      } else {
        toast.error(response.message || 'Upload failed')
      }
    } catch (error) {
      console.error('Upload error:', error)
      toast.error(error.message || 'Failed to upload CSV')
    } finally {
      setUploading(false)
    }
  }

  const handleDownloadTemplate = async () => {
    try {
      await adminAPI.downloadChargebackTemplate()
      toast.success('Template downloaded successfully')
    } catch (error) {
      console.error('Download template error:', error)
      toast.error('Failed to download template')
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
      merchant_id: '',
      from_date: '',
      to_date: '',
      transaction_id: '',
      acceptance_status: '',
      page: 1,
      per_page: 20
    })
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
          Chargeback Manager
        </h1>
        <p className="text-gray-600 mt-1">Upload and manage merchant chargebacks</p>
      </div>

      {/* Upload Section */}
      <Card className="border-2 border-purple-200 bg-gradient-to-br from-purple-50 to-white">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Upload className="h-5 w-5 text-purple-600" />
            Upload Chargeback Data
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <Label htmlFor="merchant-select">Select Merchant *</Label>
              <Select value={selectedMerchant} onValueChange={setSelectedMerchant}>
                <SelectTrigger id="merchant-select">
                  <SelectValue placeholder="Choose a merchant" />
                </SelectTrigger>
                <SelectContent>
                  {merchants.map((merchant) => (
                    <SelectItem key={merchant.merchant_id} value={merchant.merchant_id}>
                      {merchant.full_name} ({merchant.merchant_id})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div>
              <Label htmlFor="csv-file-input">Upload CSV File *</Label>
              <Input
                id="csv-file-input"
                type="file"
                accept=".csv"
                onChange={handleFileChange}
                className="cursor-pointer"
              />
              {file && (
                <p className="text-sm text-green-600 mt-1 flex items-center gap-1">
                  <CheckCircle className="h-4 w-4" />
                  {file.name}
                </p>
              )}
            </div>
          </div>

          <div className="flex gap-3">
            <Button
              onClick={handleUpload}
              disabled={uploading || !selectedMerchant || !file}
              className="bg-purple-600 hover:bg-purple-700"
            >
              {uploading ? (
                <>
                  <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                  Uploading...
                </>
              ) : (
                <>
                  <Upload className="h-4 w-4 mr-2" />
                  Upload CSV
                </>
              )}
            </Button>

            <Button
              onClick={handleDownloadTemplate}
              variant="outline"
              className="border-purple-300 text-purple-700 hover:bg-purple-50"
            >
              <Download className="h-4 w-4 mr-2" />
              Download Template
            </Button>
          </div>

          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <div className="flex items-start gap-2">
              <AlertCircle className="h-5 w-5 text-blue-600 mt-0.5" />
              <div className="text-sm text-blue-800">
                <p className="font-semibold mb-1">CSV Format Requirements:</p>
                <ul className="list-disc list-inside space-y-1">
                  <li>Headers: Transaction ID, Order ID, Chargeback Amount, Status, Payment Mode, Customer Name, Customer Mobile, UTR, Date</li>
                  <li>Date format: DD-MM-YY (e.g., 03-05-26)</li>
                  <li>Amount should be numeric without currency symbols</li>
                  <li>Download the template for reference</li>
                </ul>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Merchant Hold Settings */}
      {selectedMerchant && (
        <Card className="border-2 border-orange-200 bg-gradient-to-br from-orange-50 to-white">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-orange-800">
              <AlertCircle className="h-5 w-5" />
              Manual Hold Settings for Selected Merchant
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <Label htmlFor="cyber-hold">Cyber Hold Amount (₹)</Label>
                <Input
                  id="cyber-hold"
                  type="number"
                  value={cyberHold}
                  onChange={(e) => setCyberHold(e.target.value)}
                  placeholder="0.00"
                />
              </div>
              <div>
                <Label htmlFor="total-hold">Total Hold Amount (₹)</Label>
                <Input
                  id="total-hold"
                  type="number"
                  value={totalHold}
                  onChange={(e) => setTotalHold(e.target.value)}
                  placeholder="0.00"
                />
              </div>
            </div>
            <div className="flex justify-end">
              <Button
                onClick={handleSaveHolds}
                disabled={savingHolds}
                className="bg-orange-600 hover:bg-orange-700"
              >
                {savingHolds ? (
                  <>
                    <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                    Saving...
                  </>
                ) : (
                  <>Save Holds</>
                )}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Recent Uploads */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileSpreadsheet className="h-5 w-5 text-green-600" />
            Recent Uploads
          </CardTitle>
        </CardHeader>
        <CardContent>
          {uploads.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              <FileText className="h-12 w-12 mx-auto mb-3 text-gray-300" />
              <p>No uploads yet</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Upload ID</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Merchant</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Filename</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Total</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Success</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Failed</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Date</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {uploads.slice(0, 5).map((upload) => (
                    <tr key={upload.upload_id} className="hover:bg-gray-50">
                      <td className="px-4 py-3 text-sm font-mono">{upload.upload_id}</td>
                      <td className="px-4 py-3 text-sm">{upload.merchant_name || upload.merchant_id}</td>
                      <td className="px-4 py-3 text-sm">{upload.filename}</td>
                      <td className="px-4 py-3 text-sm">{upload.total_records}</td>
                      <td className="px-4 py-3 text-sm text-green-600">{upload.successful_records}</td>
                      <td className="px-4 py-3 text-sm text-red-600">{upload.failed_records}</td>
                      <td className="px-4 py-3 text-sm">
                        <span className={`px-2 py-1 rounded-full text-xs ${
                          upload.upload_status === 'COMPLETED' ? 'bg-green-100 text-green-700' :
                          upload.upload_status === 'PROCESSING' ? 'bg-yellow-100 text-yellow-700' :
                          'bg-red-100 text-red-700'
                        }`}>
                          {upload.upload_status}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-500">{new Date(upload.created_at).toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Filters */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Filter className="h-5 w-5 text-blue-600" />
            Filter Chargebacks
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
            <div>
              <Label>Merchant</Label>
              <Select value={filters.merchant_id || 'all'} onValueChange={(value) => handleFilterChange('merchant_id', value === 'all' ? '' : value)}>
                <SelectTrigger>
                  <SelectValue placeholder="All Merchants" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Merchants</SelectItem>
                  {merchants.map((merchant) => (
                    <SelectItem key={merchant.merchant_id} value={merchant.merchant_id}>
                      {merchant.full_name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

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
              <Label>Acceptance Status</Label>
              <Select value={filters.acceptance_status || 'all'} onValueChange={(value) => handleFilterChange('acceptance_status', value === 'all' ? '' : value)}>
                <SelectTrigger>
                  <SelectValue placeholder="All Status" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Status</SelectItem>
                  <SelectItem value="PENDING">PENDING</SelectItem>
                  <SelectItem value="ACCEPTED">ACCEPTED</SelectItem>
                  <SelectItem value="REJECTED">REJECTED</SelectItem>
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
          </div>
        </CardContent>
      </Card>

      {/* Chargebacks Table */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <span className="flex items-center gap-2">
              <FileText className="h-5 w-5 text-orange-600" />
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
              <p>No chargeback records found</p>
            </div>
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Transaction ID</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Order ID</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Merchant</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Amount</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Acceptance</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Deduction Status</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Customer</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Mobile</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">UTR</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Date</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Accepted At</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200">
                    {chargebacks.map((cb) => (
                      <tr key={cb.id} className="hover:bg-gray-50">
                        <td className="px-4 py-3 text-sm font-mono">{cb.transaction_id}</td>
                        <td className="px-4 py-3 text-sm font-mono">{cb.order_id}</td>
                        <td className="px-4 py-3 text-sm">{cb.merchant_name || cb.merchant_id}</td>
                        <td className="px-4 py-3 text-sm font-semibold text-red-600">{formatCurrency(cb.chargeback_amount)}</td>
                        <td className="px-4 py-3 text-sm">
                          <span className={`px-2 py-1 rounded-full text-xs ${
                            cb.status === 'SUCCESS' ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-700'
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
                        <td className="px-4 py-3 text-sm">
                          {cb.deduction_status ? (
                            <span className={`px-2 py-1 rounded-full text-xs ${
                              cb.deduction_status === 'SUCCESS' ? 'bg-green-100 text-green-700' :
                              cb.deduction_status === 'FAILED' ? 'bg-red-100 text-red-700' :
                              'bg-yellow-100 text-yellow-700'
                            }`}>
                              {cb.deduction_status}
                            </span>
                          ) : (
                            <span className="text-xs text-gray-400">-</span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-sm">{cb.customer_name}</td>
                        <td className="px-4 py-3 text-sm">{cb.customer_mobile}</td>
                        <td className="px-4 py-3 text-sm font-mono">{cb.utr}</td>
                        <td className="px-4 py-3 text-sm text-gray-500">{cb.chargeback_date}</td>
                        <td className="px-4 py-3 text-sm text-gray-500">
                          {cb.accepted_at ? new Date(cb.accepted_at).toLocaleString() : '-'}
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
