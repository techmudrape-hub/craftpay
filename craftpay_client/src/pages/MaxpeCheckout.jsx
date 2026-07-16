import { useEffect, useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { Loader2, CheckCircle2, XCircle, Smartphone, Receipt } from 'lucide-react';

const MaxpeCheckout = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  
  const [status, setStatus] = useState('validating'); // validating, pending, loading, success, failed, expired
  const [orderDetails, setOrderDetails] = useState(null);
  const [transactionData, setTransactionData] = useState(null);
  const [error, setError] = useState(null);
  const [pollingInterval, setPollingInterval] = useState(null);
  const [timeRemaining, setTimeRemaining] = useState(360); // 6 minutes = 360 seconds;
  
  // Get parameters from URL - all dynamic
  const intentUrl = searchParams.get('intent_url');
  const orderId = searchParams.get('order_id');
  const amount = searchParams.get('amount');
  const txnId = searchParams.get('txn_id');
  const merchantId = searchParams.get('merchant_id');
  
  useEffect(() => {
    // Validate required parameters
    if (!intentUrl || !orderId || !amount) {
      setError('Invalid checkout link. Missing required parameters.');
      setStatus('failed');
    } else {
      setOrderDetails({
        orderId,
        amount: parseFloat(amount).toFixed(2),
        txnId: txnId || orderId,
        merchantId: merchantId
      });
      
      // Validate if link is still valid (not already completed)
      validateCheckoutLink();
    }
    
    // Add visibility change listener to check status when user returns to page
    // This is critical for iOS Safari which throttles background timers
    const handleVisibilityChange = async () => {
      if (!document.hidden) {
        console.log('[Visibility] Page became visible, checking status immediately');
        
        try {
          // Check status from backend (source of truth)
          const response = await fetch(
            `${import.meta.env.VITE_API_URL}/api/checkout/maxpe/status?order_id=${orderId}`
          );
          const data = await response.json();
          
          console.log('[Visibility Check] Status response:', data);
          
          if (data.success && data.transaction) {
            const txnStatus = data.transaction.status;
            
            if (txnStatus === 'SUCCESS') {
              console.log('[Visibility Check] ✅ Payment successful!');
              setStatus('success');
              setTransactionData({
                orderId: data.transaction.order_id,
                amount: parseFloat(data.transaction.amount).toFixed(2),
                utr: data.transaction.bank_ref_no || data.transaction.utr || 'N/A',
                txnId: data.transaction.txn_id,
                completedAt: data.transaction.completed_at
              });
              if (pollingInterval) {
                clearInterval(pollingInterval);
                setPollingInterval(null);
              }
            } else if (txnStatus === 'EXPIRED') {
              console.log('[Visibility Check] ⏰ Link expired!');
              setStatus('expired');
              setError('This payment link has expired. Payment links are valid for 6 minutes only.');
              if (pollingInterval) {
                clearInterval(pollingInterval);
                setPollingInterval(null);
              }
            } else if (txnStatus === 'FAILED') {
              console.log('[Visibility Check] ❌ Payment failed!');
              setStatus('failed');
              setError('Payment failed. Please try again.');
              if (pollingInterval) {
                clearInterval(pollingInterval);
                setPollingInterval(null);
              }
            }
            
            // Update timer if still pending
            if (txnStatus === 'PENDING' || txnStatus === 'INITIATED') {
              // Use server-calculated time remaining to avoid timezone issues
              if (data.transaction.seconds_remaining !== undefined) {
                setTimeRemaining(data.transaction.seconds_remaining);
                console.log('[Visibility Check] Updated timer:', data.transaction.seconds_remaining, 'seconds');
              }
            }
          }
        } catch (err) {
          console.error('[Visibility Check] Error:', err);
        }
      }
    };
    
    document.addEventListener('visibilitychange', handleVisibilityChange);
    
    // Also check on page focus (iOS Safari specific)
    window.addEventListener('focus', handleVisibilityChange);
    
    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      window.removeEventListener('focus', handleVisibilityChange);
    };
  }, [intentUrl, orderId, amount, txnId, merchantId, pollingInterval]);
  
  // Countdown timer effect - runs independently even when page is minimized
  // For iOS Safari compatibility, we also poll the backend regularly
  useEffect(() => {
    if (status === 'success' || status === 'failed' || status === 'expired') {
      return;
    }
    
    // Decrement timer every second (simple countdown)
    // We sync with server every 10 seconds to correct any drift
    const timerInterval = setInterval(() => {
      setTimeRemaining(prev => {
        const newTime = Math.max(0, prev - 1);
        
        // If timer reaches 0, mark as expired
        if (newTime <= 0) {
          console.log('[Timer] ⏰ Time expired!');
          clearInterval(timerInterval);
          setStatus('expired');
          setError('This payment link has expired. Payment links are valid for 6 minutes only.');
        }
        
        return newTime;
      });
    }, 1000);
    
    // iOS Safari Fix: Poll backend every 10 seconds to sync timer and check status
    // This ensures we catch expiry even if timer is throttled and corrects any drift
    const backendCheckInterval = setInterval(async () => {
      try {
        console.log('[iOS Check] Syncing with backend...');
        const response = await fetch(
          `${import.meta.env.VITE_API_URL}/api/checkout/maxpe/status?order_id=${orderId}`
        );
        const data = await response.json();
        
        if (data.success && data.transaction) {
          // Sync timer with server's calculation (avoids timezone issues)
          if (data.transaction.seconds_remaining !== undefined) {
            setTimeRemaining(data.transaction.seconds_remaining);
            console.log('[iOS Check] Synced timer:', data.transaction.seconds_remaining, 'seconds');
          }
          
          if (data.transaction.status === 'EXPIRED') {
            console.log('[iOS Check] ⏰ Backend says expired!');
            clearInterval(timerInterval);
            clearInterval(backendCheckInterval);
            setStatus('expired');
            setError('This payment link has expired. Payment links are valid for 6 minutes only.');
          } else if (data.transaction.status === 'SUCCESS') {
            console.log('[iOS Check] ✅ Payment successful!');
            clearInterval(timerInterval);
            clearInterval(backendCheckInterval);
            setStatus('success');
            setTransactionData({
              orderId: data.transaction.order_id,
              amount: parseFloat(data.transaction.amount).toFixed(2),
              utr: data.transaction.bank_ref_no || data.transaction.utr || 'N/A',
              txnId: data.transaction.txn_id,
              completedAt: data.transaction.completed_at
            });
          } else if (data.transaction.status === 'FAILED') {
            console.log('[iOS Check] ❌ Payment failed!');
            clearInterval(timerInterval);
            clearInterval(backendCheckInterval);
            setStatus('failed');
            setError('Payment failed. Please try again.');
          }
        }
      } catch (err) {
        console.error('[iOS Check] Error:', err);
      }
    }, 10000); // Check every 10 seconds
    
    return () => {
      clearInterval(timerInterval);
      clearInterval(backendCheckInterval);
    };
  }, [status, orderId]);
  
  const validateCheckoutLink = async () => {
    try {
      console.log('[Validate] Checking if checkout link is still valid...');
      const response = await fetch(
        `${import.meta.env.VITE_API_URL}/api/checkout/maxpe/validate?order_id=${orderId}`
      );
      
      const data = await response.json();
      console.log('[Validate] Response:', data);
      
      if (!data.valid) {
        if (data.reason === 'EXPIRED_TIMEOUT') {
          console.log('[Validate] ⏰ Link expired - 6 minute timeout');
          setStatus('expired');
          if (data.transaction) {
            setTransactionData({
              orderId: data.transaction.order_id,
              amount: parseFloat(data.transaction.amount).toFixed(2),
              txnId: data.transaction.txn_id,
              createdAt: data.transaction.created_at,
              expiredAt: data.transaction.expired_at
            });
          }
          setError('This payment link has expired. Payment links are valid for 6 minutes only.');
        } else if (data.reason === 'ALREADY_COMPLETED') {
          console.log('[Validate] ❌ Link expired - payment already completed');
          
          // Check if transaction was successful or failed
          if (data.transaction) {
            const txnStatus = data.transaction.status;
            
            if (txnStatus === 'SUCCESS') {
              console.log('[Validate] Payment was successful');
              setStatus('success');
              setTransactionData({
                orderId: data.transaction.order_id,
                amount: parseFloat(data.transaction.amount).toFixed(2),
                utr: data.transaction.utr,
                txnId: data.transaction.txn_id,
                completedAt: data.transaction.completed_at
              });
            } else if (txnStatus === 'FAILED') {
              console.log('[Validate] Payment was failed');
              setStatus('failed');
              setTransactionData({
                orderId: data.transaction.order_id,
                amount: parseFloat(data.transaction.amount).toFixed(2),
                txnId: data.transaction.txn_id,
                completedAt: data.transaction.completed_at
              });
              setError('Payment was failed. Please request a new payment link.');
            } else {
              // For other statuses (PENDING, INITIATED, etc.), show expired
              setStatus('expired');
              setTransactionData({
                orderId: data.transaction.order_id,
                amount: parseFloat(data.transaction.amount).toFixed(2),
                utr: data.transaction.utr,
                txnId: data.transaction.txn_id,
                completedAt: data.transaction.completed_at
              });
            }
          } else {
            setStatus('expired');
          }
        } else {
          setError(data.reason || 'This payment link is no longer valid');
          setStatus('failed');
        }
      } else {
        console.log('[Validate] ✅ Link is valid');
        
        // Fetch the transaction to get server-calculated time remaining
        try {
          const statusResponse = await fetch(
            `${import.meta.env.VITE_API_URL}/api/checkout/maxpe/status?order_id=${orderId}`
          );
          const statusData = await statusResponse.json();
          
          if (statusData.success && statusData.transaction) {
            // Use server-calculated time remaining to avoid timezone issues
            if (statusData.transaction.seconds_remaining !== undefined) {
              console.log('[Validate] Setting time remaining from server:', statusData.transaction.seconds_remaining);
              setTimeRemaining(statusData.transaction.seconds_remaining);
            }
          }
        } catch (err) {
          console.error('[Validate] Error fetching time remaining:', err);
        }
        
        setStatus('pending');
      }
    } catch (err) {
      console.error('[Validate] Error:', err);
      // On error, allow payment to proceed
      setStatus('pending');
    }
  };
  
  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollingInterval) {
        clearInterval(pollingInterval);
      }
    };
  }, [pollingInterval]);
  
  // UPI Apps with their icons (using internet URLs)
  const upiApps = [
    {
      name: 'Google Pay',
      icon: 'https://animationvisarts.com/wp-content/uploads/2023/11/Frame-43-1.png',
      package: 'com.google.android.apps.nbu.paisa.user'
    },
    {
      name: 'PhonePe',
      icon: 'https://tse2.mm.bing.net/th/id/OIP.tuYalZe2SOHuvjtZkDDJ5gHaFf?rs=1&pid=ImgDetMain',
      package: 'com.phonepe.app'
    },
    {
      name: 'Other UPI Apps',
      icon: 'https://tse3.mm.bing.net/th/id/OIP.OxvYhm9rOQ5YaPNrn4vhEgHaDt?w=512&h=256&rs=1&pid=ImgDetMain',
      package: 'all',
      isGeneric: true
    }
  ];
  
  const handleUpiAppClick = (app) => {
    if (!intentUrl) {
      setError('Payment link not available');
      return;
    }
    
    setStatus('loading');
    
    // Clear any existing cache for this order_id before starting new payment
    // This prevents showing old success data if user tries to pay again
    console.log('[Payment] Clearing any existing cache for order:', orderId);
    fetch(`${import.meta.env.VITE_API_URL}/api/checkout/maxpe/clear-cache?order_id=${orderId}`, {
      method: 'POST'
    }).catch(err => console.error('[Payment] Error clearing cache:', err));
    
    // Detect if device is iOS
    const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;
    
    console.log('Device detection:', { isIOS, userAgent: navigator.userAgent });
    
    let targetUrl = intentUrl;
    
    if (isIOS) {
      // iOS: Use UPI deep links (universal links)
      // Extract UPI parameters from intent URL
      let upiUrl = intentUrl;
      
      // If it's an intent URL, extract the UPI part
      if (intentUrl.includes('intent://')) {
        // Extract UPI string from intent URL
        const match = intentUrl.match(/intent:\/\/pay\?(.+?)#Intent/);
        if (match) {
          upiUrl = 'upi://pay?' + match[1];
        }
      } else if (!intentUrl.startsWith('upi://')) {
        // If it's not a UPI URL, try to construct one
        upiUrl = intentUrl;
      }
      
      console.log('[iOS] Base UPI URL:', upiUrl);
      
      // For iOS, use app-specific URL schemes
      if (app.package === 'com.google.android.apps.nbu.paisa.user') {
        // Google Pay iOS: Use tez:// or gpay:// scheme
        targetUrl = upiUrl.replace('upi://', 'tez://');
        console.log('[iOS] Google Pay URL:', targetUrl);
      } else if (app.package === 'com.phonepe.app') {
        // PhonePe iOS: Use phonepe:// scheme
        targetUrl = upiUrl.replace('upi://', 'phonepe://');
        console.log('[iOS] PhonePe URL:', targetUrl);
      } else {
        // Other UPI Apps: Use standard upi:// which iOS will handle
        targetUrl = upiUrl;
        console.log('[iOS] Generic UPI URL:', targetUrl);
      }
    } else {
      // Android: Use intent URLs
      if (app.package === 'com.google.android.apps.nbu.paisa.user') {
        // Google Pay specific intent
        if (intentUrl.startsWith('upi://')) {
          targetUrl = intentUrl.replace('upi://', 'intent://') + '#Intent;scheme=upi;package=com.google.android.apps.nbu.paisa.user;end';
        } else {
          targetUrl = intentUrl;
        }
      } else if (app.package === 'com.phonepe.app') {
        // PhonePe specific intent
        if (intentUrl.startsWith('upi://')) {
          targetUrl = intentUrl.replace('upi://', 'intent://') + '#Intent;scheme=upi;package=com.phonepe.app;end';
        } else {
          targetUrl = intentUrl;
        }
      }
      // For "Other UPI Apps", use the original intent URL which will show all apps
    }
    
    console.log('Opening UPI app:', app.name);
    console.log('Target URL:', targetUrl);
    
    // Open the UPI intent URL
    window.location.href = targetUrl;
    
    // Start polling immediately (user will take time to complete payment anyway)
    setTimeout(() => {
      startStatusPolling();
    }, 2000);
  };
  
  const startStatusPolling = () => {
    console.log('[Polling] Starting status polling for order:', orderId);
    
    // Poll for payment status every 1 second (faster detection)
    const interval = setInterval(async () => {
      try {
        console.log('[Polling] Checking payment status...');
        
        // Check payment status from backend using order_id (no auth required for checkout page)
        const response = await fetch(
          `${import.meta.env.VITE_API_URL}/api/checkout/maxpe/status?order_id=${orderId}`,
          {
            method: 'GET'
          }
        );
        
        console.log('[Polling] Response status:', response.status);
        
        if (response.ok) {
          const data = await response.json();
          console.log('[Polling] Response data:', data);
          
          if (data.success && data.transaction) {
            const txnStatus = data.transaction.status;
            const txnData = data.transaction;
            
            console.log('[Polling] Transaction status:', txnStatus);
            console.log('[Polling] Transaction data:', txnData);
            
            if (txnStatus === 'SUCCESS') {
              console.log('[Polling] ✅ Payment SUCCESS detected!');
              clearInterval(interval);
              setPollingInterval(null);
              setStatus('success');
              setTransactionData({
                orderId: txnData.order_id,
                amount: parseFloat(txnData.amount).toFixed(2),
                utr: txnData.bank_ref_no || txnData.utr || 'N/A',
                txnId: txnData.txn_id,
                completedAt: txnData.completed_at
              });
              console.log('[Polling] Success screen data set:', {
                orderId: txnData.order_id,
                amount: parseFloat(txnData.amount).toFixed(2),
                utr: txnData.bank_ref_no || txnData.utr
              });
            } else if (txnStatus === 'FAILED') {
              console.log('[Polling] ❌ Payment FAILED detected!');
              clearInterval(interval);
              setPollingInterval(null);
              setStatus('failed');
              setError('Payment failed. Please try again.');
            } else if (txnStatus === 'EXPIRED') {
              console.log('[Polling] ⏰ Payment EXPIRED detected!');
              clearInterval(interval);
              setPollingInterval(null);
              setStatus('expired');
              setTransactionData({
                orderId: txnData.order_id,
                amount: parseFloat(txnData.amount).toFixed(2),
                txnId: txnData.txn_id,
                createdAt: txnData.created_at,
                expiredAt: txnData.expired_at
              });
              setError('This payment link has expired. Payment links are valid for 6 minutes only.');
            } else {
              console.log('[Polling] ⏳ Status still pending:', txnStatus);
            }
            // If still INITIATED/PENDING, continue polling
          } else {
            console.log('[Polling] ⚠️ Invalid response structure:', data);
          }
        } else {
          console.log('[Polling] ❌ Response not OK:', response.status);
        }
      } catch (err) {
        console.error('[Polling] ❌ Error:', err);
      }
    }, 1000); // Changed from 3000ms to 1000ms (1 second)
    
    setPollingInterval(interval);
    
    // Stop polling after 5 minutes
    setTimeout(() => {
      console.log('[Polling] ⏰ Timeout reached (5 minutes)');
      clearInterval(interval);
      setPollingInterval(null);
      if (status === 'pending') {
        setLoading(false);
        setError('Payment status check timeout. Please check your transaction history.');
      }
    }, 300000); // 5 minutes
  };
  
  if (status === 'success') {
    return (
      <div className="min-h-screen bg-gradient-to-br from-green-50 to-green-100 flex items-center justify-center p-3 sm:p-4">
        <div className="bg-white rounded-2xl shadow-2xl p-4 sm:p-6 md:p-8 max-w-md w-full">
          <div className="mb-4 sm:mb-6 text-center">
            <div className="relative inline-block">
              <CheckCircle2 className="w-24 h-24 sm:w-32 sm:h-32 text-green-500 mx-auto animate-bounce" />
              <div className="absolute inset-0 flex items-center justify-center">
                <div className="w-20 h-20 sm:w-24 sm:h-24 bg-green-500 rounded-full opacity-20 animate-ping"></div>
              </div>
            </div>
          </div>
          
          <h1 className="text-2xl sm:text-3xl font-bold text-gray-800 mb-2 text-center">Payment was Successful!</h1>
          <p className="text-sm sm:text-base text-gray-600 mb-4 sm:mb-6 text-center">
            Your payment has been processed successfully.
          </p>
          
          {transactionData && (
            <div className="bg-gradient-to-br from-green-50 to-green-100 rounded-xl p-4 sm:p-6 mb-4 sm:mb-6 border-2 border-green-200">
              <div className="flex items-center justify-center mb-3 sm:mb-4">
                <Receipt className="w-5 h-5 sm:w-6 sm:h-6 text-green-600 mr-2" />
                <h3 className="text-base sm:text-lg font-semibold text-gray-800">Transaction Details</h3>
              </div>
              
              <div className="space-y-2 sm:space-y-3">
                <div className="flex justify-between items-center pb-2 border-b border-green-200">
                  <span className="text-xs sm:text-sm text-gray-600 font-medium">Order ID:</span>
                  <span className="text-xs sm:text-sm font-semibold text-gray-800 break-all ml-2">{transactionData.orderId}</span>
                </div>
                
                <div className="flex justify-between items-center pb-2 border-b border-green-200">
                  <span className="text-xs sm:text-sm text-gray-600 font-medium">Amount Paid:</span>
                  <span className="text-xl sm:text-2xl font-bold text-green-600">₹{transactionData.amount}</span>
                </div>
                
                <div className="flex justify-between items-center pb-2 border-b border-green-200">
                  <span className="text-xs sm:text-sm text-gray-600 font-medium">UTR Number:</span>
                  <span className="font-mono text-xs sm:text-sm font-semibold text-gray-800 bg-white px-2 py-1 rounded break-all ml-2">
                    {transactionData.utr}
                  </span>
                </div>
                
                <div className="flex justify-between items-center">
                  <span className="text-xs sm:text-sm text-gray-600 font-medium">Transaction ID:</span>
                  <span className="font-mono text-[10px] sm:text-xs text-gray-600 break-all ml-2">{transactionData.txnId}</span>
                </div>
              </div>
            </div>
          )}
          
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 sm:p-4 mb-4 sm:mb-6">
            <p className="text-xs sm:text-sm text-blue-800 text-center">
              ✓ Payment confirmed and wallet credited
            </p>
          </div>
          
          <button
            onClick={() => window.close()}
            className="w-full bg-green-600 text-white py-3 sm:py-3.5 rounded-lg hover:bg-green-700 transition-colors font-semibold text-sm sm:text-base"
          >
            Close Window
          </button>
          
          <p className="text-[10px] sm:text-xs text-gray-500 text-center mt-3 sm:mt-4">
            You can safely close this window now
          </p>
        </div>
      </div>
    );
  }
  
  if (status === 'expired') {
    // Check if it's a timeout expiry or already completed
    const isTimeoutExpiry = error && error.includes('6 minutes');
    
    return (
      <div className="min-h-screen bg-gradient-to-br from-orange-50 to-orange-100 flex items-center justify-center p-3 sm:p-4">
        <div className="bg-white rounded-2xl shadow-2xl p-4 sm:p-6 md:p-8 max-w-md w-full text-center">
          <div className="mb-4 sm:mb-6">
            <div className="w-20 h-20 sm:w-24 sm:h-24 mx-auto bg-orange-100 rounded-full flex items-center justify-center">
              <svg className="w-12 h-12 sm:w-14 sm:h-14 text-orange-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
          </div>
          <h1 className="text-2xl sm:text-3xl font-bold text-gray-800 mb-3 sm:mb-4">Payment Link Expired</h1>
          <p className="text-sm sm:text-base text-gray-600 mb-4 sm:mb-6">
            {isTimeoutExpiry 
              ? 'This payment link has expired. Payment links are valid for 6 minutes only.'
              : 'This payment has already been completed. The payment link can only be used once.'
            }
          </p>
          {transactionData && (
            <div className="bg-orange-50 rounded-lg p-3 sm:p-4 mb-4 sm:mb-6 text-left">
              {transactionData.expiredAt && (
                <div className="flex justify-between mb-2">
                  <span className="text-xs sm:text-sm text-gray-600">Expired At:</span>
                  <span className="text-xs sm:text-sm font-semibold text-gray-800">
                    {new Date(transactionData.expiredAt).toLocaleString()}
                  </span>
                </div>
              )}
              {transactionData.completedAt && (
                <div className="flex justify-between mb-2">
                  <span className="text-xs sm:text-sm text-gray-600">Completed:</span>
                  <span className="text-xs sm:text-sm font-semibold text-gray-800">
                    {new Date(transactionData.completedAt).toLocaleString()}
                  </span>
                </div>
              )}
              {transactionData.utr && (
                <div className="flex justify-between mb-2">
                  <span className="text-xs sm:text-sm text-gray-600">UTR:</span>
                  <span className="font-mono text-xs sm:text-sm font-semibold text-gray-800">{transactionData.utr}</span>
                </div>
              )}
              {transactionData.amount && (
                <div className="flex justify-between">
                  <span className="text-xs sm:text-sm text-gray-600">Amount:</span>
                  <span className="text-xs sm:text-sm font-semibold text-gray-800">₹{transactionData.amount}</span>
                </div>
              )}
            </div>
          )}
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 sm:p-4 mb-4 sm:mb-6">
            <p className="text-xs sm:text-sm text-blue-800">
              {isTimeoutExpiry
                ? 'The payment link expired after 6 minutes. Please request a new payment link to try again.'
                : 'If you need to make another payment, please request a new payment link.'
              }
            </p>
          </div>
          <button
            onClick={() => window.close()}
            className="w-full bg-orange-600 text-white py-3 rounded-lg hover:bg-orange-700 transition-colors text-sm sm:text-base font-medium"
          >
            Close Window
          </button>
        </div>
      </div>
    );
  }
  
  if (status === 'failed') {
    return (
      <div className="min-h-screen bg-gradient-to-br from-red-50 to-red-100 flex items-center justify-center p-3 sm:p-4">
        <div className="bg-white rounded-2xl shadow-2xl p-4 sm:p-6 md:p-8 max-w-md w-full text-center">
          <div className="mb-4 sm:mb-6">
            <XCircle className="w-20 h-20 sm:w-24 sm:h-24 text-red-500 mx-auto" />
          </div>
          <h1 className="text-2xl sm:text-3xl font-bold text-gray-800 mb-3 sm:mb-4">Payment was Failed</h1>
          <p className="text-sm sm:text-base text-gray-600 mb-4 sm:mb-6">
            {error || 'Something went wrong with your payment.'}
          </p>
          {orderDetails && (
            <div className="bg-gray-50 rounded-lg p-3 sm:p-4 mb-4 sm:mb-6 text-left">
              <div className="flex justify-between mb-2">
                <span className="text-xs sm:text-sm text-gray-600">Order ID:</span>
                <span className="text-xs sm:text-sm font-semibold text-gray-800 break-all ml-2">{orderDetails.orderId}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-xs sm:text-sm text-gray-600">Amount:</span>
                <span className="text-xs sm:text-sm font-semibold text-gray-800">₹{orderDetails.amount}</span>
              </div>
            </div>
          )}
          <button
            onClick={() => navigate('/transactions/payin-report')}
            className="w-full bg-blue-600 text-white py-3 rounded-lg hover:bg-blue-700 transition-colors text-sm sm:text-base font-medium"
          >
            Go to Transactions
          </button>
        </div>
      </div>
    );
  }
  
  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-3 sm:p-4">
      <div className="bg-white rounded-2xl shadow-2xl p-4 sm:p-6 md:p-8 max-w-2xl w-full">
        {/* Header */}
        <div className="text-center mb-6 sm:mb-8">
          <div className="mb-3 sm:mb-4">
            <Smartphone className="w-12 h-12 sm:w-16 sm:h-16 text-blue-600 mx-auto" />
          </div>
          <h1 className="text-2xl sm:text-3xl font-bold text-gray-800 mb-2">Complete Your Payment</h1>
          <p className="text-sm sm:text-base text-gray-600">Choose your preferred UPI app to pay</p>
        </div>
        
        {/* Order Details */}
        {orderDetails && (
          <div className="bg-gradient-to-r from-blue-50 to-indigo-50 rounded-xl p-4 sm:p-6 mb-6 sm:mb-8 border border-blue-200">
            <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center mb-3 gap-2">
              <span className="text-sm sm:text-base text-gray-600 font-medium">Order ID:</span>
              <span className="text-sm sm:text-base font-bold text-gray-800 break-all">{orderDetails.orderId}</span>
            </div>
            <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2">
              <span className="text-sm sm:text-base text-gray-600 font-medium">Amount to Pay:</span>
              <span className="text-2xl sm:text-3xl font-bold text-blue-600">₹{orderDetails.amount}</span>
            </div>
          </div>
        )}
        
        {/* Timer Display */}
        {(status === 'pending' || status === 'loading') && timeRemaining > 0 && (
          <div className={`mb-6 sm:mb-8 rounded-xl p-4 border-2 ${
            timeRemaining <= 60 
              ? 'bg-red-50 border-red-300' 
              : timeRemaining <= 180 
              ? 'bg-orange-50 border-orange-300' 
              : 'bg-green-50 border-green-300'
          }`}>
            <div className="flex items-center justify-center gap-3">
              <svg className={`w-6 h-6 ${
                timeRemaining <= 60 
                  ? 'text-red-500' 
                  : timeRemaining <= 180 
                  ? 'text-orange-500' 
                  : 'text-green-500'
              }`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <div className="text-center">
                <p className="text-xs sm:text-sm text-gray-600 font-medium mb-1">Time Remaining</p>
                <p className={`text-2xl sm:text-3xl font-bold ${
                  timeRemaining <= 60 
                    ? 'text-red-600' 
                    : timeRemaining <= 180 
                    ? 'text-orange-600' 
                    : 'text-green-600'
                }`}>
                  {Math.floor(timeRemaining / 60)}:{String(timeRemaining % 60).padStart(2, '0')}
                </p>
                <p className="text-[10px] sm:text-xs text-gray-500 mt-1">
                  {timeRemaining <= 60 
                    ? '⚠️ Link expiring soon!' 
                    : 'Complete payment before timer expires'
                  }
                </p>
              </div>
            </div>
          </div>
        )}
        
        {/* Validating State */}
        {status === 'validating' && (
          <div className="text-center mb-6 sm:mb-8">
            <Loader2 className="w-10 h-10 sm:w-12 sm:h-12 text-blue-600 mx-auto animate-spin mb-4" />
            <p className="text-sm sm:text-base text-gray-600 font-medium">Validating payment link...</p>
          </div>
        )}
        
        {/* Loading State */}
        {status === 'loading' && (
          <div className="text-center mb-6 sm:mb-8">
            <Loader2 className="w-10 h-10 sm:w-12 sm:h-12 text-blue-600 mx-auto animate-spin mb-4" />
            <p className="text-sm sm:text-base text-gray-600 font-medium">Processing your payment...</p>
            <p className="text-xs sm:text-sm text-gray-500 mt-2">Please complete the payment in your UPI app</p>
            
            {/* Manual Check Status Button */}
            <button
              onClick={() => {
                console.log('[Manual Check] User clicked check status button');
                // Trigger an immediate status check
                fetch(`${import.meta.env.VITE_API_URL}/api/checkout/maxpe/status?order_id=${orderId}`)
                  .then(res => res.json())
                  .then(data => {
                    console.log('[Manual Check] Status response:', data);
                    if (data.success && data.transaction && data.transaction.status === 'SUCCESS') {
                      setStatus('success');
                      setTransactionData({
                        orderId: data.transaction.order_id,
                        amount: parseFloat(data.transaction.amount).toFixed(2),
                        utr: data.transaction.bank_ref_no || data.transaction.utr || 'N/A',
                        txnId: data.transaction.txn_id,
                        completedAt: data.transaction.completed_at
                      });
                      if (pollingInterval) {
                        clearInterval(pollingInterval);
                        setPollingInterval(null);
                      }
                    }
                  })
                  .catch(err => console.error('[Manual Check] Error:', err));
              }}
              className="mt-4 px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm font-medium"
            >
              Check Payment Status
            </button>
          </div>
        )}
        
        {/* UPI Apps Grid */}
        {status === 'pending' && (
          <>
            <h2 className="text-lg sm:text-xl font-semibold text-gray-800 mb-4 sm:mb-6 text-center">Select Payment Method</h2>
            <div className="grid grid-cols-1 gap-3 sm:gap-4 mb-4 sm:mb-6">
              {upiApps.map((app) => (
                <button
                  key={app.name}
                  onClick={() => handleUpiAppClick(app)}
                  className={`flex items-center justify-between p-4 sm:p-6 bg-white border-2 rounded-xl hover:border-blue-500 hover:shadow-lg transition-all duration-200 group ${
                    app.isGeneric ? 'border-gray-300' : 'border-gray-200'
                  }`}
                  disabled={!intentUrl}
                >
                  <div className="flex items-center space-x-3 sm:space-x-4">
                    <div className="w-12 h-12 sm:w-16 sm:h-16 flex items-center justify-center flex-shrink-0">
                      <img
                        src={app.icon}
                        alt={app.name}
                        className="w-full h-full object-contain group-hover:scale-110 transition-transform"
                        onError={(e) => {
                          e.target.src = 'https://via.placeholder.com/64?text=UPI';
                        }}
                      />
                    </div>
                    <div className="text-left">
                      <span className="text-base sm:text-lg font-semibold text-gray-800 block">
                        {app.name}
                      </span>
                      {app.isGeneric && (
                        <span className="text-xs sm:text-sm text-gray-500">
                          Paytm, BHIM, Amazon Pay & more
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="text-blue-600 group-hover:translate-x-1 transition-transform flex-shrink-0">
                    <svg className="w-5 h-5 sm:w-6 sm:h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                    </svg>
                  </div>
                </button>
              ))}
            </div>
          </>
        )}
        
        {/* Error Message */}
        {error && status !== 'loading' && status !== 'validating' && (
          <div className="mt-4 sm:mt-6 bg-red-50 border border-red-200 rounded-lg p-3 sm:p-4">
            <p className="text-red-600 text-xs sm:text-sm">{error}</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default MaxpeCheckout;
