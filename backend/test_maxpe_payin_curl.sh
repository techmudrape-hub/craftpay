#!/bin/bash

# MaxPe Payin Test Script using cURL
# This script tests MaxPe payin API using command-line tools

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Load environment variables from .env file
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | grep 'MAXPE_' | xargs)
else
    echo -e "${RED}Error: .env file not found${NC}"
    exit 1
fi

# Check if required variables are set
if [ -z "$MAXPE_BASE_URL" ] || [ -z "$MAXPE_API_KEY" ] || [ -z "$MAXPE_API_SECRET" ]; then
    echo -e "${RED}Error: MAXPE_BASE_URL, MAXPE_API_KEY, and MAXPE_API_SECRET must be set in .env${NC}"
    exit 1
fi

echo "================================================================================"
echo "MaxPe Payin Test Script (cURL)"
echo "================================================================================"
echo -e "${BLUE}Base URL:${NC} $MAXPE_BASE_URL"
echo -e "${BLUE}API Key:${NC} ${MAXPE_API_KEY:0:20}..."
echo "================================================================================"

# Function to generate HMAC SHA256 signature
generate_signature() {
    local data_string="$1"
    echo -n "$data_string" | openssl dgst -sha256 -hmac "$MAXPE_API_SECRET" | sed 's/^.* //'
}

# Function to generate nonce
generate_nonce() {
    cat /dev/urandom | tr -dc 'a-z0-9' | fold -w 16 | head -n 1
}

# Test 1: Create Payment Order
test_create_payment() {
    echo ""
    echo "================================================================================"
    echo "TEST 1: Create Payment Order"
    echo "================================================================================"
    
    # Generate test data
    local merchant_order_id="CURL_TEST_$(date +%Y%m%d%H%M%S)"
    local timestamp=$(date +%s)
    local nonce=$(generate_nonce)
    local amount="${1:-100.00}"
    local name="cURL Test User"
    local mobile="9876543210"
    local email="curltest@example.com"
    
    echo -e "${BLUE}Merchant Order ID:${NC} $merchant_order_id"
    echo -e "${BLUE}Amount:${NC} ₹$amount"
    echo -e "${BLUE}Timestamp:${NC} $timestamp"
    echo -e "${BLUE}Nonce:${NC} $nonce"
    
    # Build signature data (alphabetically sorted)
    local sig_data="amount=${amount}&email=${email}&merchant_order_id=${merchant_order_id}&mobile=${mobile}&name=${name}&nonce=${nonce}&timestamp=${timestamp}"
    
    echo -e "${BLUE}Signature Data:${NC} $sig_data"
    
    # Generate signature
    local signature=$(generate_signature "$sig_data")
    
    echo -e "${BLUE}Signature:${NC} $signature"
    
    # Prepare JSON payload
    local payload=$(cat <<EOF
{
    "name": "$name",
    "mobile": "$mobile",
    "email": "$email",
    "amount": "$amount",
    "merchant_order_id": "$merchant_order_id"
}
EOF
)
    
    echo ""
    echo -e "${BLUE}Request Payload:${NC}"
    echo "$payload"
    
    # Make API request
    echo ""
    echo -e "${YELLOW}Sending request... (this may take 30-120 seconds)${NC}"
    
    local start_time=$(date +%s)
    
    local response=$(curl -s -w "\n%{http_code}" \
        -X POST \
        -H "Content-Type: application/json" \
        -H "Accept: application/json" \
        -H "X-API-KEY: $MAXPE_API_KEY" \
        -H "X-TIMESTAMP: $timestamp" \
        -H "X-NONCE: $nonce" \
        -H "X-SIGNATURE: $signature" \
        -d "$payload" \
        --max-time 120 \
        "$MAXPE_BASE_URL/api/prod/payin/create-payment" 2>&1)
    
    local end_time=$(date +%s)
    local elapsed=$((end_time - start_time))
    
    # Extract HTTP status code (last line)
    local http_code=$(echo "$response" | tail -n 1)
    local response_body=$(echo "$response" | sed '$d')
    
    echo ""
    echo -e "${BLUE}Response Time:${NC} ${elapsed}s"
    echo -e "${BLUE}HTTP Status:${NC} $http_code"
    echo -e "${BLUE}Response Body:${NC}"
    echo "$response_body" | python3 -m json.tool 2>/dev/null || echo "$response_body"
    
    # Check if successful
    if [ "$http_code" = "200" ] || [ "$http_code" = "201" ]; then
        local status=$(echo "$response_body" | grep -o '"status"[[:space:]]*:[[:space:]]*[^,}]*' | sed 's/.*:[[:space:]]*//')
        
        if [ "$status" = "true" ]; then
            echo ""
            echo -e "${GREEN}✅ SUCCESS: Payment order created${NC}"
            
            # Extract UPI link
            local upi_link=$(echo "$response_body" | grep -o '"upi_deeplink"[[:space:]]*:[[:space:]]*"[^"]*"' | sed 's/.*:[[:space:]]*"\(.*\)"/\1/')
            
            if [ -n "$upi_link" ]; then
                echo -e "${GREEN}UPI Link:${NC} ${upi_link:0:100}..."
            fi
            
            # Save order ID for status check
            echo "$merchant_order_id" > /tmp/maxpe_last_order_id.txt
            echo ""
            echo -e "${YELLOW}Order ID saved to /tmp/maxpe_last_order_id.txt${NC}"
            echo -e "${YELLOW}Use this for status check: $merchant_order_id${NC}"
        else
            echo ""
            echo -e "${RED}❌ FAILED: Payment order creation failed${NC}"
        fi
    else
        echo ""
        echo -e "${RED}❌ HTTP ERROR: $http_code${NC}"
    fi
}

