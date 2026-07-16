import { Routes, Route, Navigate } from 'react-router-dom'
import { Toaster } from './components/ui/sonner'
import DashboardLayout from './layout/DashboardLayout'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import ProtectedRoute from './components/ProtectedRoute'
import PublicRoute from './components/PublicRoute'
import { usePageTitle } from './hooks/usePageTitle'

// QR Admin specific
import QRLogin from './pages/QR/QRLogin'
import QRDashboardLayout from './layout/QRDashboardLayout'
import QRProtectedRoute from './components/QRProtectedRoute'
import QRPublicRoute from './components/QRPublicRoute'

// User pages
import UserOnboarding from './pages/User/UserOnboarding'
import UserList from './pages/User/UserList'
import ServiceRouting from './pages/User/ServiceRouting'
import OTPService from './pages/User/OTPService'

// Transaction pages
import PayinReport from './pages/Transactions/PayinReport'
import PayoutReport from './pages/Transactions/PayoutReport'
import PendingPayin from './pages/Transactions/PendingPayin'
import PendingPayout from './pages/Transactions/PendingPayout'

// Manual Reconciliation
import ManualReconciliation from './pages/ManualReconciliation'

// Chargeback Manager
import ChargebackManager from './pages/ChargebackManager'

// User Transaction Summary
import UserTransactionSummary from './pages/UserTransactionSummary'

// Wallet pages
import WalletOverview from './pages/Wallet/WalletOverview'
import WalletStatement from './pages/Wallet/WalletStatement'
import SettleWallet from './pages/Wallet/SettleWallet'
import AutoSettlement from './pages/Wallet/AutoSettlement'

// Fund Manager pages
import TopupFund from './pages/FundManager/TopupFund'
import FundSettlement from './pages/FundManager/FundSettlement'
import FetchFund from './pages/FundManager/FetchFund'
import FundRequests from './pages/FundManager/FundRequests'

// Payout pages
import PersonalPayout from './pages/Payout/PersonalPayout'

// Security pages
import ChangePassword from './pages/Security/ChangePassword'
import ChangePin from './pages/Security/ChangePin'
import IPSecurity from './pages/Security/IPSecurity'

// Settings pages
import BankManagement from './pages/Settings/BankManagement'
import ManageServices from './pages/Settings/ManageServices'
import Commercials from './pages/Settings/Commercials'

// Activity Logs
import ActivityLogs from './pages/ActivityLogs'

// QR Collection
import QRServiceRouting from './pages/QR/QRServiceRouting'
import QRTransactions from './pages/QR/QRTransactions'

function App() {
  // Use the page title hook to dynamically update title based on route
  usePageTitle();
  
  return (
    <>
      <Routes>
        <Route path="/login" element={<PublicRoute><Login /></PublicRoute>} />
        
        <Route path="/qrlogin" element={<QRPublicRoute><QRLogin /></QRPublicRoute>} />
        
        <Route path="/qrlogin/panel" element={<QRProtectedRoute><QRDashboardLayout /></QRProtectedRoute>}>
          <Route index element={<Navigate to="service-routing" replace />} />
          <Route path="service-routing" element={<QRServiceRouting />} />
          <Route path="transactions" element={<QRTransactions />} />
          <Route path="payin-transactions" element={<PayinReport />} />
          <Route path="settle-wallet" element={<SettleWallet />} />
          <Route path="user-transaction-summary" element={<UserTransactionSummary />} />
        </Route>

        <Route path="/" element={<ProtectedRoute><DashboardLayout /></ProtectedRoute>}>
          <Route index element={<Dashboard />} />
          
          {/* User Routes */}
          <Route path="user/onboarding" element={<UserOnboarding />} />
          <Route path="user/list" element={<UserList />} />
          <Route path="user/service-routing" element={<ServiceRouting />} />
          <Route path="user/otp-service" element={<OTPService />} />
          
          {/* Transaction Routes */}
          <Route path="transactions/payin-report" element={<PayinReport />} />
          <Route path="transactions/payout-report" element={<PayoutReport />} />
          <Route path="transactions/pending-payin" element={<PendingPayin />} />
          <Route path="transactions/pending-payout" element={<PendingPayout />} />
          
          {/* Manual Reconciliation Route */}
          <Route path="manual-reconciliation" element={<ManualReconciliation />} />
          
          {/* Chargeback Manager Route */}
          <Route path="chargeback-manager" element={<ChargebackManager />} />
          
          {/* User Transaction Summary Route */}
          <Route path="user-transaction-summary" element={<UserTransactionSummary />} />
          
          {/* Payout Routes */}
          <Route path="payout/personal" element={<PersonalPayout />} />
          
          {/* Wallet Routes */}
          <Route path="wallet/overview" element={<WalletOverview />} />
          <Route path="wallet/statement" element={<WalletStatement />} />
          <Route path="wallet/settle" element={<SettleWallet />} />
          <Route path="wallet/auto-settlement" element={<AutoSettlement />} />
          
          {/* Fund Manager Routes */}
          <Route path="fund-manager/topup" element={<TopupFund />} />
          <Route path="fund-manager/settlement" element={<FundSettlement />} />
          <Route path="fund-manager/fetch" element={<FetchFund />} />
          <Route path="fund-manager/requests" element={<FundRequests />} />
          
          {/* Security Routes */}
          <Route path="security/change-password" element={<ChangePassword />} />
          <Route path="security/change-pin" element={<ChangePin />} />
          <Route path="security/ip-security" element={<IPSecurity />} />
          
          {/* Settings Routes */}
          <Route path="settings/bank" element={<BankManagement />} />
          <Route path="settings/services" element={<ManageServices />} />
          <Route path="settings/commercials" element={<Commercials />} />
          
          {/* Activity Logs */}
          <Route path="activity-logs" element={<ActivityLogs />} />

          {/* QR Collection */}
          <Route path="qr/service-routing" element={<QRServiceRouting />} />
          <Route path="qr/transactions" element={<QRTransactions />} />
        </Route>
        
        <Route path="*" element={<Navigate to="/" />} />
      </Routes>
      <Toaster />
    </>
  )
}

export default App
