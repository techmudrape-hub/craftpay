import { useState, useEffect } from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Wallet, Eye, EyeOff } from 'lucide-react'
import { toast } from 'sonner'
import adminAPI from '@/api/admin_api'

export default function PersonalPayout() {
  const [banks, setBanks] = useState([])
  const [selectedBank, setSelectedBank] = useState('')
  const [amount, setAmount] = useState('')
  const [tpin, setTpin] = useState('')
  const [showTpin, setShowTpin] = useState(false)
  const [loading, setLoading] = useState(false)
  const [pgPartner, setPgPartner] = useState('')  // Payment gateway selection
  const [pgPartners, setPgPartners] = useState([])  // Available payment gateways
  const [loadingPartners, setLoadingPartners] = useState(true)
  const [mobileNumber, setMobileNumber] = useState('')  // Beneficiary mobile number
  const [emailAddress, setEmailAddress] = useState('')  // Beneficiary email address

  useEffect(() => {
    fetchBanks()
    fetchPgPartners()
  }, [])

  const fetchBanks = async () => {
    try {
      const response = await adminAPI.getAdminBanks()
      if (response.success) {
        // Backend returns 'banks' not 'data'
        const bankList = response.banks || []
        setBanks(bankList.filter(bank => bank.is_active))
      }
    } catch (error) {
      console.error('Error fetching banks:', error)
      toast.error('Failed to load bank accounts')
      setBanks([])
    }
  }

  const fetchPgPartners = async () => {
    try {
      setLoadingPartners(true)
      // Fetch payout service routing
      const response = await adminAPI.getServiceRouting('PAYOUT', 'ADMIN')
      if (response.success) {
        const routes = response.routes || []
        // Extract unique PG partners
        const partners = routes
          .filter(route => route.is_active)
          .map(route => ({
            value: route.pg_partner,
            label: route.pg_partner
          }))
        
        // Remove duplicates
        const uniquePartners = partners.filter((partner, index, self) =>
          index === self.findIndex((p) => p.value === partner.value)
        )
        
        setPgPartners(uniquePartners)
        
        // Set first partner as default if available
        if (uniquePartners.length > 0) {
          setPgPartner(uniquePartners[0].value)
        }
      }
    } catch (error) {
      console.error('Error fetching PG partners:', error)
      toast.error('Failed to load payment gateways')
      setPgPartners([])
    } finally {
      setLoadingPartners(false)
    }
  }

  const handlePayout = async (e) => {
    e.preventDefault()
    
    if (!selectedBank) {
      toast.error('Please select a bank account')
      return
    }
    
    if (!amount || parseFloat(amount) <= 0) {
      toast.error('Please enter a valid amount')
      return
    }

    if (!mobileNumber || mobileNumber.length !== 10) {
      toast.error('Please enter a valid 10-digit mobile number')
      return
    }

    if (!emailAddress || !emailAddress.includes('@')) {
      toast.error('Please enter a valid email address')
      return
    }
    
    if (!tpin || tpin.length !== 6) {
      toast.error('Please enter a valid 6-digit TPIN')
      return
    }
    
    setLoading(true)
    
    try {
      const response = await adminAPI.personalPayout({
        bank_id: selectedBank,
        amount: parseFloat(amount),
        mobile_number: mobileNumber,
        email_address: emailAddress,
        tpin: tpin,
        pg_partner: pgPartner  // Use selected payment gateway
      })
      
      if (response.success) {
        toast.success('Payout processed successfully!')
        // Reset form
        setSelectedBank('')
        setAmount('')
        setMobileNumber('')
        setEmailAddress('')
        setTpin('')
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
    setMobileNumber('')
    setEmailAddress('')
    setTpin('')
    // Reset to first available partner
    if (pgPartners.length > 0) {
      setPgPartner(pgPartners[0].value)
    }
    toast.info('Form reset')
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Wallet className="h-8 w-8 text-purple-600" />
        <h1 className="text-3xl font-bold">Personal Payout</h1>
      </div>

      <Card>
        <CardContent className="pt-6">
          <form onSubmit={handlePayout} className="space-y-6">
            {/* First Row - Bank Account and Amount */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <Label className="text-base font-medium mb-2 block">Select Bank Account</Label>
                <select
                  value={selectedBank}
                  onChange={(e) => setSelectedBank(e.target.value)}
                  className="flex h-12 w-full rounded-md border-2 border-gray-300 bg-white px-4 py-2 text-base shadow-sm focus:outline-none focus:ring-2 focus:ring-purple-500"
                  required
                >
                  <option value="">Select Bank Account</option>
                  {banks.map((bank) => (
                    <option key={bank.id} value={bank.id}>
                      {bank.bank_name} - {bank.account_number.slice(-4).padStart(bank.account_number.length, '*')}
                    </option>
                  ))}
                </select>
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
                />
              </div>

              {/* Mobile Number and Email Address */}
              <div>
                <Label className="text-base font-medium mb-2 block">Mobile Number</Label>
                <Input
                  type="tel"
                  placeholder="Enter 10-digit mobile number"
                  value={mobileNumber}
                  onChange={(e) => setMobileNumber(e.target.value.replace(/\D/g, '').slice(0, 10))}
                  className="h-12 text-base"
                  required
                  maxLength="10"
                  pattern="[0-9]{10}"
                />
              </div>

              <div>
                <Label className="text-base font-medium mb-2 block">Email Address</Label>
                <Input
                  type="email"
                  placeholder="Enter email address"
                  value={emailAddress}
                  onChange={(e) => setEmailAddress(e.target.value)}
                  className="h-12 text-base"
                  required
                />
              </div>

              <div>
                <Label className="text-base font-medium mb-2 block">Payment Gateway</Label>
                <select
                  value={pgPartner}
                  onChange={(e) => setPgPartner(e.target.value)}
                  className="flex h-12 w-full rounded-md border-2 border-gray-300 bg-white px-4 py-2 text-base shadow-sm focus:outline-none focus:ring-2 focus:ring-purple-500"
                  required
                  disabled={loadingPartners || pgPartners.length === 0}
                >
                  {loadingPartners ? (
                    <option value="">Loading payment gateways...</option>
                  ) : pgPartners.length === 0 ? (
                    <option value="">No payment gateways configured</option>
                  ) : (
                    <>
                      <option value="">Select Payment Gateway</option>
                      {pgPartners.map((partner) => (
                        <option key={partner.value} value={partner.value}>
                          {partner.label}
                        </option>
                      ))}
                    </>
                  )}
                </select>
                {!loadingPartners && pgPartners.length === 0 && (
                  <p className="text-xs text-red-600 mt-1">
                    Please configure payout service routing in Settings
                  </p>
                )}
              </div>

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
                    {showTpin ? (
                      <EyeOff className="h-5 w-5" />
                    ) : (
                      <Eye className="h-5 w-5" />
                    )}
                  </button>
                </div>
              </div>
            </div>

            {/* Buttons */}
            <div className="flex gap-4 pt-4">
              <Button
                type="submit"
                disabled={loading}
                className="bg-gradient-to-r from-purple-600 to-purple-700 hover:from-purple-700 hover:to-purple-800 text-white px-8 h-11"
              >
                {loading ? 'Processing...' : 'Process Payout'}
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

      {/* Information Card */}
      <Card className="bg-blue-50 border-blue-200">
        <CardContent className="pt-6">
          <h3 className="font-semibold text-blue-900 mb-2">Important Information</h3>
          <ul className="text-sm text-blue-800 space-y-1 list-disc list-inside">
            <li>Payout charges will be deducted as per your scheme</li>
            <li>Ensure sufficient balance in your wallet</li>
            <li>TPIN is required for security verification</li>
            <li>Transaction will be processed through the selected payment gateway</li>
          </ul>
        </CardContent>
      </Card>
    </div>
  )
}
