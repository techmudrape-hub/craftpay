import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Badge } from '../components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../components/ui/dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { toast } from 'sonner';
import adminAPI from '../api/admin_api';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../components/ui/table';
import { Search, AlertTriangle, CheckCircle, XCircle, Loader2, Download } from 'lucide-react';

export default function ManualReconciliation() {
  const navigate = useNavigate();
  
  // Tab state
  const [activeTab, setActiveTab] = useState('search');
  
  // Search tab state
  const [searchType, setSearchType] = useState('payin');
  const [searchField, setSearchField] = useState('txn_id');
  const [searchValue, setSearchValue] = useState('');
  const [fromDateTime, setFromDateTime] = useState('');
  const [toDateTime, setToDateTime] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [searchPagination, setSearchPagination] = useState({ page: 1, page_size: 50, total_count: 0, total_pages: 0 });
  
  // Bulk tab state
  const [bulkType, setBulkType] = useState('payin');
  const [selectedMerchant, setSelectedMerchant] = useState('');
  const [merchants, setMerchants] = useState([]);
  const [bulkFromDateTime, setBulkFromDateTime] = useState('');
  const [bulkToDateTime, setBulkToDateTime] = useState('');
  const [bulkTransactions, setBulkTransactions] = useState([]);
  const [selectedTxns, setSelectedTxns] = useState([]);
  const [loadingBulk, setLoadingBulk] = useState(false);
  const [bulkPagination, setBulkPagination] = useState({ page: 1, page_size: 100, total_count: 0, total_pages: 0 });
  
  // Mark failed dialog state
  const [showMarkFailedDialog, setShowMarkFailedDialog] = useState(false);
  const [selectedTransaction, setSelectedTransaction] = useState(null);
  const [failReason, setFailReason] = useState('');
  const [marking, setMarking] = useState(false);

  // Mark success dialog state
  const [showMarkSuccessDialog, setShowMarkSuccessDialog] = useState(false);
  const [successUtr, setSuccessUtr] = useState('');
  const [successRemarks, setSuccessRemarks] = useState('');
  const [markingSuccess, setMarkingSuccess] = useState(false);
  
  // Bulk mark failed state
  const [showBulkMarkDialog, setShowBulkMarkDialog] = useState(false);
  const [bulkReason, setBulkReason] = useState('');
  const [bulkProcessing, setBulkProcessing] = useState(false);
  const [bulkProgress, setBulkProgress] = useState({ processed: 0, total: 0, success: 0, failed: 0 });
  const [bulkLogs, setBulkLogs] = useState([]);

  useEffect(() => {
    if (!adminAPI.isAuthenticated()) {
      toast.error('Please login to continue');
      navigate('/login', { replace: true });
      return;
    }
    fetchMerchants();
  }, []);

  const fetchMerchants = async () => {
    try {
      const response = await adminAPI.getManualReconMerchants();
      if (response.success) {
        setMerchants(response.merchants || []);
      }
    } catch (error) {
      console.error('Fetch merchants error:', error);
    }
  };

  const handleSearch = async (page = 1) => {
    if (!searchValue.trim()) {
      toast.error('Please enter a search value');
      return;
    }

    try {
      setSearching(true);
      const response = await adminAPI.searchManualReconTransactions({
        search_type: searchType,
        search_field: searchField,
        search_value: searchValue,
        from_datetime: fromDateTime || undefined,
        to_datetime: toDateTime || undefined,
        page,
        page_size: searchPagination.page_size
      });

      if (response.success) {
        setSearchResults(response.transactions || []);
        setSearchPagination({
          page: response.page,
          page_size: response.page_size,
          total_count: response.total_count,
          total_pages: response.total_pages
        });
        toast.success(`Found ${response.total_count} transaction(s)`);
      } else {
        toast.error(response.message || 'Search failed');
      }
    } catch (error) {
      console.error('Search error:', error);
      toast.error(error.message || 'Search failed');
    } finally {
      setSearching(false);
    }
  };

  const handleLoadBulkTransactions = async (page = 1) => {
    if (!selectedMerchant) {
      toast.error('Please select a merchant');
      return;
    }
    if (!bulkFromDateTime || !bulkToDateTime) {
      toast.error('Please select date range');
      return;
    }

    try {
      setLoadingBulk(true);
      const response = await adminAPI.getBulkInitiatedTransactions({
        txn_type: bulkType,
        merchant_id: selectedMerchant,
        from_datetime: bulkFromDateTime,
        to_datetime: bulkToDateTime,
        page,
        page_size: bulkPagination.page_size
      });

      if (response.success) {
        setBulkTransactions(response.transactions || []);
        setBulkPagination({
          page: response.page,
          page_size: response.page_size,
          total_count: response.total_count,
          total_pages: response.total_pages
        });
        setSelectedTxns([]);
        toast.success(`Loaded ${response.total_count} initiated transaction(s)`);
      } else {
        toast.error(response.message || 'Failed to load transactions');
      }
    } catch (error) {
      console.error('Load bulk error:', error);
      toast.error(error.message || 'Failed to load transactions');
    } finally {
      setLoadingBulk(false);
    }
  };

  const handleMarkSingleFailed = async () => {
    if (!failReason.trim()) {
      toast.error('Please provide a reason');
      return;
    }

    try {
      setMarking(true);
      const response = await adminAPI.markTransactionFailed({
        txn_type: searchType,
        txn_id: selectedTransaction.txn_id,
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
        setSelectedTransaction(null);
        handleSearch(searchPagination.page);
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

  const handleMarkSingleSuccess = async () => {
    try {
      setMarkingSuccess(true);
      const response = await adminAPI.markTransactionSuccess({
        txn_type: searchType,
        txn_id: selectedTransaction.txn_id,
        utr: successUtr,
        remarks: successRemarks || 'Marked as success by admin'
      });

      if (response.success) {
        toast.success('Transaction marked as success');
        if (response.callback_sent) {
          toast.success('Callback sent successfully');
        } else if (response.callback_message) {
          toast.info(`Callback: ${response.callback_message}`);
        }
        setShowMarkSuccessDialog(false);
        setSuccessUtr('');
        setSuccessRemarks('');
        setSelectedTransaction(null);
        handleSearch(searchPagination.page);
      } else {
        toast.error(response.message || 'Failed to mark transaction as success');
      }
    } catch (error) {
      console.error('Mark success error:', error);
      toast.error(error.message || 'Failed to mark transaction as success');
    } finally {
      setMarkingSuccess(false);
    }
  };

  const handleBulkMarkFailed = async () => {
    if (selectedTxns.length === 0) {
      toast.error('Please select transactions');
      return;
    }
    if (!bulkReason.trim()) {
      toast.error('Please provide a reason');
      return;
    }

    try {
      setBulkProcessing(true);
      setBulkProgress({ processed: 0, total: selectedTxns.length, success: 0, failed: 0 });
      setBulkLogs([]);

      const response = await fetch(`${import.meta.env.VITE_API_BASE_URL}/admin/manual-reconciliation/bulk-mark-failed`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('adminToken')}`
        },
        body: JSON.stringify({
          txn_type: bulkType,
          txn_ids: selectedTxns,
          reason: bulkReason
        })
      });

      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = JSON.parse(line.substring(6));

            if (data.error) {
              toast.error(data.error);
              setBulkProcessing(false);
              return;
            }

            if (data.status === 'started') {
              setBulkProgress(prev => ({ ...prev, total: data.total }));
              setBulkLogs(prev => [...prev, `Started processing ${data.total} transactions...`]);
            } else if (data.progress) {
              setBulkProgress(prev => ({
                processed: data.progress,
                total: data.total,
                success: prev.success + (data.status === 'success' ? 1 : 0),
                failed: prev.failed + (data.status !== 'success' && data.status !== 'already_failed' ? 1 : 0)
              }));
              
              const logMsg = `[${data.progress}/${data.total}] ${data.txn_id}: ${data.status}${data.callback_sent ? ' (callback sent)' : ''}`;
              setBulkLogs(prev => [...prev, logMsg]);
            } else if (data.status === 'completed') {
              setBulkProgress({
                processed: data.total,
                total: data.total,
                success: data.success,
                failed: data.failed
              });
              setBulkLogs(prev => [...prev, `\n✅ Completed! Success: ${data.success}, Failed: ${data.failed}, Callbacks: ${data.callback_success}/${data.callback_success + data.callback_failed}`]);
              toast.success(`Bulk operation completed: ${data.success} succeeded, ${data.failed} failed`);
              
              // Refresh bulk list after completion
              setTimeout(() => {
                handleLoadBulkTransactions(bulkPagination.page);
              }, 2000);
            }
          }
        }
      }
    } catch (error) {
      console.error('Bulk mark failed error:', error);
      toast.error(error.message || 'Bulk operation failed');
    } finally {
      setBulkProcessing(false);
    }
  };

  const toggleSelectAll = () => {
    if (selectedTxns.length === bulkTransactions.length) {
      setSelectedTxns([]);
    } else {
      setSelectedTxns(bulkTransactions.map(t => t.txn_id));
    }
  };

  const toggleSelectTxn = (txnId) => {
    setSelectedTxns(prev => 
      prev.includes(txnId) ? prev.filter(id => id !== txnId) : [...prev, txnId]
    );
  };

  const getStatusBadge = (status) => {
    const colors = {
      SUCCESS: 'bg-green-500',
      FAILED: 'bg-red-500',
      INITIATED: 'bg-blue-500',
      PENDING: 'bg-yellow-500',
      QUEUED: 'bg-orange-500',
      INPROCESS: 'bg-purple-500'
    };
    return <Badge className={colors[status] || 'bg-gray-500'}>{status}</Badge>;
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Manual Reconciliation</h1>
          <p className="text-gray-500 mt-1">Search and manually reconcile transactions</p>
        </div>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-2">
          <TabsTrigger value="search">Search & Mark Failed</TabsTrigger>
          <TabsTrigger value="bulk">Bulk Mark Failed</TabsTrigger>
        </TabsList>

        {/* SEARCH TAB */}
        <TabsContent value="search" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Search Transactions</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                <div>
                  <Label>Transaction Type</Label>
                  <Select value={searchType} onValueChange={setSearchType}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="payin">Payin</SelectItem>
                      <SelectItem value="payout">Payout</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div>
                  <Label>Search Field</Label>
                  <Select value={searchField} onValueChange={setSearchField}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="txn_id">Transaction ID</SelectItem>
                      <SelectItem value="order_id">Order ID</SelectItem>
                      {searchType === 'payout' && <SelectItem value="reference_id">Reference ID</SelectItem>}
                      <SelectItem value="pg_txn_id">PG Transaction ID</SelectItem>
                      {searchType === 'payout' && <SelectItem value="utr">UTR</SelectItem>}
                      {searchType === 'payin' && <SelectItem value="bank_ref_no">Bank Ref No</SelectItem>}
                    </SelectContent>
                  </Select>
                </div>

                <div>
                  <Label>Search Value</Label>
                  <Input
                    placeholder="Enter value to search"
                    value={searchValue}
                    onChange={(e) => setSearchValue(e.target.value)}
                    onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
                  />
                </div>

                <div>
                  <Label>From Date/Time</Label>
                  <Input
                    type="datetime-local"
                    value={fromDateTime}
                    onChange={(e) => setFromDateTime(e.target.value)}
                  />
                </div>

                <div>
                  <Label>To Date/Time</Label>
                  <Input
                    type="datetime-local"
                    value={toDateTime}
                    onChange={(e) => setToDateTime(e.target.value)}
                  />
                </div>

                <div className="flex items-end">
                  <Button onClick={() => handleSearch()} disabled={searching} className="w-full">
                    {searching ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Search className="h-4 w-4 mr-2" />}
                    Search
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>

          {searchResults.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Search Results ({searchPagination.total_count})</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Txn ID</TableHead>
                        <TableHead>Order ID</TableHead>
                        {searchType === 'payout' && <TableHead>Reference ID</TableHead>}
                        <TableHead>Merchant</TableHead>
                        <TableHead>Amount</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>PG Partner</TableHead>
                        <TableHead>Created At</TableHead>
                        <TableHead>Action</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {searchResults.map((txn) => (
                        <TableRow key={txn.id}>
                          <TableCell className="font-mono text-xs">{txn.txn_id}</TableCell>
                          <TableCell className="font-mono text-xs">{txn.order_id}</TableCell>
                          {searchType === 'payout' && <TableCell className="font-mono text-xs">{txn.reference_id}</TableCell>}
                          <TableCell>{txn.merchant_name || txn.merchant_id}</TableCell>
                          <TableCell>₹{parseFloat(txn.amount).toFixed(2)}</TableCell>
                          <TableCell>{getStatusBadge(txn.status)}</TableCell>
                          <TableCell>{txn.pg_partner}</TableCell>
                          <TableCell>{new Date(txn.created_at).toLocaleString()}</TableCell>
                          <TableCell>
                            <div className="flex items-center gap-2">
                              <Button
                                size="sm"
                                className="bg-green-600 hover:bg-green-700 text-white"
                                onClick={() => {
                                  setSelectedTransaction(txn);
                                  setSuccessUtr('');
                                  setSuccessRemarks('');
                                  setShowMarkSuccessDialog(true);
                                }}
                                disabled={txn.status === 'FAILED' || txn.status === 'SUCCESS'}
                              >
                                <CheckCircle className="h-3 w-3 mr-1" />
                                Success
                              </Button>
                              <Button
                                size="sm"
                                variant="destructive"
                                onClick={() => {
                                  setSelectedTransaction(txn);
                                  setShowMarkFailedDialog(true);
                                }}
                                disabled={txn.status === 'FAILED'}
                              >
                                <XCircle className="h-3 w-3 mr-1" />
                                Failed
                              </Button>
                            </div>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>

                {searchPagination.total_pages > 1 && (
                  <div className="flex items-center justify-between mt-4">
                    <Button
                      variant="outline"
                      onClick={() => handleSearch(searchPagination.page - 1)}
                      disabled={searchPagination.page === 1 || searching}
                    >
                      Previous
                    </Button>
                    <span>Page {searchPagination.page} of {searchPagination.total_pages}</span>
                    <Button
                      variant="outline"
                      onClick={() => handleSearch(searchPagination.page + 1)}
                      disabled={searchPagination.page === searchPagination.total_pages || searching}
                    >
                      Next
                    </Button>
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* BULK TAB */}
        <TabsContent value="bulk" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Bulk Mark Failed - Initiated Transactions</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                <div>
                  <Label>Transaction Type</Label>
                  <Select value={bulkType} onValueChange={setBulkType}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="payin">Payin</SelectItem>
                      <SelectItem value="payout">Payout</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div>
                  <Label>Merchant</Label>
                  <Select value={selectedMerchant} onValueChange={setSelectedMerchant}>
                    <SelectTrigger>
                      <SelectValue placeholder="Select merchant" />
                    </SelectTrigger>
                    <SelectContent>
                      {merchants.map((m) => (
                        <SelectItem key={m.merchant_id} value={m.merchant_id}>
                          {m.full_name} ({m.merchant_id})
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div>
                  <Label>From Date/Time</Label>
                  <Input
                    type="datetime-local"
                    value={bulkFromDateTime}
                    onChange={(e) => setBulkFromDateTime(e.target.value)}
                  />
                </div>

                <div>
                  <Label>To Date/Time</Label>
                  <Input
                    type="datetime-local"
                    value={bulkToDateTime}
                    onChange={(e) => setBulkToDateTime(e.target.value)}
                  />
                </div>

                <div className="flex items-end">
                  <Button onClick={() => handleLoadBulkTransactions()} disabled={loadingBulk} className="w-full">
                    {loadingBulk ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Search className="h-4 w-4 mr-2" />}
                    Load Transactions
                  </Button>
                </div>
              </div>

              {bulkTransactions.length > 0 && (
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={toggleSelectAll}
                      >
                        {selectedTxns.length === bulkTransactions.length ? 'Deselect All' : 'Select All'}
                      </Button>
                      <span className="text-sm text-gray-600">
                        {selectedTxns.length} of {bulkPagination.total_count} selected
                      </span>
                    </div>
                    <Button
                      variant="destructive"
                      onClick={() => setShowBulkMarkDialog(true)}
                      disabled={selectedTxns.length === 0}
                    >
                      <AlertTriangle className="h-4 w-4 mr-2" />
                      Mark {selectedTxns.length} as Failed
                    </Button>
                  </div>

                  <div className="overflow-x-auto">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead className="w-12">
                            <input
                              type="checkbox"
                              checked={selectedTxns.length === bulkTransactions.length}
                              onChange={toggleSelectAll}
                              className="cursor-pointer"
                            />
                          </TableHead>
                          <TableHead>Txn ID</TableHead>
                          <TableHead>Order ID</TableHead>
                          {bulkType === 'payout' && <TableHead>Reference ID</TableHead>}
                          <TableHead>Amount</TableHead>
                          <TableHead>Status</TableHead>
                          <TableHead>PG Partner</TableHead>
                          <TableHead>Created At</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {bulkTransactions.map((txn) => (
                          <TableRow key={txn.id}>
                            <TableCell>
                              <input
                                type="checkbox"
                                checked={selectedTxns.includes(txn.txn_id)}
                                onChange={() => toggleSelectTxn(txn.txn_id)}
                                className="cursor-pointer"
                              />
                            </TableCell>
                            <TableCell className="font-mono text-xs">{txn.txn_id}</TableCell>
                            <TableCell className="font-mono text-xs">{txn.order_id}</TableCell>
                            {bulkType === 'payout' && <TableCell className="font-mono text-xs">{txn.reference_id}</TableCell>}
                            <TableCell>₹{parseFloat(txn.amount).toFixed(2)}</TableCell>
                            <TableCell>{getStatusBadge(txn.status)}</TableCell>
                            <TableCell>{txn.pg_partner}</TableCell>
                            <TableCell>{new Date(txn.created_at).toLocaleString()}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>

                  {bulkPagination.total_pages > 1 && (
                    <div className="flex items-center justify-between">
                      <Button
                        variant="outline"
                        onClick={() => handleLoadBulkTransactions(bulkPagination.page - 1)}
                        disabled={bulkPagination.page === 1 || loadingBulk}
                      >
                        Previous
                      </Button>
                      <span>Page {bulkPagination.page} of {bulkPagination.total_pages}</span>
                      <Button
                        variant="outline"
                        onClick={() => handleLoadBulkTransactions(bulkPagination.page + 1)}
                        disabled={bulkPagination.page === bulkPagination.total_pages || loadingBulk}
                      >
                        Next
                      </Button>
                    </div>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Mark as Success Dialog */}
      <Dialog open={showMarkSuccessDialog} onOpenChange={setShowMarkSuccessDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <CheckCircle className="h-5 w-5 text-green-600" />
              Mark Transaction as Success
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label>Transaction ID</Label>
              <Input value={selectedTransaction?.txn_id || ''} disabled />
            </div>
            <div>
              <Label>{searchType === 'payout' ? 'UTR Number (optional)' : 'Bank Ref No / UTR (optional)'}</Label>
              <Input
                placeholder={searchType === 'payout' ? 'Enter UTR number if available' : 'Enter bank reference / UTR if available'}
                value={successUtr}
                onChange={(e) => setSuccessUtr(e.target.value)}
              />
            </div>
            <div>
              <Label>Remarks (optional)</Label>
              <Textarea
                placeholder="Enter remarks for this action"
                value={successRemarks}
                onChange={(e) => setSuccessRemarks(e.target.value)}
                rows={3}
              />
            </div>
            <div className="bg-green-50 border border-green-200 rounded p-3">
              <p className="text-sm text-green-800">
                <CheckCircle className="h-4 w-4 inline mr-2" />
                This will mark the transaction as SUCCESS and send a callback if configured.
              </p>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowMarkSuccessDialog(false)} disabled={markingSuccess}>
              Cancel
            </Button>
            <Button
              className="bg-green-600 hover:bg-green-700 text-white"
              onClick={handleMarkSingleSuccess}
              disabled={markingSuccess}
            >
              {markingSuccess ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <CheckCircle className="h-4 w-4 mr-2" />}
              Mark as Success
            </Button>
          </DialogFooter>
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
              <Input value={selectedTransaction?.txn_id || ''} disabled />
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

      {/* Bulk Mark Failed Dialog */}
      <Dialog open={showBulkMarkDialog} onOpenChange={setShowBulkMarkDialog}>
        <DialogContent className="max-w-3xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Bulk Mark Transactions as Failed</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label>Number of Transactions</Label>
              <Input value={selectedTxns.length} disabled />
            </div>
            <div>
              <Label>Reason for Failure *</Label>
              <Textarea
                placeholder="Enter reason for marking these transactions as failed"
                value={bulkReason}
                onChange={(e) => setBulkReason(e.target.value)}
                rows={4}
                disabled={bulkProcessing}
              />
            </div>
            
            {bulkProcessing && (
              <div className="space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span>Progress: {bulkProgress.processed} / {bulkProgress.total}</span>
                  <span>Success: {bulkProgress.success} | Failed: {bulkProgress.failed}</span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div
                    className="bg-blue-600 h-2 rounded-full transition-all"
                    style={{ width: `${(bulkProgress.processed / bulkProgress.total) * 100}%` }}
                  />
                </div>
                <div className="bg-gray-50 border rounded p-3 max-h-60 overflow-y-auto">
                  <pre className="text-xs whitespace-pre-wrap font-mono">
                    {bulkLogs.join('\n')}
                  </pre>
                </div>
              </div>
            )}

            {!bulkProcessing && (
              <div className="bg-red-50 border border-red-200 rounded p-3">
                <p className="text-sm text-red-800">
                  <AlertTriangle className="h-4 w-4 inline mr-2" />
                  This will mark {selectedTxns.length} transaction(s) as FAILED and send callbacks where configured.
                  This operation cannot be undone.
                </p>
              </div>
            )}
          </div>
          <DialogFooter>
            <Button 
              variant="outline" 
              onClick={() => {
                setShowBulkMarkDialog(false);
                setBulkReason('');
                setBulkLogs([]);
                setBulkProgress({ processed: 0, total: 0, success: 0, failed: 0 });
              }} 
              disabled={bulkProcessing}
            >
              {bulkProcessing ? 'Processing...' : 'Cancel'}
            </Button>
            {!bulkProcessing && (
              <Button 
                variant="destructive" 
                onClick={handleBulkMarkFailed} 
                disabled={!bulkReason.trim()}
              >
                <XCircle className="h-4 w-4 mr-2" />
                Mark {selectedTxns.length} as Failed
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
