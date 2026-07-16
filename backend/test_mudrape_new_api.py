#!/usr/bin/env python3
"""
Test script for NEW Mudrape API integration
Tests the create-intent endpoint directly
"""

import requests
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Mudrape credentials
BASE_URL = os.getenv('MUDRAPE_BASE_URL', 'https://agentmudrape.com')
API_KEY = os.getenv('MUDRAPE_API_KEY')
API_SECRET = os.getenv('MUDRAPE_API_SECRET')
USER_ID = os.getenv('MUDRAPE_USER_ID')

print("=" * 80)
print("MUDRAPE NEW API TEST")
print("=" * 80)
print(f"Base URL: {BASE_URL}")
print(f"User ID: {USER_ID}")
print(f"API Key: {API_KEY[:20]}..." if API_KEY else "API Key: NOT SET")
print(f"API Secret: {API_SECRET[:20]}..." if API_SECRET else "API Secret: NOT SET")
print("=" * 80)
print()

# Test 1: Create Payment Intent
print("TEST 1: Create Payment Intent")
print("-" * 80)

url = f"{BASE_URL}/api/mudrape-payin/create-intent"

headers = {
    'x-user-id': USER_ID,
    'x-api-key': API_KEY,
    'x-api-secret': API_SECRET,
    'Content-Type': 'application/json'
}

payload = {
    'orderId': 'TEST_ORDER_12345',
    'amount': 100.50,
    'customerName': 'Test Customer',
    'customerPhone': '9876543210',
    'paymentRemark': 'Test Payment'
}

print(f"URL: {url}")
print(f"Headers:")
print(f"  x-user-id: {USER_ID}")
print(f"  x-api-key: {API_KEY[:20]}...")
print(f"  x-api-secret: {API_SECRET[:20]}...")
print(f"  Content-Type: application/json")
print()
print(f"Payload:")
print(json.dumps(payload, indent=2))
print()

try:
    response = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=30
    )
    
    print(f"Response Status: {response.status_code}")
    print(f"Response Headers:")
    for key, value in response.headers.items():
        print(f"  {key}: {value}")
    print()
    print(f"Response Body:")
    
    try:
        response_json = response.json()
        print(json.dumps(response_json, indent=2))
        
        if response_json.get('success'):
            print()
            print("✅ SUCCESS - Payment intent created!")
            data = response_json.get('data', {})
            print(f"  Payin ID: {data.get('payinId')}")
            print(f"  Payin Reference ID: {data.get('payinReferenceId')}")
            print(f"  Transaction ID: {data.get('transactionId')}")
            print(f"  Intent Link: {data.get('intentLink')[:50]}..." if data.get('intentLink') else "  Intent Link: NOT PROVIDED")
        else:
            print()
            print("❌ FAILED - Payment intent creation failed")
            print(f"  Message: {response_json.get('message')}")
    except json.JSONDecodeError:
        print(response.text)
        print()
        print("❌ Response is not valid JSON")
    
except requests.exceptions.RequestException as e:
    print(f"❌ Request failed: {e}")

print()
print("=" * 80)

# Test 2: Check if endpoint exists (try different variations)
print()
print("TEST 2: Endpoint Availability Check")
print("-" * 80)

endpoints_to_test = [
    '/api/mudrape-payin/create-intent',
    '/api/mudrape-payin/createIntent',
    '/api/mudrape/payin/create-intent',
    '/api/payin/create-intent',
]

for endpoint in endpoints_to_test:
    test_url = f"{BASE_URL}{endpoint}"
    print(f"Testing: {test_url}")
    
    try:
        response = requests.post(
            test_url,
            headers=headers,
            json=payload,
            timeout=10
        )
        print(f"  Status: {response.status_code}")
        if response.status_code != 404:
            print(f"  Response: {response.text[:100]}")
    except Exception as e:
        print(f"  Error: {e}")
    print()

print("=" * 80)
print()

# Test 3: Try with minimal payload
print("TEST 3: Minimal Payload Test")
print("-" * 80)

minimal_payload = {
    'orderId': 'MIN_TEST_123',
    'amount': 100,
    'customerName': 'Test',
    'customerPhone': '9876543210'
}

print(f"Minimal Payload:")
print(json.dumps(minimal_payload, indent=2))
print()

try:
    response = requests.post(
        f"{BASE_URL}/api/mudrape-payin/create-intent",
        headers=headers,
        json=minimal_payload,
        timeout=30
    )
    
    print(f"Response Status: {response.status_code}")
    print(f"Response Body:")
    try:
        print(json.dumps(response.json(), indent=2))
    except:
        print(response.text)
    
except Exception as e:
    print(f"❌ Request failed: {e}")

print()
print("=" * 80)
print("TEST COMPLETE")
print("=" * 80)
