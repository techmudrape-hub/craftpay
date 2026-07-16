# MaxPe Payin Test - Quick Start

## Quick Commands

### Run Automated Test Suite
```bash
cd backend
python test_maxpe_payin_auto.py
```
**Best for:** Quick verification, CI/CD, automated testing

### Run Interactive Test
```bash
cd backend
python test_maxpe_payin.py
```
**Best for:** Manual testing, debugging, payment verification

## Test Options

### Interactive Test Menu
```
1. Create Payment Order Only     → Get UPI link
2. Check Payment Status Only     → Verify existing order
3. Full Test Flow               → Create + Wait + Check
4. Quick Test                   → Create + 10s + Check
```

## Quick Test Examples

### Example 1: Create Order and Get UPI Link
```bash
python test_maxpe_payin.py
# Choose: 1
# Amount: 100
# Result: UPI deeplink for payment
```

### Example 2: Check Existing Order Status
```bash
python test_maxpe_payin.py
# Choose: 2
# Order ID: TEST_MAXPE_20260513120000
# Result: Current payment status
```

### Example 3: Full Payment Test
```bash
python test_maxpe_payin.py
# Choose: 3
# Amount: 50
# Action: Complete payment on phone
# Result: Final status after 60s
```

### Example 4: Quick API Test
```bash
python test_maxpe_payin.py
# Choose: 4
# Amount: 10
# Result: Order created + status in 10s
```

## Expected Results

### ✅ Success
```
✅ SUCCESS: Payment order created
UPI Deeplink: upi://pay?pa=...
Transaction Status: SUCCESS
```

### ⚠️ Timeout (Normal)
```
⚠️ TIMEOUT after 45.23s
This is common with MaxPe API
Transaction may still be created
```

### ❌ Error
```
❌ FAILED: Invalid API credentials
❌ HTTP ERROR: 401
```

## Automated Test Results

### All Tests Pass
```
Total Tests: 6
✅ Passed: 6
❌ Failed: 0
Success Rate: 100.0%
```

### Some Tests Fail
```
Total Tests: 6
✅ Passed: 4
❌ Failed: 2
Success Rate: 66.7%
```

## Common Commands

### Test with Custom Amount
```bash
python test_maxpe_payin.py
# Choose: 1
# Amount: 250.50
```

### Check Multiple Orders
```bash
python test_maxpe_payin.py
# Choose: 2
# Order ID: ORDER_001

python test_maxpe_payin.py
# Choose: 2
# Order ID: ORDER_002
```

### Run Tests in Sequence
```bash
# 1. Run automated tests
python test_maxpe_payin_auto.py

# 2. If all pass, create real order
python test_maxpe_payin.py
# Choose: 1
# Amount: 100
```

## Troubleshooting

### Problem: Missing credentials
```bash
# Check .env file
cat .env | grep MAXPE

# Should show:
# MAXPE_BASE_URL=https://merchant.maxpe.tech
# MAXPE_API_KEY=537a3441...
# MAXPE_API_SECRET=a0fb8bb4...
```

### Problem: Import errors
```bash
# Install dependencies
pip install requests python-dotenv
```

### Problem: Connection timeout
```bash
# This is normal for MaxPe
# Wait and check status:
python test_maxpe_payin.py
# Choose: 2
# Order ID: [your_order_id]
```

## Integration Testing

### Test Service Routing
```sql
-- Check if MaxPe is configured
SELECT * FROM service_routing 
WHERE pg_partner = 'MAXPE' 
AND service_type = 'PAYIN';
```

### Test Recent Transactions
```sql
-- View recent MaxPe transactions
SELECT txn_id, order_id, amount, status, created_at 
FROM payin_transactions 
WHERE pg_partner = 'MAXPE' 
ORDER BY created_at DESC 
LIMIT 10;
```

### Test Callback Logs
```sql
-- Check callback attempts
SELECT merchant_id, txn_id, response_code, created_at 
FROM callback_logs 
WHERE txn_id LIKE '%MAXPE%' 
ORDER BY created_at DESC 
LIMIT 10;
```

## Performance Benchmarks

### Expected Response Times
- **Create Order**: 30-120 seconds (MaxPe is slow)
- **Status Check**: 5-30 seconds
- **Callback**: Immediate to 5 minutes

### Timeout Settings
- **Connect Timeout**: 15 seconds
- **Read Timeout**: 120 seconds (2 minutes)
- **Status Check Timeout**: 60 seconds

## Test Data

### Valid Test Data
```python
name = "Test User"
mobile = "9876543210"
email = "test@example.com"
amount = "100.00"
```

### Invalid Test Data (for error testing)
```python
name = ""  # Empty name
mobile = "123"  # Invalid mobile
email = "invalid"  # Invalid email
amount = "-10"  # Negative amount
```

## Next Steps

1. ✅ Run automated test: `python test_maxpe_payin_auto.py`
2. ✅ Verify all tests pass
3. ✅ Create test order: `python test_maxpe_payin.py` (Option 1)
4. ✅ Complete payment on phone
5. ✅ Check status: `python test_maxpe_payin.py` (Option 2)
6. ✅ Review logs and database

## Support Files

- **Test Scripts**: `test_maxpe_payin.py`, `test_maxpe_payin_auto.py`
- **Service**: `maxpe_service.py`
- **Callbacks**: `maxpe_callback_routes.py`
- **Documentation**: `MAXPE_PAYIN_TEST_GUIDE.md`
- **Config**: `.env` (MAXPE_* variables)
