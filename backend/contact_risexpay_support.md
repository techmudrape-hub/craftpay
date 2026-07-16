# Contact Risexpay Support - Signature Issue

## Issue
We are getting "Invalid signature" error when trying to integrate Risexpay Payin API.

## What We've Tried
We have tested multiple canonical string formats for HMAC-SHA256 signature generation:

1. **Format 1**: `amount=100&apikey=xxx&customer_mobile=xxx&mid=xxx&redirect_url=xxx&timestamp=xxx`
2. **Format 2**: `amount=100&apikey=xxx&customer_mobile=xxx&mid=xxx&redirect_url=xxx` (no timestamp)
3. **Format 3**: JSON string with sorted keys
4. **Format 4**: Timestamp + JSON string
5. **Format 5**: All fields including timestamp sorted alphabetically

All formats result in "Invalid signature" error (HTTP 401).

## Our Current Implementation

### Request Headers
```
Content-Type: application/json
X-Timestamp: 1779296262
X-Signature: f9eb09eda0414b9331acca8b9f383d9fdbb2de0f68460d2f28a9556cb3f8d2aa
```

### Request Body
```json
{
  "mid": "RPAYZ3703882115",
  "apikey": "5xzos01v7xzo7pwc",
  "amount": 100,
  "customer_mobile": "9876543210",
  "redirect_url": "https://api.craftpay.in/api/callback/risexpay/payin"
}
```

### Canonical String Used
```
amount=100&apikey=5xzos01v7xzo7pwc&customer_mobile=9876543210&mid=RPAYZ3703882115&redirect_url=https://api.craftpay.in/api/callback/risexpay/payin&timestamp=1779296262
```

### Signature Generation
```python
canonical_string = "amount=100&apikey=5xzos01v7xzo7pwc&customer_mobile=9876543210&mid=RPAYZ3703882115&redirect_url=https://api.craftpay.in/api/callback/risexpay/payin&timestamp=1779296262"
signature = hmac.new(
    secret_key.encode('utf-8'),
    canonical_string.encode('utf-8'),
    hashlib.sha256
).hexdigest()
```

## What We Need

1. **Integration Helper Package for Python**
   - The exact canonical string format for signature generation
   - Sample code showing how to build the canonical string
   - The correct order of fields
   - Whether timestamp should be included in the canonical string or not

2. **Verification of Credentials**
   - Confirm our MID: `RPAYZ3703882115`
   - Confirm our API Key: `5xzos01v7xzo7pwc`
   - Verify we have the correct Payin Secret Key

3. **Example Request**
   - A complete working example with:
     - Request payload
     - Timestamp
     - Canonical string
     - Expected signature
     - Request headers

## Contact Information

**Email to send**: support@risexpay.in

**Subject**: Integration Helper Package Request - Invalid Signature Error

**Body**:
```
Dear Risexpay Support Team,

We are integrating Risexpay Payin API into our payment gateway system (OrchPay) and are encountering "Invalid signature" errors.

Merchant Details:
- MID: RPAYZ3703882115
- API Key: 5xzos01v7xzo7pwc

We have implemented HMAC-SHA256 signature generation as per the documentation, but all our attempts result in "Invalid signature" error (HTTP 401).

We have tested multiple canonical string formats including:
1. Sorted fields with timestamp appended
2. Sorted fields without timestamp
3. JSON string formats
4. Various field ordering combinations

Could you please provide:
1. The Integration Helper Package for Python
2. The exact canonical string format for signature generation
3. A working example with expected signature for verification
4. Confirmation that our credentials are correct

We would appreciate your urgent assistance as this is blocking our integration.

Thank you,
OrchPay Development Team
```

## Alternative: Ask Your Account Manager

If you have a dedicated account manager at Risexpay, contact them directly for faster response.

## Temporary Workaround

Until we get the correct format from Risexpay, you can:
1. Use other payment gateways (Maxpe, ClocksPay, Razorpay) that are already integrated
2. Configure service routing to use a different gateway for payin
3. Wait for Risexpay's response with the correct format

## Once We Get the Correct Format

We will:
1. Update `backend/risexpay_service.py` with the correct signature generation
2. Test with 100 rupee transaction
3. Update documentation
4. Deploy to production
