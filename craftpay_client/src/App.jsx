import { Routes, Route, Navigate } from 'react-router-dom'
import { Toaster } from './components/ui/sonner'
import ProtectedRoute from './components/ProtectedRoute'
import PublicRoute from './components/PublicRoute'
import DashboardLayout from './layout/DashboardLayout'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import { usePageTitle } from './hooks/usePageTitle'

// Transaction pages (Collections / Payouts)
import PayinReport from './pages/Transactions/PayinReport'
import PayoutReport from './pages/Transactions/PayoutReport'

// Wallet pages (now under Fund Manager)
import WalletOverview from './pages/Wallet/WalletOverview'
import WalletStatement from './pages/Wallet/WalletStatement'

// Fund Manager pages
import SettleFund from './pages/FundManager/SettleFund'
import FundRequest from './pages/FundManager/FundRequest'

// Security pages (kept for internal use / old route redirects)
import ChangePassword from './pages/Security/ChangePassword'
import ChangePin from './pages/Security/ChangePin'

// Developer Zone pages
import Documentation from './pages/DeveloperZone/Documentation'
import Credentials from './pages/DeveloperZone/Credentials'

// Settings pages
import BankManagement from './pages/Settings/BankManagement'
import ResetPassword from './pages/Settings/ResetPassword'

// Collect Payment (formerly Generate QR)
import GenerateQR from './pages/GenerateQR'

// Rates (formerly My Commercials)
import MyCommercials from './pages/MyCommercials'

// Chargebacks
import Chargebacks from './pages/Chargebacks'
import ChargebackDeductions from './pages/ChargebackDeductions'

// MaxPe Checkout
import MaxpeCheckout from './pages/MaxpeCheckout'

// QR Transactions
import QRTransactions from './pages/QRTransactions/QRTransactions'

function App() {
  // Use the page title hook to dynamically update title based on route
  usePageTitle();

  return (
    <>
      <Routes>
        {/* Public Route - MaxPe Checkout (no auth required) */}
        <Route path="/checkout/maxpe" element={<MaxpeCheckout />} />

        {/* Public Route - Login */}
        <Route
          path="/login"
          element={
            <PublicRoute>
              <Login />
            </PublicRoute>
          }
        />

        {/* Protected Routes - Dashboard */}
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <DashboardLayout />
            </ProtectedRoute>
          }
        >
          <Route index element={<Dashboard />} />

          {/* Collections (Payin Report) */}
          <Route path="transactions/payin-report" element={<PayinReport />} />

          {/* Payouts (Payout Report) */}
          <Route path="transactions/payout-report" element={<PayoutReport />} />

          {/* Chargebacks */}
          <Route path="chargebacks" element={<Chargebacks />} />
          <Route path="chargeback-deductions" element={<ChargebackDeductions />} />

          {/* Fund Manager */}
          <Route path="fund-manager/wallet-overview" element={<WalletOverview />} />
          <Route path="fund-manager/wallet-statement" element={<WalletStatement />} />
          <Route path="fund-manager/request" element={<FundRequest />} />
          <Route path="fund-manager/settle" element={<SettleFund />} />
          <Route path="fund-manager/bank-lists" element={<BankManagement />} />

          {/* Collect Payment (Generate QR) */}
          <Route path="collect-payment" element={<GenerateQR />} />

          {/* Settings */}
          <Route path="settings/reset-password" element={<ResetPassword />} />
          <Route path="settings/rates" element={<MyCommercials />} />

          {/* Developer Zone */}
          <Route path="developer/api-docs" element={<Documentation />} />
          <Route path="developer/api-keys" element={<Credentials />} />

          {/* ── Backward-compat redirects (old routes → new routes) ── */}
          <Route path="wallet/overview" element={<Navigate to="/fund-manager/wallet-overview" replace />} />
          <Route path="wallet/statement" element={<Navigate to="/fund-manager/wallet-statement" replace />} />
          <Route path="security/change-password" element={<Navigate to="/settings/reset-password" replace />} />
          <Route path="security/change-pin" element={<Navigate to="/settings/reset-password" replace />} />
          <Route path="settings/bank" element={<Navigate to="/fund-manager/bank-lists" replace />} />
          <Route path="generate-qr" element={<Navigate to="/collect-payment" replace />} />
          <Route path="my-commercials" element={<Navigate to="/settings/rates" replace />} />
          <Route path="developer/documentation" element={<Navigate to="/developer/api-docs" replace />} />
          <Route path="developer/credentials" element={<Navigate to="/developer/api-keys" replace />} />

          {/* QR Transactions (conditionally visible in sidebar) */}
          <Route path="qr-transactions" element={<QRTransactions />} />
        </Route>

        {/* Catch all - redirect to home */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      <Toaster />
    </>
  )
}

export default App
