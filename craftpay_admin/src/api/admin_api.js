// Get API base URL from environment variable
const API_BASE_URL = `${import.meta.env.VITE_API_BASE_URL || 'http://localhost:5000/api'}/admin`;
const API_ROOT = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5000/api';

class AdminAPI {
  constructor() {
    // Don't store token in constructor, get it fresh each time
  }

  // Set authorization header
  getHeaders(includeAuth = false) {
    const headers = {
      'Content-Type': 'application/json',
    };
    
    if (includeAuth) {
      const token = localStorage.getItem('adminToken') || localStorage.getItem('qrAdminToken');
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }
    }
    
    return headers;
  }

  // Handle API response
  async handleResponse(response) {
    const data = await response.json();
    
    if (!response.ok) {
      // Handle 401 Unauthorized - token expired or invalid
      if (response.status === 401) {
        // Clear invalid token
        localStorage.removeItem('adminToken');
        localStorage.removeItem('adminId');
        localStorage.removeItem('isAuthenticated');
        localStorage.removeItem('adminHasPinSet');
        localStorage.removeItem('qrAdminToken');
        localStorage.removeItem('qrAdminId');
        
        // Redirect to login if not already there
        if (!window.location.pathname.includes('login')) {
          if (window.location.pathname.includes('/qrlogin')) {
            window.location.href = '/qrlogin';
          } else {
            window.location.href = '/login';
          }
        }
        
        throw new Error('Session expired. Please login again.');
      }
      
      throw new Error(data.message || 'API request failed');
    }
    
    return data;
  }

  // Get CAPTCHA
  async getCaptcha() {
    try {
      const response = await fetch(`${API_BASE_URL}/captcha`, {
        method: 'GET',
        headers: this.getHeaders(),
      });
      
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Get captcha error:', error);
      throw error;
    }
  }

  // Admin Login
  async login(adminId, password) {
    try {
      const response = await fetch(`${API_BASE_URL}/login`, {
        method: 'POST',
        headers: this.getHeaders(),
        body: JSON.stringify({
          adminId,
          password
        }),
      });
      
      const data = await this.handleResponse(response);
      
      if (data.success && data.token) {
        // Store token in localStorage
        localStorage.setItem('adminToken', data.token);
        localStorage.setItem('adminId', data.adminId);
        localStorage.setItem('isAuthenticated', 'true');
      }
      
      return data;
    } catch (error) {
      console.error('Login error:', error);
      throw error;
    }
  }

  // Verify Token
  async verifyToken() {
    try {
      const response = await fetch(`${API_BASE_URL}/verify`, {
        method: 'GET',
        headers: this.getHeaders(true),
      });
      
      const data = await this.handleResponse(response);
      
      // Update token if new one is provided (session refresh)
      if (data.success && data.token) {
        localStorage.setItem('adminToken', data.token);
      }
      
      return data;
    } catch (error) {
      console.error('Verify token error:', error);
      // Only clear token if it's actually invalid (401/403)
      if (error.message && (error.message.includes('401') || error.message.includes('403') || error.message.includes('Invalid token'))) {
        // Clear invalid token
        localStorage.removeItem('adminToken');
        localStorage.removeItem('adminId');
        localStorage.removeItem('isAuthenticated');
        localStorage.removeItem('adminHasPinSet');
      }
      throw error;
    }
  }

  // Admin Logout
  async logout() {
    try {
      const token = localStorage.getItem('adminToken');
      if (token) {
        await fetch(`${API_BASE_URL}/logout`, {
          method: 'POST',
          headers: this.getHeaders(true),
        });
      }
    } catch (error) {
      console.error('Logout error:', error);
    } finally {
      // Clear local storage
      localStorage.removeItem('adminToken');
      localStorage.removeItem('adminId');
      localStorage.removeItem('isAuthenticated');
      localStorage.removeItem('adminHasPinSet');
    }
  }

  // Get Activity Logs
  async getActivityLogs(params = {}) {
    try {
      const queryString = new URLSearchParams(params).toString();
      const response = await fetch(`${API_BASE_URL}/activity-logs${queryString ? '?' + queryString : ''}`, {
        method: 'GET',
        headers: this.getHeaders(true),
      });
      
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Get activity logs error:', error);
      throw error;
    }
  }

  // Download Activity Logs
  async downloadActivityLogs(params = {}) {
    try {
      const queryString = new URLSearchParams(params).toString();
      const response = await fetch(`${API_BASE_URL}/activity-logs/download${queryString ? '?' + queryString : ''}`, {
        method: 'GET',
        headers: this.getHeaders(true),
      });
      
      if (!response.ok) {
        throw new Error('Failed to download activity logs');
      }
      
      // Get the blob
      const blob = await response.blob();
      
      // Create download link
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `activity_logs_${new Date().toISOString().split('T')[0]}.csv`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      
      return { success: true };
    } catch (error) {
      console.error('Download activity logs error:', error);
      throw error;
    }
  }

  // Change Password
  async changePassword(currentPassword, newPassword, confirmPassword) {
    try {
      const response = await fetch(`${API_BASE_URL}/change-password`, {
        method: 'POST',
        headers: this.getHeaders(true),
        body: JSON.stringify({
          currentPassword,
          newPassword,
          confirmPassword,
        }),
      });
      
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Change password error:', error);
      throw error;
    }
  }

  // Change PIN
  async changePin(currentPin, newPin, confirmPin) {
    try {
      const response = await fetch(`${API_BASE_URL}/change-pin`, {
        method: 'POST',
        headers: this.getHeaders(true),
        body: JSON.stringify({
          currentPin,
          newPin,
          confirmPin,
        }),
      });
      
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Change PIN error:', error);
      throw error;
    }
  }

  // Check PIN Status
  async checkPinStatus() {
    try {
      const response = await fetch(`${API_BASE_URL}/pin-status`, {
        method: 'GET',
        headers: this.getHeaders(true),
      });
      
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Check PIN status error:', error);
      throw error;
    }
  }

  // Delete PIN
  async deletePin() {
    try {
      const response = await fetch(`${API_BASE_URL}/delete-pin`, {
        method: 'DELETE',
        headers: this.getHeaders(true),
      });
      
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Delete PIN error:', error);
      throw error;
    }
  }

  // Health Check
  async healthCheck() {
    try {
      const response = await fetch(`${API_BASE_URL}/health`, {
        method: 'GET',
        headers: this.getHeaders(),
      });
      
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Health check error:', error);
      throw error;
    }
  }

  // Check if user is authenticated
  isAuthenticated() {
    const token = localStorage.getItem('adminToken');
    const qrToken = localStorage.getItem('qrAdminToken');
    return (!!token && localStorage.getItem('isAuthenticated') === 'true') || !!qrToken;
  }

  // Get current admin ID
  getAdminId() {
    return localStorage.getItem('adminId');
  }

  // Commercials API Methods

  // Get all schemes
  async getSchemes() {
    try {
      const response = await fetch(`${API_BASE_URL}/commercials/schemes`, {
        method: 'GET',
        headers: this.getHeaders(true),
      });
      
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Get schemes error:', error);
      throw error;
    }
  }

  // Create new scheme
  async createScheme(schemeName) {
    try {
      const response = await fetch(`${API_BASE_URL}/commercials/schemes`, {
        method: 'POST',
        headers: this.getHeaders(true),
        body: JSON.stringify({ schemeName }),
      });
      
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Create scheme error:', error);
      throw error;
    }
  }

  // Get scheme charges
  async getSchemeCharges(schemeId) {
    try {
      const response = await fetch(`${API_BASE_URL}/commercials/schemes/${schemeId}/charges`, {
        method: 'GET',
        headers: this.getHeaders(true),
      });
      
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Get scheme charges error:', error);
      throw error;
    }
  }

  // Create or update charges
  async updateCharges(schemeId, charges) {
    try {
      const response = await fetch(`${API_BASE_URL}/commercials/charges`, {
        method: 'POST',
        headers: this.getHeaders(true),
        body: JSON.stringify({ schemeId, charges }),
      });
      
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Update charges error:', error);
      throw error;
    }
  }

  // Delete scheme
  async deleteScheme(schemeId) {
    try {
      const response = await fetch(`${API_BASE_URL}/commercials/schemes/${schemeId}`, {
        method: 'DELETE',
        headers: this.getHeaders(true),
      });
      
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Delete scheme error:', error);
      throw error;
    }
  }

  // Onboard Merchant
  async onboardMerchant(formData) {
    try {
      const token = localStorage.getItem('adminToken');
      const response = await fetch(`${API_BASE_URL}/merchants/onboard`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
        body: formData, // FormData for file upload
      });
      
      const data = await response.json();
      
      if (!response.ok) {
        throw new Error(data.message || 'Merchant onboarding failed');
      }
      
      return data;
    } catch (error) {
      console.error('Onboard merchant error:', error);
      throw error;
    }
  }

  // User Management API Methods

  // Get all users
  async getUsers() {
    try {
      const response = await fetch(`${API_BASE_URL}/users`, {
        method: 'GET',
        headers: this.getHeaders(true),
      });
      
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Get users error:', error);
      throw error;
    }
  }

  // Get user details
  async getUserDetails(merchantId) {
    try {
      const response = await fetch(`${API_BASE_URL}/users/${merchantId}`, {
        method: 'GET',
        headers: this.getHeaders(true),
      });
      
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Get user details error:', error);
      throw error;
    }
  }

  // Update user
  async updateUser(merchantId, userData) {
    try {
      const response = await fetch(`${API_BASE_URL}/users/${merchantId}`, {
        method: 'PUT',
        headers: this.getHeaders(true),
        body: JSON.stringify(userData),
      });
      
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Update user error:', error);
      throw error;
    }
  }

  // Toggle user status (activate/deactivate)
  async toggleUserStatus(merchantId) {
    try {
      const response = await fetch(`${API_BASE_URL}/users/${merchantId}/toggle-status`, {
        method: 'PUT',
        headers: this.getHeaders(true),
      });
      
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Toggle user status error:', error);
      throw error;
    }
  }

  // Reset user password
  async resetUserPassword(merchantId, newPassword) {
    try {
      const response = await fetch(`${API_BASE_URL}/users/${merchantId}/reset-password`, {
        method: 'POST',
        headers: this.getHeaders(true),
        body: JSON.stringify({ newPassword }),
      });
      
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Reset user password error:', error);
      throw error;
    }
  }

  // Delete user
  async deleteUser(merchantId) {
    try {
      const response = await fetch(`${API_BASE_URL}/users/${merchantId}`, {
        method: 'DELETE',
        headers: this.getHeaders(true),
      });
      
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Delete user error:', error);
      throw error;
    }
  }

  // Download document
  async downloadDocument(merchantId, docType) {
    try {
      const response = await fetch(`${API_BASE_URL}/users/${merchantId}/documents/${docType}`, {
        method: 'GET',
        headers: this.getHeaders(true),
      });
      
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Download document error:', error);
      throw error;
    }
  }

  // Get All Banks (Admin)
  async getAllBanks() {
    try {
      const response = await fetch(`${API_BASE_URL}/banks`, {
        method: 'GET',
        headers: this.getHeaders(true),
      });
      
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Get all banks error:', error);
      throw error;
    }
  }

  // Get Admin Banks
  async getAdminBanks() {
    try {
      const response = await fetch(`${API_BASE_URL}/banks`, {
        method: 'GET',
        headers: this.getHeaders(true),
      });
      
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Get admin banks error:', error);
      throw error;
    }
  }

  // Get All Users
  async getAllUsers() {
    try {
      const response = await fetch(`${API_BASE_URL}/users`, {
        method: 'GET',
        headers: this.getHeaders(true),
      });
      
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Get all users error:', error);
      throw error;
    }
  }

  // Add Bank (Admin)
  async addBank(bankData) {
    try {
      const response = await fetch(`${API_BASE_URL}/banks`, {
        method: 'POST',
        headers: this.getHeaders(true),
        body: JSON.stringify(bankData),
      });
      
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Add bank error:', error);
      throw error;
    }
  }

  // Delete Bank (Admin)
  async deleteBank(bankId, tpin) {
    try {
      const response = await fetch(`${API_BASE_URL}/banks/${bankId}`, {
        method: 'DELETE',
        headers: this.getHeaders(true),
        body: JSON.stringify({ tpin }),
      });
      
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Delete bank error:', error);
      throw error;
    }
  }

  // Toggle Bank Status (Admin)
  async toggleBankStatus(bankId) {
    try {
      const response = await fetch(`${API_BASE_URL}/banks/${bankId}/toggle-status`, {
        method: 'PUT',
        headers: this.getHeaders(true),
      });
      
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Toggle bank status error:', error);
      throw error;
    }
  }

  // Service Routing APIs
  async getServiceRouting() {
    try {
      const response = await fetch(`${import.meta.env.VITE_API_BASE_URL || 'http://localhost:5000/api'}/routing/services`, {
        method: 'GET',
        headers: this.getHeaders(true),
      });
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Get service routing error:', error);
      throw error;
    }
  }

  async createServiceRouting(data) {
    try {
      const response = await fetch(`${import.meta.env.VITE_API_BASE_URL || 'http://localhost:5000/api'}/routing/services`, {
        method: 'POST',
        headers: this.getHeaders(true),
        body: JSON.stringify(data),
      });
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Create service routing error:', error);
      throw error;
    }
  }

  async updateServiceRouting(routeId, data) {
    try {
      const response = await fetch(`${import.meta.env.VITE_API_BASE_URL || 'http://localhost:5000/api'}/routing/services/${routeId}`, {
        method: 'PUT',
        headers: this.getHeaders(true),
        body: JSON.stringify(data),
      });
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Update service routing error:', error);
      throw error;
    }
  }

  async deleteServiceRouting(routeId) {
    try {
      const response = await fetch(`${import.meta.env.VITE_API_BASE_URL || 'http://localhost:5000/api'}/routing/services/${routeId}`, {
        method: 'DELETE',
        headers: this.getHeaders(true),
      });
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Delete service routing error:', error);
      throw error;
    }
  }

  async getMerchantsForRouting() {
    try {
      const response = await fetch(`${import.meta.env.VITE_API_BASE_URL || 'http://localhost:5000/api'}/routing/merchants`, {
        method: 'GET',
        headers: this.getHeaders(true),
      });
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Get merchants for routing error:', error);
      throw error;
    }
  }

  async getPGPartners() {
    try {
      const response = await fetch(`${import.meta.env.VITE_API_BASE_URL || 'http://localhost:5000/api'}/routing/pg-partners`, {
        method: 'GET',
        headers: this.getHeaders(false),
      });
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Get PG partners error:', error);
      throw error;
    }
  }

  // Risexpay Auto Success Toggle
  async getRisexpayAutoSuccess() {
    try {
      const response = await fetch(`${import.meta.env.VITE_API_BASE_URL || 'http://localhost:5000/api'}/payout/admin/risexpay-auto-success`, {
        method: 'GET',
        headers: this.getHeaders(true),
      });
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Get Risexpay auto-success error:', error);
      throw error;
    }
  }

  async toggleRisexpayAutoSuccess(enabled) {
    try {
      const response = await fetch(`${import.meta.env.VITE_API_BASE_URL || 'http://localhost:5000/api'}/payout/admin/risexpay-auto-success`, {
        method: 'POST',
        headers: this.getHeaders(true),
        body: JSON.stringify({ enabled }),
      });
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Toggle Risexpay auto-success error:', error);
      throw error;
    }
  }

  // Payin Transaction APIs
  async getPayinTransactions(params = {}) {
    try {
      const queryString = new URLSearchParams(params).toString();
      const response = await fetch(`${API_ROOT}/payin/admin/transactions?${queryString}`, {
        method: 'GET',
        headers: this.getHeaders(true),
      });
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Get payin transactions error:', error);
      throw error;
    }
  }

  async getAllPayinTransactions(params = {}) {
    try {
      const queryString = new URLSearchParams(params).toString();
      const response = await fetch(`${API_ROOT}/payin/admin/transactions/all?${queryString}`, {
        method: 'GET',
        headers: this.getHeaders(true),
      });
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Get all payin transactions error:', error);
      throw error;
    }
  }

  async getTodayPayinTransactions() {
    try {
      const response = await fetch(`${API_ROOT}/payin/admin/transactions/today`, {
        method: 'GET',
        headers: this.getHeaders(true),
      });
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Get today payin transactions error:', error);
      throw error;
    }
  }

  async getPendingPayin() {
    try {
      const response = await fetch(`${API_ROOT}/payin/admin/pending`, {
        method: 'GET',
        headers: this.getHeaders(true),
      });
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Get pending payin error:', error);
      throw error;
    }
  }

  async checkPayinStatus(txnId) {
    try {
      const response = await fetch(`${API_ROOT}/payin/admin/check-status/${txnId}`, {
        method: 'GET',
        headers: this.getHeaders(true),
      });
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Check payin status error:', error);
      throw error;
    }
  }

  async manualCompletePayin(txnId, action, utr = '', remarks = '') {
    try {
      const response = await fetch(`${API_ROOT}/payin/admin/manual-complete/${txnId}`, {
        method: 'POST',
        headers: this.getHeaders(true),
        body: JSON.stringify({ action, utr, remarks }),
      });
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Manual complete payin error:', error);
      throw error;
    }
  }

  async getWalletOverview(merchantId) {
    try {
      const response = await fetch(`${API_BASE_URL}/wallet/overview/${merchantId}`, {
        method: 'GET',
        headers: this.getHeaders(true),
      });
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Get wallet overview error:', error);
      throw error;
    }
  }

  async getPayinStats() {
    try {
      const response = await fetch(`${API_ROOT}/payin/admin/stats`, {
        method: 'GET',
        headers: this.getHeaders(true),
      });
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Get payin stats error:', error);
      throw error;
    }
  }

  // Payout APIs
  async personalPayout(payoutData) {
    try {
      const response = await fetch(`${API_ROOT}/payout/admin/personal-payout`, {
        method: 'POST',
        headers: this.getHeaders(true),
        body: JSON.stringify(payoutData),
      });
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Personal payout error:', error);
      throw error;
    }
  }

  async getFundRequests(status = 'PENDING') {
    try {
      const response = await fetch(`${API_ROOT}/payout/admin/fund-requests?status=${status}`, {
        method: 'GET',
        headers: this.getHeaders(true),
      });
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Get fund requests error:', error);
      throw error;
    }
  }

  async processFundRequest(requestId, data) {
    try {
      const response = await fetch(`${API_ROOT}/payout/admin/fund-request/${requestId}`, {
        method: 'PUT',
        headers: this.getHeaders(true),
        body: JSON.stringify(data),
      });
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Process fund request error:', error);
      throw error;
    }
  }

  async topupFund(topupData) {
    try {
      const response = await fetch(`${API_ROOT}/payout/admin/topup-fund`, {
        method: 'POST',
        headers: this.getHeaders(true),
        body: JSON.stringify(topupData),
      });
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Topup fund error:', error);
      throw error;
    }
  }

  async fetchFund(fetchData) {
    try {
      const response = await fetch(`${API_ROOT}/payout/admin/fetch-fund`, {
        method: 'POST',
        headers: this.getHeaders(true),
        body: JSON.stringify(fetchData),
      });
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Fetch fund error:', error);
      throw error;
    }
  }

  // IP Security Management
  async getIPSecurityMerchants() {
    try {
      const response = await fetch(`${API_ROOT}/admin/ip-security/merchants`, {
        method: 'GET',
        headers: this.getHeaders(true),
      });
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Get IP security merchants error:', error);
      throw error;
    }
  }

  async getMerchantIPSecurity(merchantId) {
    try {
      const response = await fetch(`${API_ROOT}/admin/ip-security/${merchantId}`, {
        method: 'GET',
        headers: this.getHeaders(true),
      });
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Get merchant IP security error:', error);
      throw error;
    }
  }

  async addMerchantIP(merchantId, ipData) {
    try {
      const response = await fetch(`${API_ROOT}/admin/ip-security/${merchantId}/add`, {
        method: 'POST',
        headers: this.getHeaders(true),
        body: JSON.stringify(ipData),
      });
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Add merchant IP error:', error);
      throw error;
    }
  }

  async updateMerchantIP(merchantId, ipId, ipData) {
    try {
      const response = await fetch(`${API_ROOT}/admin/ip-security/${merchantId}/update/${ipId}`, {
        method: 'PUT',
        headers: this.getHeaders(true),
        body: JSON.stringify(ipData),
      });
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Update merchant IP error:', error);
      throw error;
    }
  }

  async deleteMerchantIP(merchantId, ipId) {
    try {
      const response = await fetch(`${API_ROOT}/admin/ip-security/${merchantId}/delete/${ipId}`, {
        method: 'DELETE',
        headers: this.getHeaders(true),
      });
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Delete merchant IP error:', error);
      throw error;
    }
  }

  async getIPSecurityLogs(filters = {}) {
    try {
      const queryParams = new URLSearchParams(filters).toString();
      const response = await fetch(`${API_ROOT}/admin/ip-security/logs?${queryParams}`, {
        method: 'GET',
        headers: this.getHeaders(true),
      });
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Get IP security logs error:', error);
      throw error;
    }
  }

  async fetchFund(fetchData) {
    try {
      const response = await fetch(`${API_ROOT}/payout/admin/fetch-fund`, {
        method: 'POST',
        headers: this.getHeaders(true),
        body: JSON.stringify(fetchData),
      });
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Fetch fund error:', error);
      throw error;
    }
  }

  async getPayoutReport(filters = {}) {
    try {
      const queryParams = new URLSearchParams(filters).toString();
      const url = `${API_ROOT}/payout/admin/payout-report${queryParams ? '?' + queryParams : ''}`;
      
      const response = await fetch(url, {
        method: 'GET',
        headers: this.getHeaders(true),
      });
      
      // Handle 401 specifically for payout report
      if (response.status === 401) {
        console.warn('⚠️ Token expired or invalid. Please login again.');
        return { success: false, message: 'Session expired. Please login again.', data: [] };
      }
      
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Get payout report error:', error);
      // Return empty data instead of throwing
      return { success: false, message: error.message, data: [] };
    }
  }

  async getAllPayoutReport(filters = {}) {
    try {
      const queryParams = new URLSearchParams(filters).toString();
      const url = `${API_ROOT}/payout/admin/payout-report/all${queryParams ? '?' + queryParams : ''}`;
      
      const response = await fetch(url, {
        method: 'GET',
        headers: this.getHeaders(true),
      });
      
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Get all payout report error:', error);
      throw error;
    }
  }

  async getTodayPayoutReport() {
    try {
      const response = await fetch(`${API_ROOT}/payout/admin/payout-report/today`, {
        method: 'GET',
        headers: this.getHeaders(true),
      });
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Get today payout report error:', error);
      throw error;
    }
  }

  async syncPayoutStatus(txnId) {
    try {
      const response = await fetch(`${API_ROOT}/payout/sync-status/${txnId}`, {
        method: 'POST',
        headers: this.getHeaders(true),
      });
      
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Sync payout status error:', error);
      throw error;
    }
  }

  async getPayoutStats() {
    try {
      const response = await fetch(`${API_ROOT}/payout/admin/stats`, {
        method: 'GET',
        headers: this.getHeaders(true),
      });
      
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Get payout stats error:', error);
      return { success: false, message: error.message, stats: { success: {count: 0, amount: 0}, pending: {count: 0, amount: 0}, failed: {count: 0, amount: 0}, queued: {count: 0, amount: 0} } };
    }
  }

  async getPendingPayouts() {
    try {
      const response = await fetch(`${API_ROOT}/payout/admin/pending-payouts`, {
        method: 'GET',
        headers: this.getHeaders(true),
      });
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Get pending payouts error:', error);
      throw error;
    }
  }

  async getAdminWalletOverview() {
    try {
      const response = await fetch(`${API_ROOT}/wallet/admin/overview`, {
        method: 'GET',
        headers: this.getHeaders(true),
      });
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Get admin wallet overview error:', error);
      throw error;
    }
  }

  async getAdminWalletStatement(filters = {}) {
    try {
      const queryParams = new URLSearchParams(filters).toString();
      const response = await fetch(`${API_ROOT}/wallet/admin/statement${queryParams ? '?' + queryParams : ''}`, {
        method: 'GET',
        headers: this.getHeaders(true),
      });
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Get admin wallet statement error:', error);
      throw error;
    }
  }

  async getMerchantWalletOverview(merchantId) {
    try {
      const response = await fetch(`${API_ROOT}/wallet/merchant/overview?merchant_id=${merchantId}`, {
        method: 'GET',
        headers: this.getHeaders(true),
      });
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Get merchant wallet overview error:', error);
      throw error;
    }
  }

  async getServiceRoutingFiltered(serviceType, routingType) {
    try {
      const response = await fetch(`${API_ROOT}/routing/services?service_type=${serviceType}&routing_type=${routingType}`, {
        method: 'GET',
        headers: this.getHeaders(true),
      });
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Get service routing filtered error:', error);
      throw error;
    }
  }

  // Get Service Routing by Type
  async getServiceRouting(serviceType, routingType) {
    try {
      const response = await fetch(`${API_ROOT}/routing/services?service_type=${serviceType}&routing_type=${routingType}`, {
        method: 'GET',
        headers: this.getHeaders(true),
      });
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Get service routing error:', error);
      throw error;
    }
  }

  // Get Merchant Wallet Statement (Admin viewing merchant wallet)
  async getMerchantWalletStatement(merchantId, filters = {}) {
    try {
      const queryParams = new URLSearchParams({
        merchant_id: merchantId,
        ...filters
      }).toString();
      const response = await fetch(`${API_ROOT}/wallet/merchant/statement?${queryParams}`, {
        method: 'GET',
        headers: this.getHeaders(true),
      });
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Get merchant wallet statement error:', error);
      throw error;
    }
  }

  // Settlement APIs
  async settleWallet(data) {
    try {
      const response = await fetch(`${API_ROOT}/wallet/admin/settle`, {
        method: 'POST',
        headers: this.getHeaders(true),
        body: JSON.stringify(data)
      });
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Settle wallet error:', error);
      throw error;
    }
  }

  async getMerchantWalletDetails(merchantId) {
    try {
      const response = await fetch(`${API_ROOT}/wallet/merchant/wallet-details?merchant_id=${merchantId}`, {
        method: 'GET',
        headers: this.getHeaders(true)
      });
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Get merchant wallet details error:', error);
      throw error;
    }
  }

  async getWalletSummary() {
    try {
      const response = await fetch(`${API_ROOT}/wallet/admin/wallet-summary`, {
        method: 'GET',
        headers: this.getHeaders(true)
      });
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Get wallet summary error:', error);
      throw error;
    }
  }

  // FRESH IMPLEMENTATION: Create invoice for successful payin transaction
  // Only sends txn_id to backend, backend handles everything else
  async createInvoice(txnId) {
    try {
      console.log('=== Admin API: Creating Invoice ===');
      console.log('Transaction ID:', txnId);
      console.log('Endpoint:', `${API_ROOT}/payin/admin/create-invoice/${txnId}`);
      
      const response = await fetch(`${API_ROOT}/payin/admin/create-invoice/${txnId}`, {
        method: 'POST',
        headers: this.getHeaders(true),
      });
      
      const data = await this.handleResponse(response);
      console.log('Response received:', data);
      
      return data;
    } catch (error) {
      console.error('Create invoice API error:', error);
      throw error;
    }
  }

  // Manual Reconciliation APIs
  async searchManualReconTransactions(params) {
    try {
      const response = await fetch(`${API_BASE_URL}/manual-reconciliation/search`, {
        method: 'POST',
        headers: this.getHeaders(true),
        body: JSON.stringify(params)
      });
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Search manual recon transactions error:', error);
      throw error;
    }
  }

  async markTransactionFailed(data) {
    try {
      const response = await fetch(`${API_BASE_URL}/manual-reconciliation/mark-failed`, {
        method: 'POST',
        headers: this.getHeaders(true),
        body: JSON.stringify(data)
      });
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Mark transaction failed error:', error);
      throw error;
    }
  }

  async markTransactionSuccess(data) {
    try {
      const response = await fetch(`${API_BASE_URL}/manual-reconciliation/mark-success`, {
        method: 'POST',
        headers: this.getHeaders(true),
        body: JSON.stringify(data)
      });
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Mark transaction success error:', error);
      throw error;
    }
  }

  async getBulkInitiatedTransactions(params) {
    try {
      const response = await fetch(`${API_BASE_URL}/manual-reconciliation/bulk-initiated`, {
        method: 'POST',
        headers: this.getHeaders(true),
        body: JSON.stringify(params)
      });
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Get bulk initiated transactions error:', error);
      throw error;
    }
  }

  async getManualReconMerchants() {
    try {
      const response = await fetch(`${API_BASE_URL}/manual-reconciliation/merchants`, {
        method: 'GET',
        headers: this.getHeaders(true)
      });
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Get manual recon merchants error:', error);
      throw error;
    }
  }

  // Auto-Settlement APIs
  async getAutoSettlementConfig(merchantId) {
    try {
      const response = await fetch(`${API_ROOT}/auto-settlement/config/${merchantId}`, {
        method: 'GET',
        headers: this.getHeaders(true)
      });
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Get auto-settlement config error:', error);
      throw error;
    }
  }

  async updateAutoSettlementConfig(merchantId, config) {
    try {
      const response = await fetch(`${API_ROOT}/auto-settlement/config/${merchantId}`, {
        method: 'POST',
        headers: this.getHeaders(true),
        body: JSON.stringify(config)
      });
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Update auto-settlement config error:', error);
      throw error;
    }
  }

  async triggerAutoSettlement(merchantId) {
    try {
      const response = await fetch(`${API_ROOT}/auto-settlement/trigger/${merchantId}`, {
        method: 'POST',
        headers: this.getHeaders(true)
      });
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Trigger auto-settlement error:', error);
      throw error;
    }
  }

  async getAutoSettlementLogs(merchantId, limit = 100) {
    try {
      const response = await fetch(`${API_ROOT}/auto-settlement/logs/${merchantId}?limit=${limit}`, {
        method: 'GET',
        headers: this.getHeaders(true)
      });
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Get auto-settlement logs error:', error);
      throw error;
    }
  }

  async getAllAutoSettlementLogs(limit = 100) {
    try {
      const response = await fetch(`${API_ROOT}/auto-settlement/logs?limit=${limit}`, {
        method: 'GET',
        headers: this.getHeaders(true)
      });
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Get all auto-settlement logs error:', error);
      throw error;
    }
  }

  // Chargeback APIs
  async getChargebackMerchants() {
    try {
      const response = await fetch(`${API_ROOT}/chargeback/admin/merchants`, {
        method: 'GET',
        headers: this.getHeaders(true)
      });
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Get chargeback merchants error:', error);
      throw error;
    }
  }

  async uploadChargebackCSV(formData) {
    try {
      const token = localStorage.getItem('adminToken');
      const response = await fetch(`${API_ROOT}/chargeback/admin/upload`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`
        },
        body: formData
      });
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Upload chargeback CSV error:', error);
      throw error;
    }
  }

  async getChargebackUploads(filters = {}) {
    try {
      const queryParams = new URLSearchParams(filters).toString();
      const response = await fetch(`${API_ROOT}/chargeback/admin/uploads${queryParams ? '?' + queryParams : ''}`, {
        method: 'GET',
        headers: this.getHeaders(true)
      });
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Get chargeback uploads error:', error);
      throw error;
    }
  }

  async getAdminChargebacks(filters = {}) {
    try {
      const queryParams = new URLSearchParams(filters).toString();
      const response = await fetch(`${API_ROOT}/chargeback/admin/chargebacks${queryParams ? '?' + queryParams : ''}`, {
        method: 'GET',
        headers: this.getHeaders(true)
      });
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Get admin chargebacks error:', error);
      throw error;
    }
  }

  async downloadChargebackTemplate() {
    try {
      const response = await fetch(`${API_ROOT}/chargeback/admin/template`, {
        method: 'GET',
        headers: this.getHeaders(false)
      });
      
      if (!response.ok) {
        throw new Error('Failed to download template');
      }
      
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `chargeback_template_${new Date().toISOString().split('T')[0]}.csv`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      
      return { success: true };
    } catch (error) {
      console.error('Download chargeback template error:', error);
      throw error;
    }
  }

  async getAdminChargebackStats() {
    try {
      const response = await fetch(`${API_ROOT}/chargeback/admin/stats`, {
        method: 'GET',
        headers: this.getHeaders(true)
      });
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Get admin chargeback stats error:', error);
      throw error;
    }
  }

  async getAdminDeductions(filters = {}) {
    try {
      const queryParams = new URLSearchParams(filters).toString();
      const response = await fetch(`${API_ROOT}/chargeback/admin/deductions${queryParams ? '?' + queryParams : ''}`, {
        method: 'GET',
        headers: this.getHeaders(true)
      });
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Get admin deductions error:', error);
      throw error;
    }
  }

  async getMerchantHolds(merchantId) {
    try {
      const response = await fetch(`${API_ROOT}/chargeback/admin/merchant-holds/${merchantId}`, {
        method: 'GET',
        headers: this.getHeaders(true)
      });
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Get merchant holds error:', error);
      throw error;
    }
  }

  // Auto-Settlement APIs
  async getAutoSettlementConfig(merchantId) {
    try {
      const response = await fetch(`${API_ROOT}/auto-settlement/config/${merchantId}`, {
        method: 'GET',
        headers: this.getHeaders(true)
      });
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Get auto-settlement config error:', error);
      throw error;
    }
  }

  async updateAutoSettlementConfig(merchantId, config) {
    try {
      const response = await fetch(`${API_ROOT}/auto-settlement/config/${merchantId}`, {
        method: 'POST',
        headers: this.getHeaders(true),
        body: JSON.stringify(config)
      });
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Update auto-settlement config error:', error);
      throw error;
    }
  }

  async triggerAutoSettlement(merchantId) {
    try {
      const response = await fetch(`${API_ROOT}/auto-settlement/trigger/${merchantId}`, {
        method: 'POST',
        headers: this.getHeaders(true)
      });
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Trigger auto-settlement error:', error);
      throw error;
    }
  }

  async getAutoSettlementLogs(merchantId, limit = 100) {
    try {
      const response = await fetch(`${API_ROOT}/auto-settlement/logs/${merchantId}?limit=${limit}`, {
        method: 'GET',
        headers: this.getHeaders(true)
      });
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Get auto-settlement logs error:', error);
      throw error;
    }
  }

  async getAllAutoSettlementLogs(limit = 100) {
    try {
      const response = await fetch(`${API_ROOT}/auto-settlement/logs?limit=${limit}`, {
        method: 'GET',
        headers: this.getHeaders(true)
      });
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Get all auto-settlement logs error:', error);
      throw error;
    }
  }

  // Chargeback APIs
  async getChargebackMerchants() {
    try {
      const response = await fetch(`${API_ROOT}/chargeback/admin/merchants`, {
        method: 'GET',
        headers: this.getHeaders(true)
      });
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Get chargeback merchants error:', error);
      throw error;
    }
  }

  async uploadChargebackCSV(formData) {
    try {
      const token = localStorage.getItem('adminToken');
      const response = await fetch(`${API_ROOT}/chargeback/admin/upload`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`
        },
        body: formData
      });
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Upload chargeback CSV error:', error);
      throw error;
    }
  }

  async getChargebackUploads(filters = {}) {
    try {
      const queryParams = new URLSearchParams(filters).toString();
      const response = await fetch(`${API_ROOT}/chargeback/admin/uploads${queryParams ? '?' + queryParams : ''}`, {
        method: 'GET',
        headers: this.getHeaders(true)
      });
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Get chargeback uploads error:', error);
      throw error;
    }
  }

  async getAdminChargebacks(filters = {}) {
    try {
      const queryParams = new URLSearchParams(filters).toString();
      const response = await fetch(`${API_ROOT}/chargeback/admin/chargebacks${queryParams ? '?' + queryParams : ''}`, {
        method: 'GET',
        headers: this.getHeaders(true)
      });
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Get admin chargebacks error:', error);
      throw error;
    }
  }

  async downloadChargebackTemplate() {
    try {
      const response = await fetch(`${API_ROOT}/chargeback/admin/template`, {
        method: 'GET',
        headers: this.getHeaders(false)
      });
      
      if (!response.ok) {
        throw new Error('Failed to download template');
      }
      
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `chargeback_template_${new Date().toISOString().split('T')[0]}.csv`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      
      return { success: true };
    } catch (error) {
      console.error('Download chargeback template error:', error);
      throw error;
    }
  }

  async getAdminChargebackStats() {
    try {
      const response = await fetch(`${API_ROOT}/chargeback/admin/stats`, {
        method: 'GET',
        headers: this.getHeaders(true)
      });
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Get admin chargeback stats error:', error);
      throw error;
    }
  }

  async getAdminDeductions(filters = {}) {
    try {
      const queryParams = new URLSearchParams(filters).toString();
      const response = await fetch(`${API_ROOT}/chargeback/admin/deductions${queryParams ? '?' + queryParams : ''}`, {
        method: 'GET',
        headers: this.getHeaders(true)
      });
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Get admin deductions error:', error);
      throw error;
    }
  }

  async getMerchantHolds(merchantId) {
    try {
      const response = await fetch(`${API_ROOT}/chargeback/admin/merchant-holds/${merchantId}`, {
        method: 'GET',
        headers: this.getHeaders(true)
      });
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Get merchant holds error:', error);
      throw error;
    }
  }

  async updateMerchantHolds(data) {
    try {
      const response = await fetch(`${API_ROOT}/chargeback/admin/merchant-holds`, {
        method: 'POST',
        headers: this.getHeaders(true),
        body: JSON.stringify(data)
      });
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Update merchant holds error:', error);
      throw error;
    }
  }

  // User Transaction Summary APIs
  async getUserTransactionSummaryMerchants() {
    try {
      const response = await fetch(`${API_BASE_URL}/user-transaction-summary/merchants`, {
        method: 'GET',
        headers: this.getHeaders(true)
      });
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Get user transaction summary merchants error:', error);
      throw error;
    }
  }

  async getUserTransactionSummary(params) {
    try {
      const queryParams = new URLSearchParams(params).toString();
      const response = await fetch(`${API_BASE_URL}/user-transaction-summary/summary?${queryParams}`, {
        method: 'GET',
        headers: this.getHeaders(true)
      });
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Get user transaction summary error:', error);
      throw error;
    }
  }

  // ─────────────────────────────────────────────────────────────────────────────
  // QR Payment APIs (Admin)
  // ─────────────────────────────────────────────────────────────────────────────

  async getQRCodes() {
    try {
      const response = await fetch(`${API_ROOT}/qr/admin/qr-codes`, {
        method: 'GET',
        headers: this.getHeaders(true),
      });
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Get QR codes error:', error);
      throw error;
    }
  }

  async uploadQRCode(formData) {
    try {
      const token = localStorage.getItem('adminToken');
      const response = await fetch(`${API_ROOT}/qr/admin/qr-codes`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` }, // FormData sets its own Content-Type
        body: formData,
      });
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Upload QR code error:', error);
      throw error;
    }
  }

  async deleteQRCode(qrId) {
    try {
      const response = await fetch(`${API_ROOT}/qr/admin/qr-codes/${qrId}`, {
        method: 'DELETE',
        headers: this.getHeaders(true),
      });
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Delete QR code error:', error);
      throw error;
    }
  }

  async getMerchantQRRouting() {
    try {
      const response = await fetch(`${API_ROOT}/qr/admin/merchant-routing`, {
        method: 'GET',
        headers: this.getHeaders(true),
      });
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Get merchant QR routing error:', error);
      throw error;
    }
  }

  async setMerchantQRRouting(data) {
    try {
      const response = await fetch(`${API_ROOT}/qr/admin/merchant-routing`, {
        method: 'POST',
        headers: this.getHeaders(true),
        body: JSON.stringify(data),
      });
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Set merchant QR routing error:', error);
      throw error;
    }
  }

  async getQRTransactions(params = {}) {
    try {
      const queryString = new URLSearchParams(params).toString();
      const response = await fetch(`${API_ROOT}/qr/admin/transactions?${queryString}`, {
        method: 'GET',
        headers: this.getHeaders(true),
      });
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Get QR transactions error:', error);
      throw error;
    }
  }

  async approveQRTransaction(txnId) {
    try {
      const response = await fetch(`${API_ROOT}/qr/admin/approve/${txnId}`, {
        method: 'POST',
        headers: this.getHeaders(true),
      });
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Approve QR transaction error:', error);
      throw error;
    }
  }

  async rejectQRTransaction(txnId) {
    try {
      const response = await fetch(`${API_ROOT}/qr/admin/reject/${txnId}`, {
        method: 'POST',
        headers: this.getHeaders(true),
      });
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Reject QR transaction error:', error);
      throw error;
    }
  }

  // Risexpay Auto Success Toggle
  async getRisexpayAutoSuccess(merchantId = null) {
    try {
      let url = `${import.meta.env.VITE_API_BASE_URL || 'http://localhost:5000/api'}/payout/admin/risexpay-auto-success`;
      if (merchantId) {
        url += `?merchant_id=${merchantId}`;
      }
      const response = await fetch(url, {
        method: 'GET',
        headers: this.getHeaders(true),
      });
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Get Risexpay auto-success error:', error);
      throw error;
    }
  }

  async toggleRisexpayAutoSuccess(enabled, merchantId = null) {
    try {
      const body = { enabled };
      if (merchantId) {
        body.merchant_id = merchantId;
      }
      const response = await fetch(`${import.meta.env.VITE_API_BASE_URL || 'http://localhost:5000/api'}/payout/admin/risexpay-auto-success`, {
        method: 'POST',
        headers: this.getHeaders(true),
        body: JSON.stringify(body),
      });
      return await this.handleResponse(response);
    } catch (error) {
      console.error('Toggle Risexpay auto-success error:', error);
      throw error;
    }
  }

  async completeHdfcJviPayin(txnId, action, utr = '', remarks = '') {
    try {
      const response = await fetch(`${API_ROOT}/payin/admin/hdfc-jvi/complete/${txnId}`, {
        method: 'POST',
        headers: this.getHeaders(true),
        body: JSON.stringify({ action, utr, remarks }),
      });
      return await this.handleResponse(response);
    } catch (error) {
      console.error('HDFC JVI complete payin error:', error);
      throw error;
    }
  }

}

// Export singleton instance
const adminAPI = new AdminAPI();
export default adminAPI;