# Test 2: Check Payment Status
test_check_status() {
    echo ""
    echo "================================================================================"
    echo "TEST 2: Check Payment Status"
    echo "================================================================================"
    
    local merchant_order_id="$1"
    
    # If no order ID provided, try to load from file
    if [ -z "$merchant_order_id" ]; then
        if [ -f /tmp/maxpe_last_order_id.txt ]; then
            merchant_order_id=$(cat /tmp/maxpe_last_order_id.txt)
            echo -e "${YELLOW}Using saved order ID: $merchant_order_id${NC}"
        else
            echo -e "${RED}Error: No merchant_order_id provided${NC}"
            echo "Usage: $0 status <merchant_order_id>"
            return 1
        fi
    fi
    
    echo -e "${BLUE}Merchant Order ID:${NC} $merchant_order_id"
    
    # Make API request (status check uses form data)
    echo ""
    echo -e "${YELLOW}Checking status...${NC}"
    
    local response=$(curl -s -w "\n%{http_code}" \
        -X POST \
        -H "X-API-KEY: $MAXPE_API_KEY" \
        -d "merchant_order_id=$merchant_order_id" \
        --max-time 60 \
        "$MAXPE_BASE_URL/api/prod/payin1/status" 2>&1)
    
    # Extract HTTP status code
    local http_code=$(echo "$response" | tail -n 1)
    local response_body=$(echo "$response" | sed '$d')
    
    echo ""
    echo -e "${BLUE}HTTP Status:${NC} $http_code"
    echo -e "${BLUE}Response Body:${NC}"
    echo "$response_body" | python3 -m json.tool 2>/dev/null || echo "$response_body"
    
    # Check if successful
    if [ "$http_code" = "200" ] || [ "$http_code" = "201" ]; then
        local status=$(echo "$response_body" | grep -o '"status"[[:space:]]*:[[:space:]]*[^,}]*' | sed 's/.*:[[:space:]]*//')
        
        if [ "$status" = "true" ]; then
            echo ""
            echo -e "${GREEN}✅ SUCCESS: Status retrieved${NC}"
            
            # Extract transaction status
            local txn_status=$(echo "$response_body" | grep -o '"transaction_status"[[:space:]]*:[[:space:]]*"[^"]*"' | sed 's/.*:[[:space:]]*"\(.*\)"/\1/')
            local amount=$(echo "$response_body" | grep -o '"amount"[[:space:]]*:[[:space:]]*"[^"]*"' | sed 's/.*:[[:space:]]*"\(.*\)"/\1/')
            local utr=$(echo "$response_body" | grep -o '"utr"[[:space:]]*:[[:space:]]*"[^"]*"' | sed 's/.*:[[:space:]]*"\(.*\)"/\1/')
            
            echo -e "${BLUE}Transaction Status:${NC} $txn_status"
            echo -e "${BLUE}Amount:${NC} ₹$amount"
            echo -e "${BLUE}UTR:${NC} $utr"
        else
            echo ""
            echo -e "${RED}❌ FAILED: Status check failed${NC}"
        fi
    else
        echo ""
        echo -e "${RED}❌ HTTP ERROR: $http_code${NC}"
    fi
}

# Main menu
case "$1" in
    create)
        test_create_payment "$2"
        ;;
    status)
        test_check_status "$2"
        ;;
    full)
        echo "Running full test flow..."
        test_create_payment "$2"
        echo ""
        echo "Waiting 10 seconds before status check..."
        sleep 10
        test_check_status
        ;;
    *)
        echo "Usage: $0 {create|status|full} [amount|order_id]"
        echo ""
        echo "Commands:"
        echo "  create [amount]           - Create payment order (default: 100.00)"
        echo "  status [order_id]         - Check payment status"
        echo "  full [amount]             - Create order + wait + check status"
        echo ""
        echo "Examples:"
        echo "  $0 create 100.00"
        echo "  $0 status CURL_TEST_20260513120000"
        echo "  $0 full 50.00"
        exit 1
        ;;
esac

echo ""
echo "================================================================================"
echo "Test completed"
echo "================================================================================"
