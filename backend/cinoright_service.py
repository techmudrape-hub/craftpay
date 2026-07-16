"""
Cinoright Payment Gateway Integration Service
Handles payout transactions through Cinoright
"""

import requests
import json
import uuid
from datetime import datetime
from config import Config
from database import get_db_connection

class CinorightService:
    def __init__(self):
        self.base_url = Config.CINORIGHT_BASE_URL
        self.api_key = Config.CINORIGHT_API_KEY
        self.secret_key = Config.CINORIGHT_SECRET_KEY
        self.user_id = Config.CINORIGHT_USER_ID
    
    def get_headers(self):
        """
        Get request headers for Cinoright API
        All requests require ApiKey, SecretKey, and UserId headers
        """
        headers = {
            'ApiKey': self.api_key,
            'SecretKey': self.secret_key,
            'UserId': self.user_id,
            'Content-Type': 'application/json'
        }
        return headers
    
    def calculate_charges(self, amount, scheme_id, service_type='PAYOUT'):
        """Calculate charges based on scheme"""
        try:
            conn = get_db_connection()
            if not conn:
                return None, None, None
            
            with conn.cursor() as cursor:
                # Get applicable charge
                cursor.execute("""
                    SELECT charge_value, charge_type
                    FROM commercial_charges
                    WHERE scheme_id = %s 
                    AND service_type = %s
                    AND %s BETWEEN min_amount AND max_amount
                    ORDER BY min_amount DESC
                    LIMIT 1
                """, (scheme_id, service_type, amount))
                
                charge_config = cursor.fetchone()
                
                if not charge_config:
                    # No charges configured
                    return 0.00, amount, 'FIXED'
                
                charge_type = charge_config['charge_type']
                charge_value = float(charge_config['charge_value'])
                
                if charge_type == 'PERCENTAGE':
                    charge_amount = (amount * charge_value) / 100
                else:  # FIXED
                    charge_amount = charge_value
                
                net_amount = amount - charge_amount
                
                return round(charge_amount, 2), round(net_amount, 2), charge_type
                
        except Exception as e:
            print(f"Calculate charges error: {e}")
            return None, None, None
        finally:
            if conn:
                conn.close()
    
    def call_imps_payout_api(self, account_number, ifsc_code, reference_id, amount, beneficiary_name, 
                            email=None, phone=None):
        """
        Simple IMPS payout API call to Cinoright (no database operations)
        Returns the API response
        
        Args:
            account_number: Beneficiary bank account number
            ifsc_code: Beneficiary IFSC code
            reference_id: Unique transaction ID from your system
            amount: Transfer amount in INR (Min 100)
            beneficiary_name: Beneficiary's full name
            email: Email ID (optional)
            phone: Phone number (optional)
        """
        try:
            url = f"{self.base_url}/api/v1/a/payout/imps-payout"
            
            # Fixed values as per requirements
            payload = {
                'amount': str(int(amount)),  # Amount as string
                'reference': reference_id,  # Unique reference/txn ID
                'bankAccount': account_number,  # Beneficiary bank account number
                'ifsc': ifsc_code,  # IFSC code
                'name': beneficiary_name,  # Beneficiary full name
                'email': email or 'admin@orchpay.in',  # Email ID
                'phone': phone or '9999999999',  # Phone number
                'address': 'India',  # Fixed address
                'bankProfileId': '098392',  # Fixed bank profile ID (numeric string)
                'latitude': '28.7041',  # Fixed latitude (Delhi)
                'longitude': '77.1025',  # Fixed longitude (Delhi)
                'remarks': 'Payout Fund'  # Fixed remarks
            }
            
            print(f"Calling Cinoright IMPS payout API: {payload}")
            print(f"URL: {url}")
            
            response = requests.post(
                url,
                headers=self.get_headers(),
                json=payload,
                timeout=30
            )
            
            print(f"Cinoright IMPS Payout Response: {response.status_code} - {response.text}")
            
            if response.status_code not in [200, 201]:
                return {
                    'success': False,
                    'message': f'Cinoright API error: {response.text}'
                }
            
            cinoright_response = response.json()
            
            # Check if Cinoright returned success=false in response body
            if not cinoright_response.get('success'):
                error_msg = cinoright_response.get('message', 'Payout failed')
                print(f"Cinoright returned success=false: {error_msg}")
                return {
                    'success': False,
                    'message': error_msg
                }
            
            # Extract data from response
            data = cinoright_response.get('data', {})
            status = data.get('status', 'PENDING').upper()
            status_code = data.get('statusCode', '201')
            message = data.get('message', 'Transaction Under Process')
            
            # Extract transaction details
            transaction_data = data.get('data', {})
            transaction_id = transaction_data.get('transactionId', '')
            utr = transaction_data.get('utr')
            client_reference_id = transaction_data.get('client_referenceId', reference_id)
            acknowledged = transaction_data.get('acknowledged', 0)
            
            print(f"Parsed - Status: {status}, Status Code: {status_code}, Message: {message}")
            print(f"Transaction ID: {transaction_id}, UTR: {utr}, Client Ref: {client_reference_id}")
            
            # Map Cinoright status to our status
            # Database ENUM: INITIATED, QUEUED, INPROCESS, SUCCESS, FAILED, REVERSED
            if status == 'SUCCESS':
                mapped_status = 'SUCCESS'
            elif status == 'FAILED':
                mapped_status = 'FAILED'
            elif status == 'PENDING':
                mapped_status = 'INITIATED'
            else:
                mapped_status = 'INITIATED'  # Default to INITIATED
            
            print(f"Mapped Status: {mapped_status}")
            
            return {
                'success': True,
                'status': mapped_status,
                'status_code': status_code,
                'cinoright_txn_id': transaction_id,
                'utr': utr,
                'client_reference_id': client_reference_id,
                'acknowledged': acknowledged,
                'message': message,
                'data': cinoright_response
            }
            
        except Exception as e:
            print(f"IMPS payout API call error: {e}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'message': f'API call error: {str(e)}'}
    
    def check_payout_status(self, txn_id):
        """
        Check payout status on Cinoright
        
        Args:
            txn_id: The transaction ID from Cinoright
        
        Returns:
            dict: Status information
        """
        try:
            print(f"Checking Cinoright payout status - txn_id: {txn_id}")
            
            url = f"{self.base_url}/api/payout/a/check-status"
            
            payload = {
                'txn_id': txn_id
            }
            
            print(f"Status check payload: {payload}")
            
            response = requests.post(
                url,
                headers=self.get_headers(),
                json=payload,
                timeout=30
            )
            
            print(f"Response: {response.status_code} - {response.text[:500]}")
            
            if response.status_code not in [200, 201]:
                return {
                    'success': False,
                    'message': f'Status check failed: {response.text}'
                }
            
            cinoright_response = response.json()
            
            # Extract data from Cinoright response
            if not cinoright_response.get('status'):
                return {
                    'success': False,
                    'message': cinoright_response.get('message', 'Status check failed')
                }
            
            data = cinoright_response.get('data', {})
            
            # Extract status
            status = data.get('status', 'PENDING').upper()
            
            # Map status
            if status == 'SUCCESS':
                mapped_status = 'SUCCESS'
            elif status == 'FAILED':
                mapped_status = 'FAILED'
            else:
                mapped_status = 'INITIATED'
            
            # Extract other details
            txn_id = data.get('txn_id', '')
            reference = data.get('reference', '')
            amount = data.get('amount', 0)
            utr = data.get('utr', '')
            timestamp = data.get('timestamp', '')
            
            result = {
                'success': True,
                'status': mapped_status,
                'txn_id': txn_id,
                'reference': reference,
                'amount': amount,
                'utr': utr,
                'timestamp': timestamp,
                'message': cinoright_response.get('message', 'Status retrieved successfully')
            }
            
            print(f"Parsed Cinoright Status: {result}")
            
            return result
            
        except Exception as e:
            print(f"Check payout status error: {e}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'message': f'Status check error: {str(e)}'}
    
    def create_imps_payout(self, merchant_id, payout_data):
        """
        Create IMPS payout via Cinoright
        payout_data should contain:
        - account_number
        - ifsc_code
        - amount
        - beneficiary_name
        - email (optional)
        - phone (optional)
        - reference_id (optional)
        """
        try:
            conn = get_db_connection()
            if not conn:
                return {'success': False, 'message': 'Database connection failed'}
            
            with conn.cursor() as cursor:
                # Get merchant details
                cursor.execute("""
                    SELECT merchant_id, full_name, email, scheme_id, is_active
                    FROM merchants
                    WHERE merchant_id = %s
                """, (merchant_id,))
                
                merchant = cursor.fetchone()
                
                if not merchant:
                    return {'success': False, 'message': 'Merchant not found'}
                
                if not merchant['is_active']:
                    return {'success': False, 'message': 'Merchant account is inactive'}
                
                # Validate amount (minimum 100 as per Cinoright requirements)
                amount = float(payout_data.get('amount', 0))
                if amount < 100:
                    return {'success': False, 'message': 'Minimum payout amount is ₹100'}
                
                # Calculate charges
                charge_amount, net_amount, charge_type = self.calculate_charges(
                    amount, merchant['scheme_id'], 'PAYOUT'
                )
                
                if charge_amount is None:
                    return {'success': False, 'message': 'Failed to calculate charges'}
                
                # Total deduction from wallet = amount + charges
                total_deduction = amount + charge_amount
                
                # Check wallet balance
                cursor.execute("""
                    SELECT settled_balance FROM merchant_wallet WHERE merchant_id = %s
                """, (merchant_id,))
                
                wallet = cursor.fetchone()
                if not wallet or float(wallet['settled_balance']) < total_deduction:
                    return {'success': False, 'message': 'Insufficient wallet balance'}
                
                # Generate reference ID
                reference_id = payout_data.get('reference_id') or f"CINO{datetime.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:6].upper()}"
                
                # Call Cinoright API
                result = self.call_imps_payout_api(
                    account_number=payout_data.get('account_number'),
                    ifsc_code=payout_data.get('ifsc_code'),
                    reference_id=reference_id,
                    amount=amount,
                    beneficiary_name=payout_data.get('beneficiary_name'),
                    email=payout_data.get('email'),
                    phone=payout_data.get('phone')
                )
                
                if not result['success']:
                    return result
                
                # Extract status and transaction ID
                payout_status = result.get('status', 'INITIATED')
                cinoright_txn_id = result.get('cinoright_txn_id', '')
                utr = result.get('utr')
                
                print(f"Cinoright payout initiated - Status: {payout_status}, TxnID: {cinoright_txn_id}")
                
                # Deduct from wallet
                cursor.execute("""
                    UPDATE merchant_wallet
                    SET settled_balance = settled_balance - %s,
                        balance = balance - %s,
                        last_updated = NOW()
                    WHERE merchant_id = %s
                """, (total_deduction, total_deduction, merchant_id))
                
                # Get updated balance
                cursor.execute("""
                    SELECT settled_balance FROM merchant_wallet WHERE merchant_id = %s
                """, (merchant_id,))
                wallet = cursor.fetchone()
                balance_after = float(wallet['settled_balance'])
                balance_before = balance_after + total_deduction
                
                # Create wallet transaction for debit
                cursor.execute("""
                    INSERT INTO merchant_wallet_transactions
                    (merchant_id, txn_id, txn_type, amount, balance_before, balance_after, description, reference_id, created_at)
                    VALUES (%s, %s, 'DEBIT', %s, %s, %s, %s, %s, NOW())
                """, (
                    merchant_id,
                    reference_id,
                    total_deduction,
                    balance_before,
                    balance_after,
                    f'IMPS Payout to {payout_data.get("account_number")} (Amount: {amount}, Charges: {charge_amount})',
                    reference_id
                ))
                
                # Insert payout transaction record
                txn_id = f"TXN{uuid.uuid4().hex[:12].upper()}"
                order_id = f"ORD{datetime.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:8].upper()}"
                
                cursor.execute("""
                    INSERT INTO payout_transactions (
                        txn_id, reference_id, order_id, merchant_id, amount, charge_amount, charge_type,
                        net_amount, bene_name, account_no, ifsc_code, payment_type, 
                        pg_partner, pg_txn_id, status, created_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'IMPS', 'CINORIGHT', %s, %s, NOW()
                    )
                """, (
                    txn_id, reference_id, order_id, merchant_id, amount, charge_amount, charge_type,
                    net_amount, payout_data.get('beneficiary_name'),
                    payout_data.get('account_number'), payout_data.get('ifsc_code'),
                    cinoright_txn_id, payout_status
                ))
                
                # Update with UTR if available
                if utr and payout_status == 'SUCCESS':
                    cursor.execute("""
                        UPDATE payout_transactions
                        SET utr = %s, completed_at = NOW()
                        WHERE reference_id = %s
                    """, (utr, reference_id))
                
                conn.commit()
                
                return {
                    'success': True,
                    'txn_id': txn_id,
                    'reference_id': reference_id,
                    'amount': amount,
                    'charge_amount': charge_amount,
                    'total_deduction': total_deduction,
                    'status': payout_status,
                    'cinoright_txn_id': cinoright_txn_id,
                    'utr': utr,
                    'message': 'Payout initiated successfully'
                }
                
        except Exception as e:
            print(f"Create IMPS payout error: {e}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'message': f'Internal error: {str(e)}'}
        finally:
            if conn:
                conn.close()

# Create singleton instance
cinoright_service = CinorightService()
