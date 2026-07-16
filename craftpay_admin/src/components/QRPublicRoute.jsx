import { Navigate } from 'react-router-dom'

export default function QRPublicRoute({ children }) {
  // If QR Admin is already authenticated, redirect to QR dashboard
  if (!!localStorage.getItem('qrAdminToken')) {
    return <Navigate to="/qrlogin/panel" replace />
  }

  return children
}
