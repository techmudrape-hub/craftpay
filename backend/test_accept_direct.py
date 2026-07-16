#!/usr/bin/env python3
"""
Direct test of accept endpoint
"""

import requests
import json

# Test with your actual token and chargeback ID
TOKEN = "YOUR_TOKEN_HERE"  # Replace with actual token from login
CHARGEBACK_ID = 20  # Replace with actual chargeback ID

API_URL = "http://localhost:5000/api/chargeback/merchant/accept/{}".format(CHARGEBACK_ID)

print(f"Testing URL: {API_URL}")
print(f"Token: {TOKEN[:20]}...")
print()

# Test 1: With empty JSON body
print("Test 1: POST with empty JSON body")
response1 = requests.post(
    API_URL,
    headers={
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json"
    },
    json={}
)
print(f"Status: {response1.status_code}")
print(f"Response: {response1.text[:200]}")
print()

# Test 2: With no body
print("Test 2: POST with no body")
response2 = requests.post(
    API_URL,
    headers={
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json"
    }
)
print(f"Status: {response2.status_code}")
print(f"Response: {response2.text[:200]}")
print()

# Test 3: With data parameter instead of json
print("Test 3: POST with data parameter")
response3 = requests.post(
    API_URL,
    headers={
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json"
    },
    data=json.dumps({})
)
print(f"Status: {response3.status_code}")
print(f"Response: {response3.text[:200]}")
