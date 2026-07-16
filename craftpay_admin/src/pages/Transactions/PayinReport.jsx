import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Badge } from '../../components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../../components/ui/dialog';
import { toast } from 'sonner';
import adminAPI from '../../api/admin_api';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../../components/ui/table';
import { Search, Download, RefreshCw, Filter, Eye, FileText } from 'lucide-react';

export default function PayinReport() {
  const navigate = useNavigate();
  const [transactions, setTransactions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [fromDate, setFromDate] = useState('');
  const [toDate, setToDate] = useState('');
  const [selectedTxn, setSelectedTxn] = useState(null);
  const [showDetailsDialog, setShowDetailsDialog] = useState(false);
  const [checkingStatus, setCheckingStatus] = useState(false);
  const [creatingInvoice, setCreatingInvoice] = useState(null);
  const [showUtrDialog, setShowUtrDialog] = useState(false);
  const [utrValue, setUtrValue] = useState('');
  const [selectedManualTxn, setSelectedManualTxn] = useState(null);
  const [submittingManual, setSubmittingManual] = useState(false);
  const [pagination, setPagination] = useState({
    page: 1,
    limit: 50,
    total: 0,
    pages: 0
  });

  useEffect(() => {
    fetchTransactions();
  }, [pagination.page, statusFilter, searchTerm, fromDate, toDate]);

  const fetchTransactions = async () => {
    try {
      setLoading(true);
      
      // Check authentication first
      if (!adminAPI.isAuthenticated()) {
        toast.error('Please login to continue');
        const isQR = window.location.pathname.includes('/qrlogin');
        navigate(isQR ? '/qrlogin' : '/login', { replace: true });
        return;
      }

      const params = {
        page: pagination.page,
        limit: pagination.limit
      };

      if (statusFilter) {
        params.status = statusFilter;
      }

      if (searchTerm) {
        params.search = searchTerm;
      }

      if (fromDate) {
        params.from_date = fromDate;
      }

      if (toDate) {
        params.to_date = toDate;
      }

      const response = await adminAPI.getPayinTransactions(params);
      
      if (response.success) {
        setTransactions(response.transactions || []);
        setPagination(prev => ({
          ...prev,
          ...(response.pagination || {})
        }));
      } else {
        toast.error(response.message || 'Failed to load transactions');
      }
    } catch (error) {
      console.error('Fetch transactions error:', error);
      
      // Check if it's an authentication error
      if (error.message && (error.message.includes('token') || error.message.includes('401') || error.message.includes('Session expired'))) {
        toast.error('Session expired. Please login again.');
        const isQR = window.location.pathname.includes('/qrlogin');
        navigate(isQR ? '/qrlogin' : '/login', { replace: true });
      } else {
        toast.error(error.message || 'Failed to load transactions');
      }
    } finally {
      setLoading(false);
    }
  };

  const getStatusBadge = (status) => {
    const statusConfig = {
      SUCCESS: { color: 'bg-green-500', text: 'Success' },
      PENDING: { color: 'bg-yellow-500', text: 'Pending' },
      INITIATED: { color: 'bg-blue-500', text: 'Initiated' },
      FAILED: { color: 'bg-red-500', text: 'Failed' },
      CANCELLED: { color: 'bg-gray-500', text: 'Cancelled' }
    };

    const config = statusConfig[status] || { color: 'bg-gray-500', text: status };
    
    return (
      <Badge className={config.color}>
        {config.text}
      </Badge>
    );
  };

  const formatAmount = (amount) => {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR'
    }).format(amount);
  };

  const formatDate = (dateString) => {
    if (!dateString) return '-';
    return new Date(dateString).toLocaleString('en-IN', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  // Backend search is now used, no need for client-side filtering
  const filteredTransactions = transactions;

  const exportToCSV = () => {
    const headers = ['Transaction ID', 'Order ID', 'Merchant', 'Amount', 'Charge', 'Net Amount', 'UTR/Bank Ref', 'PG Transaction ID', 'Status', 'Payment Mode', 'Service', 'Date'];
    const rows = transactions.map(txn => [
      txn.txn_id,
      txn.order_id,
      txn.merchant_name || txn.merchant_id,
      txn.amount,
      txn.charge_amount,
      txn.net_amount,
      txn.bank_ref_no || txn.utr || '-',
      txn.pg_txn_id || '-',
      txn.status,
      txn.payment_mode || '-',
      txn.service_name || '-',
      formatDate(txn.created_at)
    ]);

    const csvContent = [
      headers.join(','),
      ...rows.map(row => row.join(','))
    ].join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `payin-report-${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
    window.URL.revokeObjectURL(url);
    toast.success('Report exported successfully');
  };

  const exportTodayReport = async () => {
    try {
      toast.info('Fetching today\'s transactions...');
      
      // Fetch ALL today's transactions from backend
      const response = await adminAPI.getTodayPayinTransactions();
      
      if (!response.success || !response.transactions) {
        toast.error('Failed to fetch today\'s transactions');
        return;
      }

      const todayTransactions = response.transactions;

      if (todayTransactions.length === 0) {
        toast.error('No transactions found for today');
        return;
      }

      const headers = ['Transaction ID', 'Order ID', 'Merchant', 'Amount', 'Charge', 'Net Amount', 'UTR/Bank Ref', 'PG Transaction ID', 'Status', 'Payment Mode', 'Service', 'Date & Time'];
      const rows = todayTransactions.map(txn => [
        txn.txn_id,
        txn.order_id,
        txn.merchant_name || txn.merchant_id,
        txn.amount,
        txn.charge_amount,
        txn.net_amount,
        txn.bank_ref_no || txn.utr || '-',
        txn.pg_txn_id || '-',
        txn.status,
        txn.payment_mode || '-',
        txn.service_name || '-',
        formatDate(txn.created_at)
      ]);

      const csvContent = [
        headers.join(','),
        ...rows.map(row => row.map(cell => `"${cell}"`).join(','))
      ].join('\n');

      const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const today = new Date().toISOString().split('T')[0];
      a.download = `payin-report-today-${today}.csv`;
      a.click();
      window.URL.revokeObjectURL(url);
      toast.success(`Today's report exported (${todayTransactions.length} transactions)`);
    } catch (error) {
      console.error('Export today report error:', error);
      toast.error('Failed to export today\'s report');
    }
  };

  const exportFilteredReport = async () => {
    try {
      // Check if any filters are applied
      const hasFilters = statusFilter || searchTerm || fromDate || toDate;
      
      if (!hasFilters) {
        toast.info('No filters applied. Use "Export All" to download all transactions.');
        return;
      }

      toast.info('Fetching filtered transactions...');
      
      // Build params with current filters
      const params = {};
      if (statusFilter) params.status = statusFilter;
      if (searchTerm) params.search = searchTerm;
      if (fromDate) params.from_date = fromDate;
      if (toDate) params.to_date = toDate;
      
      // Fetch ALL filtered transactions from backend (no pagination)
      const response = await adminAPI.getAllPayinTransactions(params);
      
      if (!response.success || !response.transactions) {
        toast.error('Failed to fetch filtered transactions');
        return;
      }

      const filteredTransactions = response.transactions;

      if (filteredTransactions.length === 0) {
        toast.error('No transactions found with current filters');
        return;
      }

      const headers = ['Transaction ID', 'Order ID', 'Merchant', 'Amount', 'Charge', 'Net Amount', 'UTR/Bank Ref', 'PG Transaction ID', 'Status', 'Payment Mode', 'Service', 'Date & Time'];
      const rows = filteredTransactions.map(txn => [
        txn.txn_id,
        txn.order_id,
        txn.merchant_name || txn.merchant_id,
        txn.amount,
        txn.charge_amount,
        txn.net_amount,
        txn.bank_ref_no || txn.utr || '-',
        txn.pg_txn_id || '-',
        txn.status,
        txn.payment_mode || '-',
        txn.service_name || '-',
        formatDate(txn.created_at)
      ]);

      const csvContent = [
        headers.join(','),
        ...rows.map(row => row.map(cell => `"${cell}"`).join(','))
      ].join('\n');

      const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const today = new Date().toISOString().split('T')[0];
      a.download = `payin-report-filtered-${today}.csv`;
      a.click();
      window.URL.revokeObjectURL(url);
      toast.success(`Filtered report exported (${filteredTransactions.length} transactions)`);
    } catch (error) {
      console.error('Export filtered report error:', error);
      toast.error('Failed to export filtered report');
    }
  };

  const handleCheckStatus = async (txn) => {
    try {
      setCheckingStatus(true);
      
      // Check authentication
      if (!adminAPI.isAuthenticated()) {
        toast.error('Please login to continue');
        const isQR = window.location.pathname.includes('/qrlogin');
        navigate(isQR ? '/qrlogin' : '/login', { replace: true });
        return;
      }

      const response = await adminAPI.checkPayinStatus(txn.txn_id);
      
      if (response.success) {
        const updatedTxn = response.transaction;
        
        // Update local state
        setTransactions(prev => 
          prev.map(t => t.txn_id === txn.txn_id ? updatedTxn : t)
        );
        
        // Show details dialog
        setSelectedTxn(updatedTxn);
        setShowDetailsDialog(true);
        
        toast.success('Status updated');
      } else {
        toast.error(response.message || 'Failed to check status');
      }
    } catch (error) {
      console.error('Check status error:', error);
      
      // Check if it's an authentication error
      if (error.message && (error.message.includes('token') || error.message.includes('401'))) {
        toast.error('Session expired. Please login again.');
        const isQR = window.location.pathname.includes('/qrlogin');
        navigate(isQR ? '/qrlogin' : '/login', { replace: true });
      } else {
        toast.error(error.message || 'Failed to check status');
      }
    } finally {
      setCheckingStatus(false);
    }
  };

  const handleCreateInvoice = async (txn) => {
    // FRESH IMPLEMENTATION - Only sends txn_id to backend
    // Backend fetches transaction data and sends to invoice API
    
    try {
      // Validate transaction status
      if (txn.status !== 'SUCCESS') {
        toast.error('Invoice can only be created for successful transactions');
        return;
      }

      // Set loading state
      setCreatingInvoice(txn.txn_id);
      
      console.log('=== Creating Invoice ===');
      console.log('Transaction ID:', txn.txn_id);
      console.log('Sending to backend endpoint...');
      
      // Call backend - only send txn_id
      const response = await adminAPI.createInvoice(txn.txn_id);
      
      console.log('Backend response:', response);
      
      if (response.success) {
        toast.success('Invoice created successfully!');
        
        // Show receipt number if available
        if (response.data?.order?.receipt_number) {
          toast.success(`Receipt: ${response.data.order.receipt_number}`, {
            duration: 5000
          });
        }
      } else {
        toast.error(response.message || 'Failed to create invoice');
      }
    } catch (error) {
      console.error('Invoice creation error:', error);
      toast.error(error.message || 'Failed to create invoice');
    } finally {
      setCreatingInvoice(null);
    }
  };

  const handleManualSuccess = (txn) => {
    setSelectedManualTxn(txn);
    setUtrValue('');
    setShowUtrDialog(true);
  };

  const submitManualUtr = async () => {
    if (!utrValue.trim()) {
      toast.error('Please enter a valid UTR');
      return;
    }
    
    try {
      setSubmittingManual(true);
      const response = await adminAPI.manualCompletePayin(selectedManualTxn.txn_id, 'success', utrValue, 'Transaction Successful');
      
      if (response.success) {
        toast.success('Transaction marked as SUCCESS and callback sent');
        setShowUtrDialog(false);
        fetchTransactions(); // Refresh the list
      } else {
        toast.error(response.message || 'Failed to update transaction');
      }
    } catch (error) {
      console.error('Submit manual UTR error:', error);
      toast.error(error.message || 'Failed to update transaction');
    } finally {
      setSubmittingManual(false);
    }
  };

  const handleManualFailed = async (txn) => {
    if (!window.confirm(`Are you sure you want to mark transaction ${txn.txn_id} as FAILED?`)) {
      return;
    }
    
    try {
      setSubmittingManual(true);
      const response = await adminAPI.manualCompletePayin(txn.txn_id, 'failed', '', 'Manual failure');
      
      if (response.success) {
        toast.success('Transaction marked as FAILED and callback sent');
        fetchTransactions(); // Refresh the list
      } else {
        toast.error(response.message || 'Failed to update transaction');
      }
    } catch (error) {
      console.error('Fail manual txn error:', error);
      toast.error(error.message || 'Failed to update transaction');
    } finally {
      setSubmittingManual(false);
    }
  };

  if (loading && transactions.length === 0) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-lg">Loading transactions...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">Payin Report</h1>
          <p className="text-gray-500 mt-1">
            View all payin transactions across all merchants
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={fetchTransactions}>
            <RefreshCw className="w-4 h-4 mr-2" />
            Refresh
          </Button>
          <Button variant="outline" onClick={exportTodayReport} className="bg-green-50 hover:bg-green-100 border-green-200">
            <Download className="w-4 h-4 mr-2" />
            Today's Report
          </Button>
          <Button 
            variant="outline" 
            onClick={exportFilteredReport}
            disabled={!statusFilter && !searchTerm && !fromDate && !toDate}
            className="bg-blue-50 hover:bg-blue-100 border-blue-200 disabled:opacity-50"
          >
            <Download className="w-4 h-4 mr-2" />
            Download Filtered
          </Button>
          <Button onClick={exportToCSV}>
            <Download className="w-4 h-4 mr-2" />
            Export All
          </Button>
        </div>
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="pt-6">
          <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
            <div>
              <Input
                placeholder="Search by TXN ID, Order ID, Merchant, UTR..."
                value={searchTerm}
                onChange={(e) => {
                  setSearchTerm(e.target.value);
                  setPagination(prev => ({ ...prev, page: 1 }));
                }}
                className="w-full"
              />
            </div>
            <div>
              <select
                className="w-full border rounded-md p-2"
                value={statusFilter}
                onChange={(e) => {
                  setStatusFilter(e.target.value);
                  setPagination(prev => ({ ...prev, page: 1 }));
                }}
              >
                <option value="">All Status</option>
                <option value="SUCCESS">Success</option>
                <option value="PENDING">Pending</option>
                <option value="INITIATED">Initiated</option>
                <option value="FAILED">Failed</option>
                <option value="CANCELLED">Cancelled</option>
              </select>
            </div>
            <div>
              <Input
                type="date"
                placeholder="From Date"
                value={fromDate}
                onChange={(e) => {
                  setFromDate(e.target.value);
                  setPagination(prev => ({ ...prev, page: 1 }));
                }}
                className="w-full"
              />
            </div>
            <div>
              <Input
                type="date"
                placeholder="To Date"
                value={toDate}
                onChange={(e) => {
                  setToDate(e.target.value);
                  setPagination(prev => ({ ...prev, page: 1 }));
                }}
                className="w-full"
              />
            </div>
            <div>
              <Button 
                variant="outline" 
                onClick={() => {
                  setSearchTerm('');
                  setStatusFilter('');
                  setFromDate('');
                  setToDate('');
                  setPagination(prev => ({ ...prev, page: 1 }));
                }}
                className="w-full"
              >
                Clear Filters
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Transactions Table */}
      <Card>
        <CardHeader>
          <CardTitle>Transactions ({pagination.total})</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Transaction ID</TableHead>
                  <TableHead>Order ID</TableHead>
                  <TableHead>Merchant</TableHead>
                  <TableHead>Customer</TableHead>
                  <TableHead>Amount</TableHead>
                  <TableHead>Charge</TableHead>
                  <TableHead>Net Amount</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Payment Mode</TableHead>
                  <TableHead>Date</TableHead>
                  <TableHead className="text-center">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredTransactions.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={11} className="text-center py-8 text-gray-500">
                      No transactions found
                    </TableCell>
                  </TableRow>
                ) : (
                  filteredTransactions.map((txn) => (
                    <TableRow key={txn.id}>
                      <TableCell className="font-mono text-sm">{txn.txn_id}</TableCell>
                      <TableCell className="font-mono text-sm">{txn.order_id}</TableCell>
                      <TableCell>
                        <div>
                          <div className="font-medium">{txn.merchant_name}</div>
                          <div className="text-xs text-gray-500">{txn.merchant_id}</div>
                        </div>
                      </TableCell>
                      <TableCell>
                        <div>
                          <div className="text-sm">{txn.payee_name}</div>
                          <div className="text-xs text-gray-500">{txn.payee_mobile}</div>
                        </div>
                      </TableCell>
                      <TableCell className="font-semibold">{formatAmount(txn.amount)}</TableCell>
                      <TableCell className="text-red-600">
                        -{formatAmount(txn.charge_amount)}
                        <div className="text-xs text-gray-500">{txn.charge_type}</div>
                      </TableCell>
                      <TableCell className="font-semibold text-green-600">
                        {formatAmount(txn.net_amount)}
                      </TableCell>
                      <TableCell>{getStatusBadge(txn.status)}</TableCell>
                      <TableCell>{txn.payment_mode || '-'}</TableCell>
                      <TableCell className="text-sm">{formatDate(txn.created_at)}</TableCell>
                      <TableCell className="text-center">
                        <div className="flex gap-2 justify-center">
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => handleCheckStatus(txn)}
                            disabled={checkingStatus}
                            className="text-xs h-7"
                          >
                            <Eye className="h-3 w-3 mr-1" />
                            Check
                          </Button>
                          {txn.status === 'SUCCESS' && (
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => handleCreateInvoice(txn)}
                              disabled={creatingInvoice === txn.txn_id}
                              className="text-xs h-7 bg-blue-50 hover:bg-blue-100 border-blue-200"
                              title="Create Invoice"
                            >
                              <FileText className="h-3 w-3 mr-1" />
                              {creatingInvoice === txn.txn_id ? 'Creating...' : 'Invoice'}
                            </Button>
                          )}
                          {txn.status === 'INITIATED' && ['HDFC_JVI', 'AU_BANK'].includes(txn.pg_partner) && (
                            <>
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => handleManualSuccess(txn)}
                                disabled={submittingManual}
                                className="text-xs h-7 bg-green-50 hover:bg-green-100 border-green-200"
                                title="Add UTR"
                              >
                                Add UTR
                              </Button>
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => handleManualFailed(txn)}
                                disabled={submittingManual}
                                className="text-xs h-7 bg-red-50 hover:bg-red-100 border-red-200 text-red-600"
                                title="Fail Transaction"
                              >
                                Fail
                              </Button>
                            </>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>

          {/* Pagination */}
          {pagination.pages > 1 && (
            <div className="flex justify-between items-center mt-4">
              <div className="text-sm text-gray-500">
                Page {pagination.page} of {pagination.pages}
              </div>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={pagination.page === 1}
                  onClick={() => setPagination(prev => ({ ...prev, page: prev.page - 1 }))}
                >
                  Previous
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={pagination.page === pagination.pages}
                  onClick={() => setPagination(prev => ({ ...prev, page: prev.page + 1 }))}
                >
                  Next
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Transaction Details Dialog */}
      <Dialog open={showDetailsDialog} onOpenChange={setShowDetailsDialog}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Transaction Details</DialogTitle>
          </DialogHeader>
          {selectedTxn && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-sm text-gray-500">Transaction ID</p>
                  <p className="font-mono text-sm font-medium">{selectedTxn.txn_id}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Order ID</p>
                  <p className="font-mono text-sm font-medium">{selectedTxn.order_id}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Merchant</p>
                  <p className="font-medium">{selectedTxn.merchant_name}</p>
                  <p className="text-xs text-gray-500">{selectedTxn.merchant_id}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Status</p>
                  <div className="mt-1">{getStatusBadge(selectedTxn.status)}</div>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Amount</p>
                  <p className="font-semibold">{formatAmount(selectedTxn.amount)}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Charge Amount</p>
                  <p className="font-semibold text-red-600">-{formatAmount(selectedTxn.charge_amount)}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Net Amount</p>
                  <p className="font-semibold text-green-600">{formatAmount(selectedTxn.net_amount)}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Payment Mode</p>
                  <p className="font-medium">{selectedTxn.payment_mode || '-'}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Customer Name</p>
                  <p className="font-medium">{selectedTxn.payee_name || '-'}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Customer Mobile</p>
                  <p className="font-medium">{selectedTxn.payee_mobile || '-'}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Customer Email</p>
                  <p className="font-medium">{selectedTxn.payee_email || '-'}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">PG Transaction ID</p>
                  <p className="font-mono text-xs">{selectedTxn.pg_txn_id || '-'}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Bank Reference</p>
                  <p className="font-mono text-xs">{selectedTxn.bank_ref_no || '-'}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Created At</p>
                  <p className="text-sm">{formatDate(selectedTxn.created_at)}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Completed At</p>
                  <p className="text-sm">{formatDate(selectedTxn.completed_at)}</p>
                </div>
                {selectedTxn.remarks && (
                  <div className="col-span-2">
                    <p className="text-sm text-gray-500">Remarks</p>
                    <p className="text-sm">{selectedTxn.remarks}</p>
                  </div>
                )}
                {selectedTxn.error_message && (
                  <div className="col-span-2">
                    <p className="text-sm text-gray-500">Error Message</p>
                    <p className="text-sm text-red-600">{selectedTxn.error_message}</p>
                  </div>
                )}
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Manual UTR Dialog */}
      <Dialog open={showUtrDialog} onOpenChange={setShowUtrDialog}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Enter UTR for Transaction</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            {selectedManualTxn && (
              <div className="text-sm space-y-2">
                <p className="break-all"><strong>Transaction ID:</strong> {selectedManualTxn.txn_id}</p>
                <p><strong>Amount:</strong> {formatAmount(selectedManualTxn.amount)}</p>
              </div>
            )}
            <div className="space-y-2">
              <label htmlFor="utr" className="text-sm font-medium">UTR Number</label>
              <Input
                id="utr"
                placeholder="Enter 12-digit UTR number"
                value={utrValue}
                onChange={(e) => setUtrValue(e.target.value)}
              />
            </div>
            <div className="flex justify-end gap-2 pt-4">
              <Button variant="outline" onClick={() => setShowUtrDialog(false)} disabled={submittingManual}>
                Cancel
              </Button>
              <Button onClick={submitManualUtr} disabled={submittingManual || !utrValue.trim()}>
                {submittingManual ? 'Submitting...' : 'Mark Success'}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
