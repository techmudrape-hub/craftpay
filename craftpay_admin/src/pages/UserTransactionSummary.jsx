import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Badge } from '../components/ui/badge';
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
import { 
  Search, RefreshCw, TrendingUp, TrendingDown, 
  DollarSign, CreditCard, User, Calendar, Clock 
} from 'lucide-react';

export default function UserTransactionSummary() {
  const navigate = useNavigate();
  const [merchants, setMerchants] = useState([]);
  const [selectedMerchant, setSelectedMerchant] = useState('');
  const [merchantDetails, setMerchantDetails] = useState(null);
  const [loading, setLoading] = useState(false);
  const [summary, setSummary] = useState(null);
  
  // Filters
  const [fromDate, setFromDate] = useState('');
  const [toDate, setToDate] = useState('');
  const [fromTime, setFromTime] = useState('');
  const [toTime, setToTime] = useState('');

  useEffect(() => {
    loadMerchants();
    // Set today's date as default
    const today = new Date().toISOString().split('T')[0];
    setFromDate(today);
    setToDate(today);
  }, []);

  const loadMerchants = async () => {
    try {
      if (!adminAPI.isAuthenticated()) {
        toast.error('Please login to continue');
        navigate('/login', { replace: true });
        return;
      }

      const response = await adminAPI.getUserTransactionSummaryMerchants();
      
      if (response.success) {
        setMerchants(response.merchants || []);
      } else {
        toast.error(response.message || 'Failed to load merchants');
      }
    } catch (error) {
      console.error('Load merchants error:', error);
      if (error.message && (error.message.includes('token') || error.message.includes('401'))) {
        toast.error('Session expired. Please login again.');
        navigate('/login', { replace: true });
      } else {
        toast.error('Failed to load merchants');
      }
    }
  };

  const loadSummary = async () => {
    if (!selectedMerchant) {
      toast.error('Please select a user');
      return;
    }

    try {
      setLoading(true);
      
      if (!adminAPI.isAuthenticated()) {
        toast.error('Please login to continue');
        navigate('/login', { replace: true });
        return;
      }

      const params = {
        merchant_id: selectedMerchant
      };

      if (fromDate) params.from_date = fromDate;
      if (toDate) params.to_date = toDate;
      if (fromTime) params.from_time = fromTime;
      if (toTime) params.to_time = toTime;

      const response = await adminAPI.getUserTransactionSummary(params);
      
      if (response.success) {
        setSummary(response);
        setMerchantDetails(response.merchant);
        toast.success('Summary loaded successfully');
      } else {
        toast.error(response.message || 'Failed to load summary');
      }
    } catch (error) {
      console.error('Load summary error:', error);
      if (error.message && (error.message.includes('token') || error.message.includes('401'))) {
        toast.error('Session expired. Please login again.');
        navigate('/login', { replace: true });
      } else {
        toast.error('Failed to load summary');
      }
    } finally {
      setLoading(false);
    }
  };

  const formatAmount = (amount) => {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 2
    }).format(amount || 0);
  };

  const formatDateTime = (dateString) => {
    if (!dateString) return '-';
    return new Date(dateString).toLocaleString('en-IN', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      timeZone: 'Asia/Kolkata'
    });
  };

  const getStatusBadge = (status) => {
    const statusConfig = {
      SUCCESS: { color: 'bg-green-500', text: 'Success' },
      PENDING: { color: 'bg-yellow-500', text: 'Pending' },
      QUEUED: { color: 'bg-blue-500', text: 'Queued' },
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

  const handleClearFilters = () => {
    const today = new Date().toISOString().split('T')[0];
    setFromDate(today);
    setToDate(today);
    setFromTime('');
    setToTime('');
    setSummary(null);
    setMerchantDetails(null);
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">User Transaction Summary</h1>
          <p className="text-gray-500 mt-1">
            View payin and payout summary for any user with date and time filtering
          </p>
        </div>
        <Button variant="outline" onClick={loadMerchants}>
          <RefreshCw className="w-4 h-4 mr-2" />
          Refresh
        </Button>
      </div>

      {/* Filters Card */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Search className="w-5 h-5" />
            Search Filters
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* User Selection */}
            <div className="md:col-span-3">
              <label className="block text-sm font-medium mb-2">
                <User className="w-4 h-4 inline mr-1" />
                Select User *
              </label>
              <select
                className="w-full border rounded-md p-2"
                value={selectedMerchant}
                onChange={(e) => setSelectedMerchant(e.target.value)}
              >
                <option value="">-- Select User --</option>
                {merchants.map((merchant) => (
                  <option key={merchant.merchant_id} value={merchant.merchant_id}>
                    {merchant.full_name} ({merchant.merchant_id})
                  </option>
                ))}
              </select>
            </div>

            {/* Date Filters */}
            <div>
              <label className="block text-sm font-medium mb-2">
                <Calendar className="w-4 h-4 inline mr-1" />
                From Date
              </label>
              <Input
                type="date"
                value={fromDate}
                onChange={(e) => setFromDate(e.target.value)}
                className="w-full"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-2">
                <Calendar className="w-4 h-4 inline mr-1" />
                To Date
              </label>
              <Input
                type="date"
                value={toDate}
                onChange={(e) => setToDate(e.target.value)}
                className="w-full"
              />
            </div>
            <div className="flex items-end">
              <Button 
                onClick={loadSummary}
                disabled={loading || !selectedMerchant}
                className="w-full"
              >
                {loading ? 'Loading...' : 'Get Summary'}
              </Button>
            </div>

            {/* Time Filters (Optional) */}
            <div>
              <label className="block text-sm font-medium mb-2">
                <Clock className="w-4 h-4 inline mr-1" />
                From Time (IST) - Optional
              </label>
              <Input
                type="time"
                value={fromTime}
                onChange={(e) => setFromTime(e.target.value)}
                className="w-full"
                placeholder="HH:MM"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-2">
                <Clock className="w-4 h-4 inline mr-1" />
                To Time (IST) - Optional
              </label>
              <Input
                type="time"
                value={toTime}
                onChange={(e) => setToTime(e.target.value)}
                className="w-full"
                placeholder="HH:MM"
              />
            </div>
            <div className="flex items-end">
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

      {/* Summary Cards */}
      {summary && merchantDetails && (
        <>
          {/* Merchant Info */}
          <Card className="bg-gradient-to-r from-purple-50 to-blue-50">
            <CardContent className="pt-6">
              <div className="flex items-center gap-4">
                <div className="w-16 h-16 bg-purple-600 rounded-full flex items-center justify-center text-white text-2xl font-bold">
                  {merchantDetails.full_name.charAt(0).toUpperCase()}
                </div>
                <div>
                  <h2 className="text-2xl font-bold">{merchantDetails.full_name}</h2>
                  <p className="text-gray-600">ID: {merchantDetails.merchant_id}</p>
                  <p className="text-sm text-gray-500">{merchantDetails.email} | {merchantDetails.mobile}</p>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Payin Summary */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-green-600">
                <TrendingUp className="w-6 h-6" />
                Payin Summary
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div className="bg-green-50 p-4 rounded-lg">
                  <p className="text-sm text-gray-600 mb-1">Total Payin</p>
                  <p className="text-2xl font-bold text-green-600">
                    {formatAmount(summary.payin_summary.total_payin)}
                  </p>
                  <p className="text-xs text-gray-500 mt-1">
                    {summary.payin_summary.success_count} successful transactions
                  </p>
                </div>
                <div className="bg-red-50 p-4 rounded-lg">
                  <p className="text-sm text-gray-600 mb-1">Total Charges</p>
                  <p className="text-2xl font-bold text-red-600">
                    -{formatAmount(summary.payin_summary.total_charges)}
                  </p>
                  <p className="text-xs text-gray-500 mt-1">Deducted from payin</p>
                </div>
                <div className="bg-blue-50 p-4 rounded-lg">
                  <p className="text-sm text-gray-600 mb-1">Net Payin</p>
                  <p className="text-2xl font-bold text-blue-600">
                    {formatAmount(summary.payin_summary.net_payin)}
                  </p>
                  <p className="text-xs text-gray-500 mt-1">After deducting charges</p>
                </div>
                <div className="bg-gray-50 p-4 rounded-lg">
                  <p className="text-sm text-gray-600 mb-1">Transaction Status</p>
                  <div className="space-y-1 mt-2">
                    <p className="text-sm">
                      <span className="text-green-600 font-semibold">{summary.payin_summary.success_count}</span> Success
                    </p>
                    <p className="text-sm">
                      <span className="text-yellow-600 font-semibold">{summary.payin_summary.pending_count}</span> Pending
                    </p>
                    <p className="text-sm">
                      <span className="text-red-600 font-semibold">{summary.payin_summary.failed_count}</span> Failed
                    </p>
                  </div>
                </div>
              </div>

              {/* Recent Payins */}
              {summary.recent_payins && summary.recent_payins.length > 0 && (
                <div className="mt-6">
                  <h3 className="text-lg font-semibold mb-3">Recent Payin Transactions</h3>
                  <div className="overflow-x-auto">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Transaction ID</TableHead>
                          <TableHead>Amount</TableHead>
                          <TableHead>Charge</TableHead>
                          <TableHead>Net Amount</TableHead>
                          <TableHead>Status</TableHead>
                          <TableHead>Date & Time (IST)</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {summary.recent_payins.map((txn) => (
                          <TableRow key={txn.txn_id}>
                            <TableCell className="font-mono text-sm">{txn.txn_id}</TableCell>
                            <TableCell className="font-semibold">{formatAmount(txn.amount)}</TableCell>
                            <TableCell className="text-red-600">-{formatAmount(txn.charge_amount)}</TableCell>
                            <TableCell className="font-semibold text-green-600">{formatAmount(txn.net_amount)}</TableCell>
                            <TableCell>{getStatusBadge(txn.status)}</TableCell>
                            <TableCell className="text-sm">{formatDateTime(txn.created_at)}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Payout Summary */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-orange-600">
                <TrendingDown className="w-6 h-6" />
                Payout Summary
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div className="bg-orange-50 p-4 rounded-lg">
                  <p className="text-sm text-gray-600 mb-1">Total Payout</p>
                  <p className="text-2xl font-bold text-orange-600">
                    {formatAmount(summary.payout_summary.total_payout)}
                  </p>
                  <p className="text-xs text-gray-500 mt-1">
                    {summary.payout_summary.success_count} successful transactions
                  </p>
                </div>
                <div className="bg-red-50 p-4 rounded-lg">
                  <p className="text-sm text-gray-600 mb-1">Total Charges</p>
                  <p className="text-2xl font-bold text-red-600">
                    +{formatAmount(summary.payout_summary.total_charges)}
                  </p>
                  <p className="text-xs text-gray-500 mt-1">Added to payout</p>
                </div>
                <div className="bg-purple-50 p-4 rounded-lg">
                  <p className="text-sm text-gray-600 mb-1">Net Payout</p>
                  <p className="text-2xl font-bold text-purple-600">
                    {formatAmount(summary.payout_summary.net_payout)}
                  </p>
                  <p className="text-xs text-gray-500 mt-1">After adding charges</p>
                </div>
                <div className="bg-gray-50 p-4 rounded-lg">
                  <p className="text-sm text-gray-600 mb-1">Transaction Status</p>
                  <div className="space-y-1 mt-2">
                    <p className="text-sm">
                      <span className="text-green-600 font-semibold">{summary.payout_summary.success_count}</span> Success
                    </p>
                    <p className="text-sm">
                      <span className="text-yellow-600 font-semibold">{summary.payout_summary.pending_count}</span> Pending
                    </p>
                    <p className="text-sm">
                      <span className="text-red-600 font-semibold">{summary.payout_summary.failed_count}</span> Failed
                    </p>
                  </div>
                </div>
              </div>

              {/* Recent Payouts */}
              {summary.recent_payouts && summary.recent_payouts.length > 0 && (
                <div className="mt-6">
                  <h3 className="text-lg font-semibold mb-3">Recent Payout Transactions</h3>
                  <div className="overflow-x-auto">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Transaction ID</TableHead>
                          <TableHead>Beneficiary</TableHead>
                          <TableHead>Amount</TableHead>
                          <TableHead>Charge</TableHead>
                          <TableHead>Status</TableHead>
                          <TableHead>Date & Time (IST)</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {summary.recent_payouts.map((txn) => (
                          <TableRow key={txn.txn_id}>
                            <TableCell className="font-mono text-sm">{txn.txn_id}</TableCell>
                            <TableCell>
                              <div>
                                <div className="font-medium">{txn.bene_name || '-'}</div>
                                <div className="text-xs text-gray-500">{txn.account_no || '-'}</div>
                              </div>
                            </TableCell>
                            <TableCell className="font-semibold">{formatAmount(txn.amount)}</TableCell>
                            <TableCell className="text-red-600">+{formatAmount(txn.charge_amount)}</TableCell>
                            <TableCell>{getStatusBadge(txn.status)}</TableCell>
                            <TableCell className="text-sm">{formatDateTime(txn.created_at)}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </>
      )}

      {/* No Data Message */}
      {!summary && !loading && (
        <Card>
          <CardContent className="py-12 text-center">
            <DollarSign className="w-16 h-16 mx-auto text-gray-300 mb-4" />
            <p className="text-gray-500 text-lg">Select a user and click "Get Summary" to view transaction data</p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
