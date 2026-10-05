import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Building, Eye, EyeOff, RefreshCw, Wallet, Plus, Banknote } from 'lucide-react'
import { toast } from 'sonner'
import { clientAPI } from '@/api/client_api'
import clientAPIDefault from '@/api/client_api'
import { formatCurrency, formatDateTime } from '@/lib/utils'

const TABS = [
  { id: 'imps-payout', label: 'IMPS Payout', icon: Banknote },
  { id: 'add-bank', label: 'Add Bank', icon: Plus },
]

// ────────────────────────────────────────────────
// IMPS Payout Panel
// ────────────────────────────────────────────────
function IMPSPayoutPanel() {
  const [banks, setBanks] = useState([])
  const [selectedBank, setSelectedBank] = useState('')
  const [amount, setAmount] = useState('')
  const [tpin, setTpin] = useState('')
  const [showTpin, setShowTpin] = useState(false)
  const [loading, setLoading] = useState(false)
  const [loadingBanks, setLoadingBanks] = useState(true)
  const [walletBalance, setWalletBalance] = useState(0)
  const [transactions, setTransactions] = useState([])

  useEffect(() => {
    fetchBanks()
    fetchWalletBalance()
    fetchTransactions()
  }, [])

  const fetchBanks = async () => {
    try {
      setLoadingBanks(true)
      const response = await clientAPI.getMerchantBanks()
      if (response.success) {
        const bankList = response.banks || response.data || []
        const activeBanks = bankList.filter(bank => bank.is_active)
        setBanks(activeBanks)
      } else {
        toast.error('Failed to load bank accounts')
      }
    } catch (error) {
      console.error('Error fetching banks:', error)
      toast.error('Failed to load bank accounts')
    } finally {
      setLoadingBanks(false)
    }
  }

  const fetchWalletBalance = async () => {
    try {
      const response = await clientAPI.getWalletOverview()
      if (response.success) {
        setWalletBalance(response.data.balance || 0)
      }
    } catch (error) {
      console.error('Error fetching wallet balance:', error)
    }
  }

  const fetchTransactions = async () => {
    try {
      const response = await clientAPI.getClientWalletStatement()
      if (response.success) {
        setTransactions(response.data)
      }
    } catch (error) {
      console.error('Error fetching transactions:', error)
    }
  }

  const handleSettle = async (e) => {
    e.preventDefault()
    if (!selectedBank) { toast.error('Please select a bank account'); return }
    if (!amount || parseFloat(amount) <= 0) { toast.error('Please enter a valid amount'); return }
    if (parseFloat(amount) > walletBalance) { toast.error('Insufficient balance in wallet'); return }
    if (!tpin || tpin.length !== 6) { toast.error('Please enter a valid 6-digit TPIN'); return }

    setLoading(true)
    try {
      const response = await clientAPI.settleFund({
        bank_id: selectedBank,
        amount: parseFloat(amount),
        tpin: tpin
      })
      if (response.success) {
        const chargeInfo = response.charges
          ? ` Charges: ₹${response.charges}, Amount to Bank: ₹${response.net_amount}`
          : ''
        toast.success(`Payout initiated!${chargeInfo}`)
        setSelectedBank('')
        setAmount('')
        setTpin('')
        fetchWalletBalance()
        fetchTransactions()
      } else {
        toast.error(response.message || 'Payout failed')
      }
    } catch (error) {
      toast.error(error.message || 'An error occurred')
    } finally {
      setLoading(false)
    }
  }

  const handleReset = () => {
    setSelectedBank('')
    setAmount('')
    setTpin('')
    toast.info('Form reset')
  }

  return (
    <div className="space-y-6">
      {/* Wallet Balance Card */}
      <Card className="bg-gradient-to-br from-green-500 to-green-600 text-white">
        <CardContent className="pt-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-green-100 text-sm mb-1">Available Wallet Balance</p>
              <p className="text-3xl font-bold">₹{walletBalance.toLocaleString()}</p>
            </div>
            <div className="bg-white/20 p-3 rounded-full">
              <Wallet className="h-8 w-8" />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Payout Form */}
      <Card>
        <CardHeader>
          <CardTitle>Initiate IMPS Payout</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSettle} className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <Label className="text-base font-medium mb-2 block">Select Bank Account</Label>
                {loadingBanks ? (
                  <div className="flex h-12 w-full rounded-md border-2 border-gray-300 bg-gray-50 px-4 py-2 text-base items-center text-gray-500">
                    Loading banks...
                  </div>
                ) : banks.length === 0 ? (
                  <div className="flex h-12 w-full rounded-md border-2 border-orange-200 bg-orange-50 px-4 py-2 text-base items-center text-orange-600">
                    No bank accounts found. Use the <strong className="mx-1">Add Bank</strong> tab to add one.
                  </div>
                ) : (
                  <select
                    value={selectedBank}
                    onChange={(e) => setSelectedBank(e.target.value)}
                    className="flex h-12 w-full rounded-md border-2 border-gray-300 bg-white px-4 py-2 text-base shadow-sm focus:outline-none focus:ring-2 focus:ring-orange-500 focus:border-orange-500"
                    required
                  >
                    <option value="">-- Select Bank Account --</option>
                    {banks.map((bank) => (
                      <option key={bank.id} value={bank.id}>
                        {bank.bank_name} - {bank.account_holder_name} - ****{bank.account_number.slice(-4)}
                      </option>
                    ))}
                  </select>
                )}
              </div>

              <div>
                <Label className="text-base font-medium mb-2 block">Amount</Label>
                <Input
                  type="number"
                  placeholder="Enter amount"
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                  className="h-12 text-base"
                  required
                  min="1"
                  step="0.01"
                  max={walletBalance}
                />
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <Label className="text-base font-medium mb-2 block">TPIN</Label>
                <div className="relative">
                  <Input
                    type={showTpin ? 'text' : 'password'}
                    placeholder="Enter 6-digit TPIN"
                    value={tpin}
                    onChange={(e) => setTpin(e.target.value)}
                    className="h-12 text-base pr-12"
                    required
                    maxLength="6"
                    pattern="[0-9]{6}"
                  />
                  <button
                    type="button"
                    onClick={() => setShowTpin(!showTpin)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-700"
                  >
                    {showTpin ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
                  </button>
                </div>
              </div>
            </div>

            <div className="flex gap-4">
              <Button
                type="submit"
                disabled={loading}
                className="bg-gradient-to-r from-orange-600 to-orange-700 hover:from-orange-700 hover:to-orange-800 text-white px-8 h-11"
              >
                {loading ? 'Processing...' : 'Initiate Payout'}
              </Button>
              <Button
                type="button"
                onClick={handleReset}
                variant="outline"
                className="bg-gray-400 hover:bg-gray-500 text-white px-8 h-11 border-0"
              >
                Reset
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      {/* Transaction History */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>Transaction History</CardTitle>
            <Button variant="ghost" size="sm" onClick={fetchTransactions} className="text-gray-600 hover:text-gray-900">
              <RefreshCw className="h-4 w-4" />
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Transaction ID</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Amount</TableHead>
                  <TableHead>Balance Before</TableHead>
                  <TableHead>Balance After</TableHead>
                  <TableHead>Description</TableHead>
                  <TableHead>Date</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {transactions.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={7} className="text-center text-gray-500">
                      No transactions found
                    </TableCell>
                  </TableRow>
                ) : (
                  transactions.map((txn) => (
                    <TableRow key={txn.id}>
                      <TableCell className="font-medium">{txn.txn_id}</TableCell>
                      <TableCell>
                        <Badge className={txn.txn_type === 'CREDIT' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}>
                          {txn.txn_type}
                        </Badge>
                      </TableCell>
                      <TableCell>{formatCurrency(txn.amount)}</TableCell>
                      <TableCell>{formatCurrency(txn.balance_before)}</TableCell>
                      <TableCell>{formatCurrency(txn.balance_after)}</TableCell>
                      <TableCell>{txn.description}</TableCell>
                      <TableCell>{formatDateTime(txn.created_at)}</TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      {/* Information Card */}
      <Card className="bg-blue-50 border-blue-200">
        <CardContent className="pt-6">
          <h3 className="font-semibold text-blue-900 mb-2">Important Information</h3>
          <ul className="text-sm text-blue-800 space-y-1 list-disc list-inside">
            <li>Payout charges will be deducted from the settlement amount as per your scheme</li>
            <li>Example: If you settle ₹100 with ₹10 charges, ₹100 is deducted from wallet and ₹90 goes to bank</li>
            <li>Funds will be transferred to your selected bank account</li>
            <li>TPIN is required for security verification</li>
            <li>Settlement may take 1-2 business days</li>
          </ul>
        </CardContent>
      </Card>
    </div>
  )
}

// ────────────────────────────────────────────────
// Add Bank Panel
// ────────────────────────────────────────────────
function AddBankPanel() {
  const [loading, setLoading] = useState(false)
  const [bankName, setBankName] = useState('')
  const [accountNo, setAccountNo] = useState('')
  const [reAccountNo, setReAccountNo] = useState('')
  const [ifscCode, setIfscCode] = useState('')
  const [branchName, setBranchName] = useState('')
  const [accountHolderName, setAccountHolderName] = useState('')
  const [tpin, setTpin] = useState('')
  const [showTpin, setShowTpin] = useState(false)
  const [bankCount, setBankCount] = useState(0)
  const [loadingCount, setLoadingCount] = useState(true)

  useEffect(() => {
    loadBankCount()
  }, [])

  const loadBankCount = async () => {
    try {
      setLoadingCount(true)
      const response = await clientAPIDefault.getBanks()
      if (response.success) {
        setBankCount((response.banks || []).length)
      }
    } catch {
      // silent
    } finally {
      setLoadingCount(false)
    }
  }

  const handleReset = () => {
    setBankName('')
    setAccountNo('')
    setReAccountNo('')
    setIfscCode('')
    setBranchName('')
    setAccountHolderName('')
    setTpin('')
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (bankCount >= 5) { toast.error('Maximum 5 banks allowed'); return }
    if (!bankName) { toast.error('Please enter a bank name'); return }
    if (!accountNo) { toast.error('Please enter account number'); return }
    if (accountNo !== reAccountNo) { toast.error('Account numbers do not match'); return }
    if (!ifscCode) { toast.error('Please enter IFSC code'); return }
    if (!branchName) { toast.error('Please enter branch name'); return }
    if (!accountHolderName) { toast.error('Please enter account holder name'); return }
    if (!tpin || tpin.length !== 6) { toast.error('Please enter valid 6-digit TPIN'); return }

    setLoading(true)
    try {
      const response = await clientAPIDefault.addBank({
        bankName,
        accountNumber: accountNo,
        reAccountNumber: reAccountNo,
        ifscCode,
        branchName,
        accountHolderName,
        tpin
      })
      if (response.success) {
        toast.success('Bank account added successfully!')
        handleReset()
        loadBankCount()
      }
    } catch (error) {
      toast.error(error.message || 'Failed to add bank account')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Card className="border-0 shadow-none">
      <CardHeader className="px-0 pt-0">
        <CardTitle className="flex items-center gap-2 text-lg text-gray-800">
          <div className="p-2 rounded-lg bg-gradient-to-br from-orange-50 to-amber-50">
            <Building className="h-5 w-5 text-orange-600" />
          </div>
          Add New Bank Account
        </CardTitle>
      </CardHeader>
      <CardContent className="px-0">
        {!loadingCount && bankCount >= 5 && (
          <div className="mb-4 p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
            <p className="text-sm text-yellow-800">
              You have reached the maximum limit of 5 banks. Please delete a bank from <strong>Bank Lists</strong> to add a new one.
            </p>
          </div>
        )}
        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Row 1 */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div>
              <Label className="text-base font-medium mb-2 block">Bank Name</Label>
              <Input
                type="text"
                placeholder="Enter Bank Name"
                value={bankName}
                onChange={(e) => setBankName(e.target.value)}
                className="h-12 text-base"
                required
                disabled={loading}
              />
            </div>
            <div>
              <Label className="text-base font-medium mb-2 block">Account No</Label>
              <Input
                type="text"
                placeholder="Enter Account No"
                value={accountNo}
                onChange={(e) => setAccountNo(e.target.value)}
                className="h-12 text-base"
                required
                disabled={loading}
              />
            </div>
            <div>
              <Label className="text-base font-medium mb-2 block">Re-Enter Account No</Label>
              <Input
                type="text"
                placeholder="Re-Enter Account No"
                value={reAccountNo}
                onChange={(e) => setReAccountNo(e.target.value)}
                className="h-12 text-base"
                required
                disabled={loading}
              />
            </div>
          </div>

          {/* Row 2 */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div>
              <Label className="text-base font-medium mb-2 block">IFSC Code</Label>
              <Input
                type="text"
                placeholder="Enter IFSC Code"
                value={ifscCode}
                onChange={(e) => setIfscCode(e.target.value.toUpperCase())}
                className="h-12 text-base"
                required
                disabled={loading}
              />
            </div>
            <div>
              <Label className="text-base font-medium mb-2 block">Branch Name</Label>
              <Input
                type="text"
                placeholder="Branch Name"
                value={branchName}
                onChange={(e) => setBranchName(e.target.value)}
                className="h-12 text-base"
                required
                disabled={loading}
              />
            </div>
            <div>
              <Label className="text-base font-medium mb-2 block">Account Holder Name</Label>
              <Input
                type="text"
                placeholder="Enter Account Holder Name"
                value={accountHolderName}
                onChange={(e) => setAccountHolderName(e.target.value)}
                className="h-12 text-base"
                required
                disabled={loading}
              />
            </div>
          </div>

          {/* Row 3 - TPIN */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div>
              <Label className="text-base font-medium mb-2 block">TPIN</Label>
              <div className="relative">
                <Input
                  type={showTpin ? 'text' : 'password'}
                  placeholder="TPIN"
                  value={tpin}
                  onChange={(e) => setTpin(e.target.value.replace(/\D/g, '').slice(0, 6))}
                  className="h-12 text-base pr-12"
                  required
                  maxLength="6"
                  disabled={loading}
                />
                <button
                  type="button"
                  onClick={() => setShowTpin(!showTpin)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-700"
                >
                  {showTpin ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
                </button>
              </div>
            </div>
          </div>

          <div className="flex gap-4">
            <Button
              type="submit"
              className="bg-gradient-to-r from-purple-600 to-purple-700 hover:from-purple-700 hover:to-purple-800 text-white px-8 h-11"
              disabled={loading || bankCount >= 5}
            >
              {loading ? 'Submitting...' : 'Submit'}
            </Button>
            <Button
              type="button"
              onClick={handleReset}
              variant="outline"
              className="bg-gray-400 hover:bg-gray-500 text-white px-8 h-11 border-0"
              disabled={loading}
            >
              Reset
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  )
}

// ────────────────────────────────────────────────
// Main IMPS Payout Page
// ────────────────────────────────────────────────
export default function SettleFund() {
  const [activeTab, setActiveTab] = useState('imps-payout')

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center gap-3">
        <div className="p-2.5 rounded-xl bg-gradient-to-br from-orange-100 to-amber-100">
          <Banknote className="h-7 w-7 text-orange-600" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-gray-900">IMPS Payout</h1>
          <p className="text-sm text-gray-500">Settle funds to your bank account via IMPS</p>
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="flex gap-1 p-1 bg-gray-100/80 rounded-xl w-fit">
        {TABS.map((tab) => {
          const Icon = tab.icon
          const isActive = activeTab === tab.id
          return (
            <button
              key={tab.id}
              id={`tab-imps-${tab.id}`}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-semibold transition-all duration-200 ${
                isActive
                  ? 'bg-white text-orange-700 shadow-sm'
                  : 'text-gray-500 hover:text-gray-700 hover:bg-white/50'
              }`}
            >
              <Icon size={15} />
              {tab.label}
            </button>
          )
        })}
      </div>

      {/* Tab Content */}
      <div>
        {activeTab === 'imps-payout' && <IMPSPayoutPanel />}
        {activeTab === 'add-bank' && (
          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
            <AddBankPanel />
          </div>
        )}
      </div>
    </div>
  )
}
