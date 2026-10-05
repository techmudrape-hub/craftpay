import { useState, useEffect } from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { List, Eye, EyeOff, RefreshCw, Trash2, ToggleLeft, ToggleRight } from 'lucide-react'
import { toast } from 'sonner'
import clientAPI from '@/api/client_api'

export default function BankManagement() {
  const [loadingBanks, setLoadingBanks] = useState(true)
  const [banks, setBanks] = useState([])
  
  const [showDeleteDialog, setShowDeleteDialog] = useState(false)
  const [deletingBank, setDeletingBank] = useState(null)
  const [deleteTpin, setDeleteTpin] = useState('')
  const [showDeleteTpin, setShowDeleteTpin] = useState(false)

  useEffect(() => {
    loadBanks()
  }, [])

  const loadBanks = async () => {
    try {
      setLoadingBanks(true)
      const response = await clientAPI.getBanks()
      if (response.success) {
        setBanks(response.banks || [])
      }
    } catch (error) {
      toast.error('Failed to load banks')
      console.error('Load banks error:', error)
    } finally {
      setLoadingBanks(false)
    }
  }

  const handleDeleteClick = (bank) => {
    setDeletingBank(bank)
    setDeleteTpin('')
    setShowDeleteDialog(true)
  }

  const handleDeleteConfirm = async () => {
    if (!deleteTpin || deleteTpin.length !== 6) {
      toast.error('Please enter valid 6-digit TPIN')
      return
    }
    try {
      const response = await clientAPI.deleteBank(deletingBank.id, deleteTpin)
      if (response.success) {
        toast.success('Bank deleted successfully!')
        setShowDeleteDialog(false)
        setDeletingBank(null)
        setDeleteTpin('')
        loadBanks()
      }
    } catch (error) {
      toast.error(error.message || 'Failed to delete bank')
    }
  }

  const handleToggleStatus = async (bank) => {
    try {
      const response = await clientAPI.toggleBankStatus(bank.id)
      if (response.success) {
        toast.success(response.message)
        loadBanks()
      }
    } catch (error) {
      toast.error(error.message || 'Failed to toggle bank status')
    }
  }

  const getStatusBadge = (isActive) => {
    return isActive ? (
      <Badge className="bg-green-100 text-green-700 hover:bg-green-100">Active</Badge>
    ) : (
      <Badge className="bg-gray-100 text-gray-700 hover:bg-gray-100">Inactive</Badge>
    )
  }

  return (
    <>
      {/* Delete Dialog */}
      <Dialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Bank Account</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete this bank account? This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <div className="py-4">
            <Label>Enter TPIN to confirm</Label>
            <div className="relative mt-2">
              <Input
                type={showDeleteTpin ? 'text' : 'password'}
                placeholder="Enter 6-digit TPIN"
                value={deleteTpin}
                onChange={(e) => setDeleteTpin(e.target.value.replace(/\D/g, '').slice(0, 6))}
                maxLength="6"
                className="pr-10"
              />
              <button
                type="button"
                onClick={() => setShowDeleteTpin(!showDeleteTpin)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500"
              >
                {showDeleteTpin ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowDeleteDialog(false)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleDeleteConfirm}>
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <div className="space-y-6">
        {/* Page Header */}
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-gradient-to-br from-purple-100 to-indigo-100">
            <List className="h-7 w-7 text-purple-600" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Bank Lists</h1>
            <p className="text-sm text-gray-500">View and manage your registered bank accounts</p>
          </div>
        </div>

        {/* Bank List */}
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between mb-6">
              <div>
                <h2 className="text-lg font-semibold text-gray-800">Registered Banks</h2>
                <p className="text-sm text-gray-500 mt-0.5">
                  {banks.length} / 5 bank accounts added. To add a new bank, go to{' '}
                  <strong>Fund Manager → IMPS Payout → Add Bank</strong>.
                </p>
              </div>
              <Button
                variant="ghost"
                size="sm"
                className="text-gray-600 hover:text-gray-900"
                onClick={loadBanks}
                disabled={loadingBanks}
              >
                <RefreshCw className={`h-4 w-4 ${loadingBanks ? 'animate-spin' : ''}`} />
              </Button>
            </div>

            {/* Notes */}
            <div className="mb-4 space-y-1">
              <p className="text-sm text-gray-700"><span className="font-semibold">Note:</span></p>
              <p className="text-sm text-gray-600">1. Maximum 5 banks allowed to add.</p>
              <p className="text-sm text-gray-600">2. You can activate or deactivate your bank accounts.</p>
            </div>

            {loadingBanks ? (
              <div className="flex items-center justify-center py-12">
                <div className="text-center">
                  <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-purple-600 mx-auto" />
                  <p className="mt-4 text-gray-600">Loading banks...</p>
                </div>
              </div>
            ) : (
              <div className="overflow-x-auto border rounded-lg">
                <Table>
                  <TableHeader>
                    <TableRow className="bg-gray-50">
                      <TableHead className="whitespace-nowrap font-semibold">SR. NO.</TableHead>
                      <TableHead className="whitespace-nowrap font-semibold">NAME</TableHead>
                      <TableHead className="whitespace-nowrap font-semibold">ACCOUNT NO</TableHead>
                      <TableHead className="whitespace-nowrap font-semibold">IFSC</TableHead>
                      <TableHead className="whitespace-nowrap font-semibold">BANK NAME</TableHead>
                      <TableHead className="whitespace-nowrap font-semibold">BRANCH NAME</TableHead>
                      <TableHead className="whitespace-nowrap font-semibold">STATUS</TableHead>
                      <TableHead className="whitespace-nowrap font-semibold">ACTIONS</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {banks.length === 0 ? (
                      <TableRow>
                        <TableCell colSpan={8} className="text-center py-10 text-gray-500">
                          <List className="h-8 w-8 mx-auto mb-2 text-gray-300" />
                          No bank accounts found. Add one via <strong>Fund Manager → IMPS Payout → Add Bank</strong>.
                        </TableCell>
                      </TableRow>
                    ) : (
                      banks.map((bank, index) => (
                        <TableRow key={bank.id} className="hover:bg-gray-50">
                          <TableCell>{index + 1}</TableCell>
                          <TableCell className="font-medium">{bank.account_holder_name}</TableCell>
                          <TableCell>{bank.account_number}</TableCell>
                          <TableCell>{bank.ifsc_code}</TableCell>
                          <TableCell className="max-w-xs">{bank.bank_name}</TableCell>
                          <TableCell>{bank.branch_name}</TableCell>
                          <TableCell>{getStatusBadge(bank.is_active)}</TableCell>
                          <TableCell>
                            <div className="flex items-center gap-2">
                              <Button
                                onClick={() => handleToggleStatus(bank)}
                                variant="ghost"
                                size="sm"
                                className={bank.is_active
                                  ? 'text-red-600 hover:text-red-700 hover:bg-red-50'
                                  : 'text-green-600 hover:text-green-700 hover:bg-green-50'}
                                title={bank.is_active ? 'Deactivate' : 'Activate'}
                              >
                                {bank.is_active ? (
                                  <ToggleRight className="h-5 w-5" />
                                ) : (
                                  <ToggleLeft className="h-5 w-5" />
                                )}
                              </Button>
                              <Button
                                onClick={() => handleDeleteClick(bank)}
                                variant="ghost"
                                size="sm"
                                className="text-red-600 hover:text-red-700 hover:bg-red-50"
                              >
                                <Trash2 className="h-4 w-4" />
                              </Button>
                            </div>
                          </TableCell>
                        </TableRow>
                      ))
                    )}
                  </TableBody>
                </Table>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </>
  )
}
