import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { UserPlus, Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import adminAPI from '@/api/admin_api'

export default function UserOnboarding() {
  const [schemes, setSchemes] = useState([])
  const [loading, setLoading] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [formData, setFormData] = useState({
    fullName: '',
    email: '',
    mobile: '',
    merchantType: 'PAYIN',
    schemeId: '',
    // Optional documents
    aadharFront: null,
    aadharBack: null,
    panCard: null,
    gstCertificate: null,
    shopPhoto: null,
    profilePhoto: null,
  })

  useEffect(() => {
    loadSchemes()
  }, [])

  const loadSchemes = async () => {
    try {
      setLoading(true)
      const response = await adminAPI.getSchemes()
      if (response.success) {
        setSchemes(response.schemes.filter(s => s.is_active))
      }
    } catch (error) {
      toast.error('Failed to load schemes')
    } finally {
      setLoading(false)
    }
  }

  // Helper function to generate random strings
  const generateRandomString = (length, chars) => {
    let result = ''
    for (let i = 0; i < length; i++) {
      result += chars.charAt(Math.floor(Math.random() * chars.length))
    }
    return result
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    
    // Validate only the essential fields
    if (!formData.fullName || !formData.email || !formData.mobile || !formData.schemeId || !formData.merchantType) {
      toast.error('Please fill all required basic fields')
      return
    }

    try {
      setSubmitting(true)
      
      const submitData = new FormData()
      
      // 1. Append the actual user inputs
      submitData.append('fullName', formData.fullName)
      submitData.append('email', formData.email)
      submitData.append('mobile', formData.mobile)
      submitData.append('merchantType', formData.merchantType)
      submitData.append('schemeId', formData.schemeId)

      // 2. Generate and append dummy data for everything else
      submitData.append('dob', '1990-01-01')
      
      // Random 12 digit Aadhar
      const dummyAadhar = generateRandomString(12, '0123456789')
      submitData.append('aadharCard', dummyAadhar)
      
      // Random PAN format (5 letters, 4 numbers, 1 letter)
      const dummyPan = generateRandomString(5, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ') + 
                       generateRandomString(4, '0123456789') + 
                       generateRandomString(1, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ')
      submitData.append('panNo', dummyPan)
      
      submitData.append('pincode', generateRandomString(6, '0123456789'))
      submitData.append('state', 'Delhi')
      submitData.append('city', 'New Delhi')
      submitData.append('address', 'Auto Generated Address')
      submitData.append('houseNumber', 'Auto Generated')
      submitData.append('landmark', 'Auto Generated')
      
      submitData.append('accountNum', generateRandomString(12, '0123456789'))
      submitData.append('ifscCode', 'SBIN0001234')
      submitData.append('gstNo', generateRandomString(15, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'))

      const getFileOrEmpty = (file, defaultName) => {
        if (file) return file
        const blob = new Blob(['dummy'], { type: 'image/png' })
        return new File([blob], defaultName, { type: 'image/png' })
      }

      // 3. Append optional files if they were uploaded, or dummy files if they were skipped
      submitData.append('aadharFront', getFileOrEmpty(formData.aadharFront, 'dummy_aadhar_front.png'))
      submitData.append('aadharBack', getFileOrEmpty(formData.aadharBack, 'dummy_aadhar_back.png'))
      submitData.append('panCard', getFileOrEmpty(formData.panCard, 'dummy_pan.png'))
      submitData.append('gstCertificate', getFileOrEmpty(formData.gstCertificate, 'dummy_gst.png'))
      submitData.append('shopPhoto', getFileOrEmpty(formData.shopPhoto, 'dummy_shop.png'))
      submitData.append('profilePhoto', getFileOrEmpty(formData.profilePhoto, 'dummy_profile.png'))
      
      const response = await adminAPI.onboardMerchant(submitData)
      
      if (response.success) {
        toast.success(`Merchant onboarded successfully! Merchant ID: ${response.merchantId}`)
        if (response.emailSent) {
          toast.success('Credentials sent to merchant email')
        } else {
          toast.warning('Failed to send email. Please share credentials manually.')
        }
        
        // Reset form
        setFormData({
          fullName: '',
          email: '',
          mobile: '',
          merchantType: 'PAYIN',
          schemeId: '',
          aadharFront: null,
          aadharBack: null,
          panCard: null,
          gstCertificate: null,
          shopPhoto: null,
          profilePhoto: null,
        })
      }
    } catch (error) {
      toast.error(error.message || 'Failed to onboard merchant')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <UserPlus className="h-8 w-8 text-orange-600" />
          <h1 className="text-3xl font-bold">Add Wallet User</h1>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Fast Onboarding</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-8">
            
            {/* Essential Details Section */}
            <div>
              <h3 className="text-lg font-semibold mb-4 border-b pb-2">Essential Details</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                <div>
                  <Label>Merchant Name *</Label>
                  <Input
                    value={formData.fullName}
                    onChange={(e) => setFormData({ ...formData, fullName: e.target.value })}
                    placeholder="Enter merchant name"
                    required
                  />
                </div>
                <div>
                  <Label>Email *</Label>
                  <Input
                    type="email"
                    value={formData.email}
                    onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                    placeholder="m@example.com"
                    required
                  />
                </div>
                <div>
                  <Label>Mobile Number *</Label>
                  <Input
                    value={formData.mobile}
                    onChange={(e) => setFormData({ ...formData, mobile: e.target.value })}
                    placeholder="Enter mobile number"
                    maxLength={10}
                    required
                  />
                </div>
                
                <div>
                  <Label>Merchant Type *</Label>
                  <select
                    value={formData.merchantType}
                    onChange={(e) => setFormData({ ...formData, merchantType: e.target.value })}
                    className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm"
                    required
                  >
                    <option value="PAYIN">Payin</option>
                    <option value="PAYOUT">Payout</option>
                    <option value="BOTH">Both</option>
                  </select>
                </div>

                <div>
                  <Label>Select Scheme *</Label>
                  <select
                    value={formData.schemeId}
                    onChange={(e) => setFormData({ ...formData, schemeId: e.target.value })}
                    className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm"
                    required
                    disabled={loading || schemes.length === 0}
                  >
                    <option value="">--Select Scheme--</option>
                    {schemes.map(scheme => (
                      <option key={scheme.id} value={scheme.id}>
                        {scheme.scheme_name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            </div>

            {/* Optional Document Uploads Section */}
            <div>
              <h3 className="text-lg font-semibold mb-4 border-b pb-2">Documents (Optional)</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                <div>
                  <Label>Aadhar Card Front</Label>
                  <Input
                    type="file"
                    accept="image/*,.pdf"
                    onChange={(e) => setFormData({ ...formData, aadharFront: e.target.files[0] })}
                    className="cursor-pointer"
                  />
                  {formData.aadharFront && <p className="text-xs text-green-600 mt-1">✓ {formData.aadharFront.name}</p>}
                </div>
                <div>
                  <Label>Aadhar Card Back</Label>
                  <Input
                    type="file"
                    accept="image/*,.pdf"
                    onChange={(e) => setFormData({ ...formData, aadharBack: e.target.files[0] })}
                    className="cursor-pointer"
                  />
                  {formData.aadharBack && <p className="text-xs text-green-600 mt-1">✓ {formData.aadharBack.name}</p>}
                </div>
                <div>
                  <Label>PAN Card</Label>
                  <Input
                    type="file"
                    accept="image/*,.pdf"
                    onChange={(e) => setFormData({ ...formData, panCard: e.target.files[0] })}
                    className="cursor-pointer"
                  />
                  {formData.panCard && <p className="text-xs text-green-600 mt-1">✓ {formData.panCard.name}</p>}
                </div>
                <div>
                  <Label>GST Certificate</Label>
                  <Input
                    type="file"
                    accept="image/*,.pdf"
                    onChange={(e) => setFormData({ ...formData, gstCertificate: e.target.files[0] })}
                    className="cursor-pointer"
                  />
                  {formData.gstCertificate && <p className="text-xs text-green-600 mt-1">✓ {formData.gstCertificate.name}</p>}
                </div>
                <div>
                  <Label>Shop Photo</Label>
                  <Input
                    type="file"
                    accept="image/*"
                    onChange={(e) => setFormData({ ...formData, shopPhoto: e.target.files[0] })}
                    className="cursor-pointer"
                  />
                  {formData.shopPhoto && <p className="text-xs text-green-600 mt-1">✓ {formData.shopPhoto.name}</p>}
                </div>
                <div>
                  <Label>Profile Photo</Label>
                  <Input
                    type="file"
                    accept="image/*"
                    onChange={(e) => setFormData({ ...formData, profilePhoto: e.target.files[0] })}
                    className="cursor-pointer"
                  />
                  {formData.profilePhoto && <p className="text-xs text-green-600 mt-1">✓ {formData.profilePhoto.name}</p>}
                </div>
              </div>
            </div>

            <div className="flex justify-end pt-4 border-t">
              <Button
                type="submit"
                disabled={submitting}
                className="bg-gradient-to-r from-orange-500 to-yellow-400 hover:from-orange-600 hover:to-yellow-500 min-w-32"
              >
                {submitting ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Submitting...
                  </>
                ) : (
                  'Submit'
                )}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
