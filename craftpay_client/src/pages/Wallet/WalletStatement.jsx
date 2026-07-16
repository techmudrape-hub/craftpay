import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Wallet, Download, Search, RefreshCw, Calendar } from 'lucide-react'
import { toast } from 'sonner'
import clientAPI from '@/api/client_api'

export default function WalletStatement() {
  const [fromDate, setFromDate] = useState('')
  const [toDate, setToDate] = useState('')
  const [transactions, setTransactions] = useState([])
  const [loading, setLoading] = useState(false)
  const [downloading, setDownloading] = useState(false)
  const [entriesPerPage, setEntriesPerPage] = useState(10)
  const [searchTerm, setSearchTerm] = useState('')
  const [currentPage, setCurrentPage] = useState(1)
  const [txnTypeFilter, setTxnTypeFilter] = useState('')
  const [categoryFilter, setCategoryFilter] = useState('')
  const [walletBalance, setWalletBalance] = useState({ settled_balance: 0, unsettled_balance: 0 })

  useEffect(() => {
    loadWalletStatement()
    loadWalletBalance()
  }, [])

  const loadWalletBalance = async () => {
    try {
      const response = await clientAPI.getWalletOverview()
      if (response.success && response.data) {
        setWalletBalance({
          settled_balance: response.data.balance || 0,
          unsettled_balance: response.data.unsettled_balance || 0
        })
      }
    } catch (error) {
      console.error('Wallet balance error:', error)
    }
  }

  const loadWalletStatement = async (filters = {}) => {
    try {
      setLoading(true)
      const response = await clientAPI.getWalletStatement(filters)
      if (response.success) {
        setTransactions(response.transactions || [])
        if (response.wallet) {
          setWalletBalance(response.wallet)
        }
      }
    } catch (error) {
      toast.error('Failed to load wallet statement')
      console.error('Wallet statement error:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleSearch = () => {
    setCurrentPage(1)
    const filters = {}
    if (fromDate) filters.from_date = fromDate
    if (toDate) filters.to_date = toDate
    if (txnTypeFilter) filters.txn_type = txnTypeFilter
    if (categoryFilter) filters.filter_type = categoryFilter
    
    loadWalletStatement(filters)
    toast.success('Search applied successfully!')
  }

  const handleReset = () => {
    setFromDate('')
    setToDate('')
    setSearchTerm('')
    setTxnTypeFilter('')
    setCategoryFilter('')
    setCurrentPage(1)
    loadWalletStatement()
    toast.info('Filters reset')
  }

  const exportToCSV = async (type = 'current') => {
    try {
      setDownloading(true)
      let data = []

      if (type === 'all') {
        // Download all transactions
        const response = await clientAPI.getWalletStatement()
        if (response.success) {
          data = response.transactions || []
        }
      } else if (type === 'today') {
        // Download today's transactions
        const today = new Date().toISOString().split('T')[0]
        const response = await clientAPI.getWalletStatement({
          from_date: today,
          to_date: today
        })
        if (response.success) {
          data = response.transactions || []
        }
      } else if (type === 'filtered') {
        // Download filtered transactions
        const hasFilters = txnTypeFilter || categoryFilter || fromDate || toDate
        
        if (!hasFilters) {
          toast.info('No filters applied. Use "Export All" to download all transactions.')
          setDownloading(false)
          return
        }

        const filters = {}
        if (fromDate) filters.from_date = fromDate
        if (toDate) filters.to_date = toDate
        if (txnTypeFilter) filters.txn_type = txnTypeFilter
        if (categoryFilter) filters.filter_type = categoryFilter

        const response = await clientAPI.getWalletStatement(filters)
        if (response.success) {
          data = response.transactions || []
        }
      } else {
        // Download current page
        data = filteredTransactions
      }

      if (data.length === 0) {
        toast.info('No transactions to export')
        return
      }

      const headers = ['Transaction ID', 'Category', 'Type', 'Description', 'Date', 'Amount', 'Balance Before', 'Balance After', 'Reference ID', 'Status']
      const rows = data.map(txn => [
        txn.txn_id || '-',
        txn.category || '-',
        txn.txn_type || '-',
        txn.description || '-',
        new Date(txn.created_at).toLocaleString(),
        parseFloat(txn.amount || 0),
        parseFloat(txn.balance_before || 0),
        parseFloat(txn.balance_after || 0),
        txn.reference_id || '-',
        txn.status || '-'
      ])

      const csvContent = [
        headers.join(','),
        ...rows.map(row => row.map(cell => `"${cell}"`).join(','))
      ].join('\n')

      const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      const filename = type === 'today' 
        ? `wallet-statement-today-${new Date().toISOString().split('T')[0]}.csv`
        : type === 'all'
        ? `wallet-statement-all-${new Date().toISOString().split('T')[0]}.csv`
        : type === 'filtered'
        ? `wallet-statement-filtered-${new Date().toISOString().split('T')[0]}.csv`
        : `wallet-statement-${new Date().toISOString().split('T')[0]}.csv`
      a.download = filename
      a.click()
      window.URL.revokeObjectURL(url)
      
      toast.success(`Exported ${data.length} transactions`)
    } catch (error) {
      toast.error('Failed to export data')
      console.error(error)
    } finally {
      setDownloading(false)
    }
  }

  const formatDate = (dateString) => {
    if (!dateString) return '-'
    return new Date(dateString).toLocaleString('en-IN', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    })
  }

  const formatCurrency = (amount) => {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 2
    }).format(amount || 0)
  }

  const filteredTransactions = transactions.filter(txn => {
    if (!searchTerm) return true
    const searchLower = searchTerm.toLowerCase()
    return (
      (txn.txn_id || '').toLowerCase().includes(searchLower) ||
      (txn.description || '').toLowerCase().includes(searchLower) ||
      (txn.category || '').toLowerCase().includes(searchLower) ||
      (txn.reference_id || '').toLowerCase().includes(searchLower)
    )
  })

  // Pagination calculations
  const totalPages = Math.ceil(filteredTransactions.length / entriesPerPage)
  const startIndex = (currentPage - 1) * entriesPerPage
  const endIndex = startIndex + entriesPerPage
  const currentTransactions = filteredTransactions.slice(startIndex, endIndex)

  const handlePageChange = (page) => {
    setCurrentPage(page)
  }

  const handlePrevious = () => {
    if (currentPage > 1) {
      setCurrentPage(currentPage - 1)
    }
  }

  const handleNext = () => {
    if (currentPage < totalPages) {
      setCurrentPage(currentPage + 1)
    }
  }

  return (
    <div className="space-y-6">
      {/* Page Header with Export Buttons */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Wallet className="h-8 w-8 text-orange-600" />
          <h1 className="text-3xl font-bold">Wallet Statement</h1>
        </div>
        <div className="flex gap-2">
          <Button
            onClick={() => loadWalletStatement()}
            disabled={loading}
            variant="outline"
          >
            <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
          <Button
            onClick={() => exportToCSV('current')}
            disabled={downloading}
            className="bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-700 hover:to-blue-800"
          >
            <Download className="h-4 w-4 mr-2" />
            Export Page
          </Button>
          <Button
            onClick={() => exportToCSV('filtered')}
            disabled={downloading || (!txnTypeFilter && !categoryFilter && !fromDate && !toDate)}
            variant="outline"
            className="bg-blue-50 hover:bg-blue-100 border-blue-200 disabled:opacity-50"
          >
            <Download className="h-4 w-4 mr-2" />
            Download Filtered
          </Button>
          <Button
            onClick={() => exportToCSV('all')}
            disabled={downloading}
            className="bg-gradient-to-r from-green-600 to-green-700 hover:from-green-700 hover:to-green-800"
          >
            <Download className="h-4 w-4 mr-2" />
            Export All
          </Button>
          <Button
            onClick={() => exportToCSV('today')}
            disabled={downloading}
            className="bg-gradient-to-r from-purple-600 to-purple-700 hover:from-purple-700 hover:to-purple-800"
          >
            <Calendar className="h-4 w-4 mr-2" />
            Today's Report
          </Button>
        </div>
      </div>

      {/* Search Filters */}
      <Card>
        <CardHeader>
          <CardTitle>Search Filters</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-12 gap-4 items-end">
            <div className="col-span-2">
              <Label className="text-sm font-medium">Transaction Type</Label>
              <select
                value={txnTypeFilter}
                onChange={(e) => setTxnTypeFilter(e.target.value)}
                className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-purple-500"
              >
                <option value="">All Types</option>
                <option value="CREDIT">Credit</option>
                <option value="DEBIT">Debit</option>
              </select>
            </div>
            <div className="col-span-2">
              <Label className="text-sm font-medium">Category</Label>
              <select
                value={categoryFilter}
                onChange={(e) => setCategoryFilter(e.target.value)}
                className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-purple-500"
              >
                <option value="">All Categories</option>
                <option value="topup">Fund Topup</option>
                <option value="fetch">Fund Fetch</option>
                <option value="fund_request">Fund Request</option>
                <option value="unsettled_settlement">Settlement</option>
              </select>
            </div>
            <div className="col-span-2">
              <Label className="text-sm font-medium">From Date</Label>
              <Input
                type="date"
                value={fromDate}
                onChange={(e) => setFromDate(e.target.value)}
                className="h-9"
              />
            </div>
            <div className="col-span-2">
              <Label className="text-sm font-medium">To Date</Label>
              <Input
                type="date"
                value={toDate}
                onChange={(e) => setToDate(e.target.value)}
                className="h-9"
              />
            </div>
            <div className="col-span-2">
              <Button 
                onClick={handleSearch}
                disabled={loading}
                className="w-full h-9 bg-gradient-to-r from-purple-600 to-purple-700 hover:from-purple-700 hover:to-purple-800"
              >
                <Search className="h-4 w-4 mr-2" />
                Search
              </Button>
            </div>
            <div className="col-span-2">
              <Button 
                onClick={handleReset}
                disabled={loading}
                variant="outline"
                className="w-full h-9"
              >
                Reset
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Transaction Table */}
      <Card>
        <CardContent className="pt-6">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <div className="text-center">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-orange-600 mx-auto"></div>
                <p className="mt-4 text-gray-600">Loading wallet statement...</p>
              </div>
            </div>
          ) : (
            <>
              {/* Wallet Balance Display */}
              <div className="mb-4 p-4 bg-gradient-to-r from-orange-50 to-yellow-50 rounded-lg border-2 border-orange-200">
                <div className="grid grid-cols-2 gap-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm text-gray-600">Settled Balance</p>
                      <p className="text-2xl font-bold text-green-700">{formatCurrency(walletBalance.settled_balance)}</p>
                    </div>
                    <Wallet className="h-8 w-8 text-green-600" />
                  </div>
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm text-gray-600">Unsettled Balance</p>
                      <p className="text-2xl font-bold text-orange-700">{formatCurrency(walletBalance.unsettled_balance)}</p>
                    </div>
                    <Wallet className="h-8 w-8 text-orange-600" />
                  </div>
                </div>
                <div className="mt-3 pt-3 border-t border-orange-200">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm text-gray-600">Total Balance</p>
                      <p className="text-xl font-bold text-blue-700">
                        {formatCurrency((walletBalance.settled_balance || 0) + (walletBalance.unsettled_balance || 0))}
                      </p>
                    </div>
                  </div>
                </div>
              </div>

              {/* Table Controls */}
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <span className="text-sm">Show</span>
                  <select
                    value={entriesPerPage}
                    onChange={(e) => {
                      setEntriesPerPage(Number(e.target.value))
                      setCurrentPage(1)
                    }}
                    className="flex h-9 w-20 rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm"
                  >
                    <option value={10}>10</option>
                    <option value={25}>25</option>
                    <option value={50}>50</option>
                    <option value={100}>100</option>
                  </select>
                  <span className="text-sm">entries</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-sm">Quick Filter:</span>
                  <Input
                    value={searchTerm}
                    onChange={(e) => {
                      setSearchTerm(e.target.value)
                      setCurrentPage(1)
                    }}
                    className="w-64 h-9"
                    placeholder="Filter current page..."
                  />
                </div>
              </div>

              {/* Table */}
              <div className="overflow-x-auto border rounded-lg">
                <Table>
                  <TableHeader>
                    <TableRow className="bg-gray-50">
                      <TableHead className="font-semibold">TRANSACTION ID</TableHead>
                      <TableHead className="font-semibold">CATEGORY</TableHead>
                      <TableHead className="font-semibold">TYPE</TableHead>
                      <TableHead className="font-semibold">DESCRIPTION</TableHead>
                      <TableHead className="font-semibold">DATE</TableHead>
                      <TableHead className="font-semibold">AMOUNT</TableHead>
                      <TableHead className="font-semibold">BALANCE BEFORE</TableHead>
                      <TableHead className="font-semibold">BALANCE AFTER</TableHead>
                      <TableHead className="font-semibold">REFERENCE ID</TableHead>
                      <TableHead className="font-semibold">STATUS</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredTransactions.length === 0 ? (
                      <TableRow>
                        <TableCell colSpan={10} className="text-center py-8 text-gray-500">
                          No wallet transactions found
                        </TableCell>
                      </TableRow>
                    ) : (
                      currentTransactions.map((txn, index) => (
                        <TableRow key={txn.id || index} className="hover:bg-gray-50">
                          <TableCell className="font-mono text-xs">{txn.txn_id || '-'}</TableCell>
                          <TableCell>
                            <span className={`px-2 py-1 rounded text-xs font-medium ${
                              txn.category === 'TOPUP' ? 'bg-blue-100 text-blue-700' :
                              txn.category === 'FETCH' ? 'bg-red-100 text-red-700' :
                              txn.category === 'FUND_REQUEST' ? 'bg-yellow-100 text-yellow-700' :
                              txn.category === 'UNSETTLED_SETTLEMENT' ? 'bg-green-100 text-green-700' :
                              'bg-gray-100 text-gray-700'
                            }`}>
                              {txn.category || '-'}
                            </span>
                          </TableCell>
                          <TableCell>
                            <span className={`px-2 py-1 rounded text-xs font-medium ${
                              txn.txn_type === 'CREDIT' 
                                ? 'bg-green-100 text-green-700' 
                                : txn.txn_type === 'DEBIT'
                                ? 'bg-red-100 text-red-700'
                                : 'bg-gray-100 text-gray-700'
                            }`}>
                              {txn.txn_type || '-'}
                            </span>
                          </TableCell>
                          <TableCell className="max-w-xs truncate">{txn.description || '-'}</TableCell>
                          <TableCell className="whitespace-nowrap">{formatDate(txn.created_at)}</TableCell>
                          <TableCell className={`font-medium ${txn.txn_type === 'CREDIT' ? 'text-green-600' : 'text-red-600'}`}>
                            {txn.txn_type === 'CREDIT' ? '+' : txn.txn_type === 'DEBIT' ? '-' : ''}{formatCurrency(txn.amount)}
                          </TableCell>
                          <TableCell>{formatCurrency(txn.balance_before)}</TableCell>
                          <TableCell className="font-medium">{formatCurrency(txn.balance_after)}</TableCell>
                          <TableCell className="font-mono text-xs">{txn.reference_id || '-'}</TableCell>
                          <TableCell>
                            <span className={`px-2 py-1 rounded text-xs font-medium ${
                              txn.status === 'COMPLETED' || txn.status === 'APPROVED' ? 'bg-green-100 text-green-700' :
                              txn.status === 'PENDING' ? 'bg-yellow-100 text-yellow-700' :
                              txn.status === 'REJECTED' ? 'bg-red-100 text-red-700' :
                              'bg-gray-100 text-gray-700'
                            }`}>
                              {txn.status || '-'}
                            </span>
                          </TableCell>
                        </TableRow>
                      ))
                    )}
                  </TableBody>
                </Table>
              </div>

              {/* Pagination */}
              <div className="flex items-center justify-between mt-4">
                <div className="text-sm text-gray-600">
                  Showing {startIndex + 1} to {Math.min(endIndex, filteredTransactions.length)} of {filteredTransactions.length} entries
                </div>
                <div className="flex gap-1">
                  <Button 
                    variant="outline" 
                    size="sm" 
                    onClick={handlePrevious}
                    disabled={currentPage === 1}
                    className="text-sm"
                  >
                    Previous
                  </Button>
                  {Array.from({ length: Math.min(totalPages, 5) }, (_, i) => {
                    let pageNum
                    if (totalPages <= 5) {
                      pageNum = i + 1
                    } else if (currentPage <= 3) {
                      pageNum = i + 1
                    } else if (currentPage >= totalPages - 2) {
                      pageNum = totalPages - 4 + i
                    } else {
                      pageNum = currentPage - 2 + i
                    }
                    return (
                      <Button
                        key={pageNum}
                        variant={currentPage === pageNum ? "default" : "outline"}
                        size="sm"
                        onClick={() => handlePageChange(pageNum)}
                        className={`text-sm ${
                          currentPage === pageNum 
                            ? 'bg-gradient-to-r from-purple-600 to-purple-700 hover:from-purple-700 hover:to-purple-800' 
                            : ''
                        }`}
                      >
                        {pageNum}
                      </Button>
                    )
                  })}
                  <Button 
                    variant="outline" 
                    size="sm" 
                    onClick={handleNext}
                    disabled={currentPage === totalPages}
                    className="text-sm"
                  >
                    Next
                  </Button>
                </div>
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
