import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Badge } from '../../components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../../components/ui/dialog';
import { Label } from '../../components/ui/label';
import { Textarea } from '../../components/ui/textarea';
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
import { Search, Download, RefreshCw, Eye, CheckCircle, Loader2, XCircle, AlertTriangle } from 'lucide-react';

export default function PayoutReport() {
  const navigate = useNavigate();
  const [payouts, setPayouts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [fromDate, setFromDate] = useState('');
  const [toDate, setToDate] = useState('');
  const [selectedPayout, setSelectedPayout] = useState(null);
  const [showDetailsDialog, setShowDetailsDialog] = useState(false);
  const [syncingStatus, setSyncingStatus] = useState({});
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);

  // Mark failed dialog state
  const [showMarkFailedDialog, setShowMarkFailedDialog] = useState(false);
  const [selectedPayoutToFail, setSelectedPayoutToFail] = useState(null);
  const [failReason, setFailReason] = useState('');
  const [marking, setMarking] = useState(false);

  // Restored missing functions
  useEffect(() => {
    fetchPayouts();
  }, [statusFilter, searchTerm, fromDate, toDate, currentPage, pageSize]);

  const fetchPayouts = async () => {
    try {
      setLoading(true);
      
      // Check authentication first
      if (!adminAPI.isAuthenticated()) {
        toast.error('Please login to continue');
        navigate('/login', { replace: true });
        return;
      }

      const params = {
        page: currentPage,
        limit: pageSize
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

      const response = await adminAPI.getPayoutReport(params);
      
      if (response.success) {
        setPayouts(response.data || []);
        // No need for client-side filtering anymore
      } else {
        toast.error(response.message || 'Failed to load payouts');
      }
    } catch (error) {
      console.error('Fetch payouts error:', error);
      
      // Check if it's an authentication error
      if (error.message && (error.message.includes('token') || error.message.includes('401') || error.message.includes('Session expired'))) {
        toast.error('Session expired. Please login again.');
        navigate('/login', { replace: true });
      } else {
        toast.error(error.message || 'Failed to load payouts');
      }
    } finally {
      setLoading(false);
    }
  };

  const getStatusBadge = (status) => {
    const statusConfig = {
      SUCCESS: { color: 'bg-green-500', text: 'Success' },
      FAILED: { color: 'bg-red-500', text: 'Failed' },
      INITIATED: { color: 'bg-blue-500', text: 'Initiated' },
      QUEUED: { color: 'bg-yellow-500', text: 'Queued' },
      INPROCESS: { color: 'bg-orange-500', text: 'In Process' },
      REVERSED: { color: 'bg-purple-500', text: 'Reversed' }
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

  // No client-side filtering - backend handles everything
  const filteredPayouts = payouts;
  const paginatedPayouts = payouts;

  const handleClearFilters = () => {
    setSearchTerm('');
    setStatusFilter('');
    setFromDate('');
    setToDate('');
    setCurrentPage(1);
  };

  const exportToCSV = () => {
    const headers = ['Transaction ID', 'Reference ID', 'Order ID', 'Merchant/Admin', 'Beneficiary', 'Bank', 'IFSC', 'Account No', 'Amount', 'Charges', 'Net Amount', 'Status', 'UTR', 'Date'];
    const rows = filteredPayouts.map(payout => [
      payout.txn_id,
      payout.reference_id,
      payout.order_id || '-',
      payout.payer_name || payout.full_name || 'Admin Payout',
      payout.bene_name,
      payout.bene_bank || '-',
      payout.ifsc_code || '-',
      payout.account_no || payout.vpa || '-',
      payout.net_amount,
      payout.charge_amount,
      payout.amount,
      payout.status,
      payout.utr || payout.bank_ref_no || '-',
      formatDate(payout.created_at)
    ]);

    const csvContent = [
      headers.join(','),
      ...rows.map(row => row.join(','))
    ].join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `payout-report-${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
    window.URL.revokeObjectURL(url);
    toast.success('Report exported successfully');
  };

  const exportTodayReport = async () => {
    try {
      toast.info('Fetching today\'s payouts...');
      
      // Fetch ALL today's payouts from backend
      const response = await adminAPI.getTodayPayoutReport();
      
      if (!response.success || !response.data) {
        toast.error('Failed to fetch today\'s payouts');
        return;
      }

      const todayPayouts = response.data;

      if (todayPayouts.length === 0) {
        toast.error('No payouts found for today');
        return;
      }

      const headers = ['Transaction ID', 'Reference ID', 'Order ID', 'Merchant/Admin', 'Beneficiary', 'Bank', 'IFSC', 'Account No', 'Amount', 'Charges', 'Net Amount', 'Status', 'UTR', 'Date & Time'];
      const rows = todayPayouts.map(payout => [
        payout.txn_id,
        payout.reference_id,
        payout.order_id || '-',
        payout.payer_name || payout.full_name || 'Admin Payout',
        payout.bene_name,
        payout.bene_bank || '-',
        payout.ifsc_code || '-',
        payout.account_no || payout.vpa || '-',
        payout.net_amount,
        payout.charge_amount,
        payout.amount,
        payout.status,
        payout.utr || payout.bank_ref_no || '-',
        formatDate(payout.created_at)
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
      a.download = `payout-report-today-${today}.csv`;
      a.click();
      window.URL.revokeObjectURL(url);
      toast.success(`Today's report exported (${todayPayouts.length} payouts)`);
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
        toast.info('No filters applied. Use "Export All" to download all payouts.');
        return;
      }

      toast.info('Fetching filtered payouts...');
      
      // Build params with current filters
      const params = {};
      if (statusFilter) params.status = statusFilter;
      if (searchTerm) params.search = searchTerm;
      if (fromDate) params.from_date = fromDate;
      if (toDate) params.to_date = toDate;
      
      // Fetch ALL filtered payouts from backend (no pagination)
      const response = await adminAPI.getAllPayoutReport(params);
      
      if (!response.success || !response.data) {
        toast.error('Failed to fetch filtered payouts');
        return;
      }

      const filteredPayouts = response.data;

      if (filteredPayouts.length === 0) {
        toast.error('No payouts found with current filters');
        return;
      }

      const headers = ['Transaction ID', 'Reference ID', 'Order ID', 'Merchant/Admin', 'Beneficiary', 'Bank', 'IFSC', 'Account No', 'Amount', 'Charges', 'Net Amount', 'Status', 'UTR', 'Date & Time'];
      const rows = filteredPayouts.map(payout => [
        payout.txn_id,
        payout.reference_id,
        payout.order_id || '-',
        payout.payer_name || payout.full_name || 'Admin Payout',
        payout.bene_name,
        payout.bene_bank || '-',
        payout.ifsc_code || '-',
        payout.account_no || payout.vpa || '-',
        payout.net_amount,
        payout.charge_amount,
        payout.amount,
        payout.status,
        payout.utr || payout.bank_ref_no || '-',
        formatDate(payout.created_at)
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
      a.download = `payout-report-filtered-${today}.csv`;
      a.click();
      window.URL.revokeObjectURL(url);
      toast.success(`Filtered report exported (${filteredPayouts.length} payouts)`);
    } catch (error) {
      console.error('Export filtered report error:', error);
      toast.error('Failed to export filtered report');
    }
  };

  const handleViewDetails = (payout) => {
    setSelectedPayout(payout);
    setShowDetailsDialog(true);
  };

  const handleMarkSingleFailed = async () => {
    if (!failReason.trim()) {
      toast.error('Please provide a reason');
      return;
    }

    try {
      setMarking(true);
      const response = await adminAPI.markTransactionFailed({
        txn_type: 'payout',
        txn_id: selectedPayoutToFail.txn_id,
        reason: failReason
      });

      if (response.success) {
        toast.success('Transaction marked as failed');
        if (response.callback_sent) {
          toast.success('Callback sent successfully');
        } else if (response.callback_message) {
          toast.info(`Callback: ${response.callback_message}`);
        }
        setShowMarkFailedDialog(false);
        setFailReason('');
        setSelectedPayoutToFail(null);
        fetchPayouts();
      } else {
        toast.error(response.message || 'Failed to mark transaction');
      }
    } catch (error) {
      console.error('Mark failed error:', error);
      toast.error(error.message || 'Failed to mark transaction');
    } finally {
      setMarking(false);
    }
  };

  const handleCheckStatus = async (txnId) => {
    try {
      setSyncingStatus(prev => ({ ...prev, [txnId]: true }));
      
      const response = await adminAPI.syncPayoutStatus(txnId);
      
      if (response.success) {
        toast.success('Status updated successfully');
        // Update the payout in the list
        setPayouts(prevPayouts => 
          prevPayouts.map(p => 
            p.txn_id === txnId ? response.data : p
          )
        );
      } else {
        toast.error(response.message || 'Failed to check status');
      }
    } catch (error) {
      console.error('Check status error:', error);
      toast.error(error.message || 'Failed to check status');
    } finally {
      setSyncingStatus(prev => ({ ...prev, [txnId]: false }));
    }
  };

  // Manual Success one-click handler
  const generateRandomUTR = () => {
    let utr = "61";
    for(let i = 0; i < 10; i++) {
      utr += Math.floor(Math.random() * 10).toString();
    }
    return utr;
  };

  const handlePushCallbackMaxpe = async (payout) => {
    try {
      setSyncingStatus(prev => ({ ...prev, [payout.txn_id]: true }));
      const randomUtr = generateRandomUTR();
      const utrToUse = payout.utr || randomUtr;
      const response = await adminAPI.markTransactionSuccess({
        txn_type: 'payout',
        txn_id: payout.txn_id,
        utr: utrToUse,
        remarks: 'Manual success via Push Callback',
        callback_format: 'maxpe'
      });

      if (response.success) {
        toast.success(`Transaction marked as success and Callback pushed. UTR: ${utrToUse}`);
        if (response.callback_sent) {
          toast.success('Callback sent successfully');
        } else if (response.callback_message) {
          toast.info(`Callback: ${response.callback_message}`);
        }
        fetchPayouts();
      } else {
        toast.error(response.message || 'Failed to push callback');
      }
    } catch (error) {
      console.error('Push callback error:', error);
      toast.error(error.message || 'Failed to push callback');
    } finally {
      setSyncingStatus(prev => ({ ...prev, [payout.txn_id]: false }));
    }
  };

  const handleOneClickSuccess = async (payout) => {
    try {
      setSyncingStatus(prev => ({ ...prev, [payout.txn_id]: true }));
      const randomUtr = generateRandomUTR();
      const response = await adminAPI.markTransactionSuccess({
        txn_type: 'payout',
        txn_id: payout.txn_id,
        utr: randomUtr,
        remarks: 'Manual success via one-click'
      });

      if (response.success) {
        toast.success(`Transaction marked as success. UTR: ${randomUtr}`);
        if (response.callback_sent) {
          toast.success('Callback sent successfully');
        } else if (response.callback_message) {
          toast.info(`Callback: ${response.callback_message}`);
        }
        fetchPayouts();
      } else {
        toast.error(response.message || 'Failed to mark transaction as success');
      }
    } catch (error) {
      console.error('Mark success error:', error);
      toast.error(error.message || 'Failed to mark transaction as success');
    } finally {
      setSyncingStatus(prev => ({ ...prev, [payout.txn_id]: false }));
    }
  };

  if (loading && payouts.length === 0) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-lg">Loading payouts...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">Payout Report</h1>
          <p className="text-gray-500 mt-1">
            View all payout transactions for admin and merchants
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={fetchPayouts}>
            <RefreshCw className="w-4 h-4 mr-2" />
            Refresh
          </Button>
          <Button variant="outline" onClick={exportTodayReport} disabled={payouts.length === 0} className="bg-green-50 hover:bg-green-100 border-green-200">
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
          <Button onClick={exportToCSV} disabled={payouts.length === 0}>
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
                placeholder="Search by TXN ID, Reference ID, Merchant, Beneficiary..."
                value={searchTerm}
                onChange={(e) => {
                  setSearchTerm(e.target.value);
                  setCurrentPage(1);
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
                  setCurrentPage(1);
                }}
              >
                <option value="">All Status</option>
                <option value="SUCCESS">Success</option>
                <option value="FAILED">Failed</option>
                <option value="INITIATED">Initiated</option>
                <option value="QUEUED">Queued</option>
                <option value="INPROCESS">In Process</option>
                <option value="REVERSED">Reversed</option>
              </select>
            </div>
            <div>
              <Input
                type="date"
                placeholder="From Date"
                value={fromDate}
                onChange={(e) => {
                  setFromDate(e.target.value);
                  setCurrentPage(1);
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
                  setCurrentPage(1);
                }}
                className="w-full"
              />
            </div>
            <div>
              <Button
                variant="outline"
                onClick={handleClearFilters}
                className="w-full"
              >
                Clear Filters
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Payouts Table */}
      <Card>
        <CardHeader>
          <div className="flex justify-between items-center">
            <CardTitle>Payout Transactions ({filteredPayouts.length})</CardTitle>
            <div className="flex items-center gap-2">
              <span className="text-sm text-gray-500">Show:</span>
              <select
                className="border rounded-md p-1 text-sm"
                value={pageSize}
                onChange={(e) => {
                  setPageSize(Number(e.target.value));
                  setCurrentPage(1);
                }}
              >
                <option value={10}>10</option>
                <option value={25}>25</option>
                <option value={50}>50</option>
                <option value={100}>100</option>
              </select>
              <span className="text-sm text-gray-500">per page</span>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Transaction ID</TableHead>
                  <TableHead>Reference ID</TableHead>
                  <TableHead>Order ID</TableHead>
                  <TableHead>Merchant/Admin</TableHead>
                  <TableHead>Beneficiary</TableHead>
                  <TableHead>Bank</TableHead>
                  <TableHead>Account No</TableHead>
                  <TableHead>Amount</TableHead>
                  <TableHead>Charges</TableHead>
                  <TableHead>Net Amount</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Payment Type</TableHead>
                  <TableHead>Date</TableHead>
                  <TableHead className="text-center">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {paginatedPayouts.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={14} className="text-center py-8 text-gray-500">
                      No payout transactions found
                    </TableCell>
                  </TableRow>
                ) : (
                  paginatedPayouts.map((payout) => (
                    <TableRow key={payout.id}>
                      <TableCell className="font-mono text-sm">{payout.txn_id}</TableCell>
                      <TableCell className="font-mono text-sm">{payout.reference_id}</TableCell>
                      <TableCell className="font-mono text-sm">{payout.order_id || '-'}</TableCell>
                      <TableCell>
                        <div>
                          <div className="font-medium">{payout.payer_name || payout.full_name || 'Admin Payout'}</div>
                          <div className="text-xs text-gray-500">{payout.merchant_id || payout.admin_id || 'N/A'}</div>
                        </div>
                      </TableCell>
                      <TableCell>
                        <div>
                          <div className="text-sm">{payout.bene_name}</div>
                          <div className="text-xs text-gray-500">{payout.bene_mobile || '-'}</div>
                        </div>
                      </TableCell>
                      <TableCell>{payout.bene_bank || '-'}</TableCell>
                      <TableCell className="font-mono text-sm">{payout.account_no || payout.vpa || '-'}</TableCell>
                      <TableCell className="font-semibold">{formatAmount(payout.net_amount)}</TableCell>
                      <TableCell className="text-red-600">
                        -{formatAmount(payout.charge_amount)}
                        <div className="text-xs text-gray-500">{payout.charge_type}</div>
                      </TableCell>
                      <TableCell className="font-semibold text-green-600">
                        {formatAmount(payout.amount)}
                      </TableCell>
                      <TableCell>{getStatusBadge(payout.status)}</TableCell>
                      <TableCell>{payout.payment_type || 'IMPS'}</TableCell>
                      <TableCell className="text-sm">{formatDate(payout.created_at)}</TableCell>
                      <TableCell className="text-center">
                        <div className="flex gap-1 justify-center">
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => handleViewDetails(payout)}
                            className="text-xs h-7"
                          >
                            <Eye className="h-3 w-3 mr-1" />
                            View
                          </Button>
                          {payout.status === 'INITIATED' && payout.pg_partner === 'Mudrape' && (
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => handleCheckStatus(payout.txn_id)}
                              disabled={syncingStatus[payout.txn_id]}
                              className="text-xs h-7"
                            >
                              <RefreshCw className={`h-3 w-3 mr-1 ${syncingStatus[payout.txn_id] ? 'animate-spin' : ''}`} />
                              {syncingStatus[payout.txn_id] ? 'Checking...' : 'Check'}
                            </Button>
                          )}
                          {(payout.status === 'INITIATED' || payout.status === 'QUEUED') && (
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => handleOneClickSuccess(payout)}
                              disabled={syncingStatus[payout.txn_id]}
                              className="text-xs h-7 border-green-200 text-green-700 hover:bg-green-50"
                            >
                              {syncingStatus[payout.txn_id] ? (
                                <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                              ) : (
                                <CheckCircle className="h-3 w-3 mr-1" />
                              )}
                              {syncingStatus[payout.txn_id] ? 'Processing...' : 'Success'}
                            </Button>
                          )}
                          {(payout.status === 'INITIATED' || payout.status === 'QUEUED' || payout.status === 'INPROCESS' || (payout.status === 'SUCCESS' && payout.pg_partner?.toLowerCase() === 'oqpay')) && (
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => handlePushCallbackMaxpe(payout)}
                              disabled={syncingStatus[payout.txn_id]}
                              className="text-xs h-7 border-blue-200 text-blue-700 hover:bg-blue-50"
                            >
                              {syncingStatus[payout.txn_id] ? (
                                <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                              ) : (
                                <RefreshCw className="h-3 w-3 mr-1" />
                              )}
                              Push Callback
                            </Button>
                          )}
                          <Button
                            size="sm"
                            variant="destructive"
                            onClick={() => {
                              setSelectedPayoutToFail(payout);
                              setShowMarkFailedDialog(true);
                            }}
                            disabled={payout.status === 'FAILED'}
                            className="text-xs h-7"
                          >
                            <XCircle className="h-3 w-3 mr-1" />
                            Failed
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>

          {/* Pagination Controls */}
          {payouts.length > 0 && (
            <div className="flex items-center justify-between mt-4 pt-4 border-t">
              <div className="text-sm text-gray-500">
                Page {currentPage} of {Math.ceil(payouts.length / pageSize)} (Total: {payouts.length} entries)
              </div>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setCurrentPage(1)}
                  disabled={currentPage === 1}
                >
                  First
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
                  disabled={currentPage === 1}
                >
                  Previous
                </Button>
                <span className="text-sm">Page {currentPage}</span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setCurrentPage(prev => prev + 1)}
                  disabled={payouts.length < pageSize}
                >
                  Next
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Payout Details Dialog */}
      <Dialog open={showDetailsDialog} onOpenChange={setShowDetailsDialog}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Payout Transaction Details</DialogTitle>
          </DialogHeader>
          {selectedPayout && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-sm text-gray-500">Transaction ID</p>
                  <p className="font-mono text-sm font-medium">{selectedPayout.txn_id}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Reference ID</p>
                  <p className="font-mono text-sm font-medium">{selectedPayout.reference_id}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Order ID</p>
                  <p className="font-mono text-sm font-medium">{selectedPayout.order_id || '-'}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Merchant/Admin</p>
                  <p className="font-medium">{selectedPayout.payer_name || selectedPayout.full_name || 'Admin Payout'}</p>
                  <p className="text-xs text-gray-500">{selectedPayout.merchant_id || selectedPayout.admin_id || 'N/A'}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Status</p>
                  <div className="mt-1">{getStatusBadge(selectedPayout.status)}</div>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Amount</p>
                  <p className="font-semibold">{formatAmount(selectedPayout.amount)}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Charge Amount</p>
                  <p className="font-semibold text-red-600">-{formatAmount(selectedPayout.charge_amount)}</p>
                  <p className="text-xs text-gray-500">{selectedPayout.charge_type}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Net Amount</p>
                  <p className="font-semibold text-green-600">{formatAmount(selectedPayout.net_amount)}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Payment Type</p>
                  <p className="font-medium">{selectedPayout.payment_type || 'IMPS'}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Beneficiary Name</p>
                  <p className="font-medium">{selectedPayout.bene_name || '-'}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Beneficiary Mobile</p>
                  <p className="font-medium">{selectedPayout.bene_mobile || '-'}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Beneficiary Email</p>
                  <p className="font-medium">{selectedPayout.bene_email || '-'}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Bank Name</p>
                  <p className="font-medium">{selectedPayout.bene_bank || '-'}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">IFSC Code</p>
                  <p className="font-mono text-sm">{selectedPayout.ifsc_code || '-'}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Account Number</p>
                  <p className="font-mono text-sm">{selectedPayout.account_no || '-'}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">VPA/UPI ID</p>
                  <p className="font-mono text-sm">{selectedPayout.vpa || '-'}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">PG Partner</p>
                  <p className="font-medium">{selectedPayout.pg_partner || 'PayU'}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">PG Transaction ID</p>
                  <p className="font-mono text-xs">{selectedPayout.pg_txn_id || '-'}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">UTR Number</p>
                  <p className="font-mono text-xs">{selectedPayout.utr || '-'}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Bank Reference</p>
                  <p className="font-mono text-xs">{selectedPayout.bank_ref_no || '-'}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Name with Bank</p>
                  <p className="text-sm">{selectedPayout.name_with_bank || '-'}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Name Match Score</p>
                  <p className="text-sm">{selectedPayout.name_match_score || '-'}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Created At</p>
                  <p className="text-sm">{formatDate(selectedPayout.created_at)}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Completed At</p>
                  <p className="text-sm">{formatDate(selectedPayout.completed_at)}</p>
                </div>
                {selectedPayout.purpose && (
                  <div className="col-span-2">
                    <p className="text-sm text-gray-500">Purpose</p>
                    <p className="text-sm">{selectedPayout.purpose}</p>
                  </div>
                )}
                {selectedPayout.remarks && (
                  <div className="col-span-2">
                    <p className="text-sm text-gray-500">Remarks</p>
                    <p className="text-sm">{selectedPayout.remarks}</p>
                  </div>
                )}
                {selectedPayout.error_message && (
                  <div className="col-span-2">
                    <p className="text-sm text-gray-500">Error Message</p>
                    <p className="text-sm text-red-600">{selectedPayout.error_message}</p>
                  </div>
                )}
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Mark Single Failed Dialog */}
      <Dialog open={showMarkFailedDialog} onOpenChange={setShowMarkFailedDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Mark Transaction as Failed</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label>Transaction ID</Label>
              <Input value={selectedPayoutToFail?.txn_id || ''} disabled />
            </div>
            <div>
              <Label>Reason for Failure *</Label>
              <Textarea
                placeholder="Enter reason for marking this transaction as failed"
                value={failReason}
                onChange={(e) => setFailReason(e.target.value)}
                rows={4}
              />
            </div>
            <div className="bg-yellow-50 border border-yellow-200 rounded p-3">
              <p className="text-sm text-yellow-800">
                <AlertTriangle className="h-4 w-4 inline mr-2" />
                This will mark the transaction as FAILED and send a callback if configured.
              </p>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowMarkFailedDialog(false)} disabled={marking}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleMarkSingleFailed} disabled={marking || !failReason.trim()}>
              {marking ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <XCircle className="h-4 w-4 mr-2" />}
              Mark as Failed
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
