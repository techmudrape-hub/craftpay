import { useEffect, useState } from 'react'
import { Navigate } from 'react-router-dom'

export default function QRProtectedRoute({ children }) {
  const [isChecking, setIsChecking] = useState(true)
  const [isAuthenticated, setIsAuthenticated] = useState(false)

  useEffect(() => {
    checkAuth()
  }, [])

  const checkAuth = () => {
    // Check if qrAdminToken exists in localStorage
    const hasToken = !!localStorage.getItem('qrAdminToken')
    
    setIsAuthenticated(hasToken)
    setIsChecking(false)
  }

  if (isChecking) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-purple-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading...</p>
        </div>
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to="/qrlogin" replace />
  }

  return children
}
