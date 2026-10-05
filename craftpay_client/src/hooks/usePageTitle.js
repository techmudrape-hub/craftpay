import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';

// Map routes to page titles
const routeTitles = {
  '/': 'Dashboard',
  '/login': 'Login',

  // Collections (Payin)
  '/transactions/payin-report': 'Collections',

  // Payouts
  '/transactions/payout-report': 'Payouts',

  // Chargebacks
  '/chargebacks': 'Chargebacks',
  '/chargeback-deductions': 'Chargeback Deductions',

  // Fund Manager
  '/fund-manager/wallet-overview': 'Wallet Overview',
  '/fund-manager/wallet-statement': 'Wallet Statement',
  '/fund-manager/request': 'Fund Request',
  '/fund-manager/settle': 'IMPS Payout',
  '/fund-manager/bank-lists': 'Bank Lists',

  // Collect Payment
  '/collect-payment': 'Collect Payment',

  // Settings
  '/settings/reset-password': 'Reset Password',
  '/settings/rates': 'Rates',

  // Developer Zone
  '/developer/api-docs': 'API Docs',
  '/developer/api-keys': 'API Keys',

  // QR Transactions
  '/qr-transactions': 'QR Transactions',
};

export const usePageTitle = (customTitle = null) => {
  const location = useLocation();

  useEffect(() => {
    const pageTitle = customTitle || routeTitles[location.pathname] || 'CraftPay';
    document.title = `${pageTitle} | CraftPay`;
  }, [location.pathname, customTitle]);
};
