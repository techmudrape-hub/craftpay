import re
import uuid

file_path = 'c:/Users/USER/Desktop/JAHARVIR INFINET/Orchpay/backend/payout_routes.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add import
if 'sectorpe_payout_service' not in content:
    content = content.replace(
        'from clockspay_payout_service import clockspay_payout_service',
        'from clockspay_payout_service import clockspay_payout_service\nfrom sectorpe_payout_service import sectorpe_payout_service'
    )

# 2. Update txn_id generation
txn_pattern = r"(elif pg_partner_upper in \['MAXPE', 'NODEPAY'\]:\s+txn_id = f\"MAXPE_TXN_\{uuid.uuid4\(\).hex\[:12\].upper\(\)\}\")"
sectorpe_txn = r"elif pg_partner_upper == 'SECTORPE':\n                    txn_id = f\"SECTORPE_TXN_{uuid.uuid4().hex[:12].upper()}\"\n                \1"
content = re.sub(txn_pattern, sectorpe_txn, content)


# 3. Add SectorPe blocks

# Admin Personal Payout (approx line 535)
admin_maxpe_pattern = r"(elif pg_partner_upper in \['MAXPE', 'NODEPAY'\]:\s+# Use MaxPe or NodePay for payout \(IMPS\) - Direct API call, NO wallet deduction)"
admin_sectorpe_block = """elif pg_partner_upper == 'SECTORPE':
                    # Use SectorPe for payout (IMPS) - Direct API call, NO wallet deduction
                    result = sectorpe_payout_service.call_payout_api(
                        account_number=bank['account_number'],
                        ifsc_code=bank['ifsc_code'],
                        bank_name=bank['bank_name'],
                        merchant_order_id=reference_id,
                        amount=float(data['amount']),
                        payee_name=bank['account_holder_name'],
                        email=email_address,
                        mobile=mobile_number,
                        mode='IMPS'
                    )
                    
                    if result['success']:
                        # NO WALLET DEDUCTION
                        status = result.get('status', 'INITIATED')
                        
                        print(f"SectorPe payout initiated - Status: {status}, Merchant Order ID: {reference_id}")
                        
                        if status in ['SUCCESS', 'FAILED']:
                            cursor.execute(\"\"\"
                                UPDATE payout_transactions 
                                SET status = %s, completed_at = NOW(), updated_at = NOW()
                                WHERE reference_id = %s
                            \"\"\", (status, reference_id))
                        else:
                            cursor.execute(\"\"\"
                                UPDATE payout_transactions 
                                SET status = %s, updated_at = NOW()
                                WHERE reference_id = %s
                            \"\"\", (status, reference_id))
                        
                        conn.commit()
                        
                        # Check status if INITIATED
                        if status == 'INITIATED':
                            print(f"Checking status from SectorPe for merchant_order_id: {reference_id}")
                            import time
                            time.sleep(2)
                            
                            status_result = sectorpe_payout_service.check_payout_status(reference_id)
                            if status_result.get('success'):
                                updated_status = status_result.get('status', 'INITIATED')
                                updated_utr = status_result.get('utr')
                                
                                print(f"SectorPe status check result - Status: {updated_status}, UTR: {updated_utr}")
                                
                                if updated_status in ['SUCCESS', 'FAILED']:
                                    cursor.execute(\"\"\"
                                        UPDATE payout_transactions 
                                        SET status = %s, utr = %s, completed_at = NOW(), updated_at = NOW()
                                        WHERE reference_id = %s
                                    \"\"\", (updated_status, updated_utr, reference_id))
                                else:
                                    cursor.execute(\"\"\"
                                        UPDATE payout_transactions 
                                        SET status = %s, utr = %s, updated_at = NOW()
                                        WHERE reference_id = %s
                                    \"\"\", (updated_status, updated_utr, reference_id))
                                
                                conn.commit()
                                status = updated_status
                        
                        return jsonify({
                            'success': True,
                            'message': 'Payout initiated successfully',
                            'txn_id': txn_id,
                            'reference_id': reference_id,
                            'status': status
                        }), 200
                    else:
                        cursor.execute(\"\"\"
                            UPDATE payout_transactions 
                            SET status = 'FAILED', error_message = %s, completed_at = NOW(), updated_at = NOW()
                            WHERE reference_id = %s
                        \"\"\", (result.get('message', 'Payout failed'), reference_id))
                        conn.commit()
                        
                        return jsonify({
                            'success': False,
                            'message': result.get('message', 'Payout failed')
                        }), 400
                
                \\1"""
content = re.sub(admin_maxpe_pattern, admin_sectorpe_block, content, count=1)


# Client Settle Fund (approx line 1309)
settle_maxpe_pattern = r"(elif pg_partner_upper in \['MAXPE', 'NODEPAY'\]:\s+# Use MaxPe or NodePay for payout \(IMPS\)\s+payout_service_instance = get_payout_service\(pg_partner_upper\))"
settle_sectorpe_block = """elif pg_partner_upper == 'SECTORPE':
                    # Use SectorPe for payout (IMPS)
                    sectorpe_result = sectorpe_payout_service.call_payout_api(
                        account_number=data['account_number'],
                        ifsc_code=data['ifsc_code'],
                        bank_name=data['bank_name'],
                        merchant_order_id=reference_id,
                        amount=net_amount,
                        payee_name=data['account_holder_name'],
                        email=merchant['email'],
                        mobile=merchant['mobile'],
                        mode='IMPS'
                    )

                    if sectorpe_result['success']:
                        status = sectorpe_result.get('status', 'INITIATED')

                        print(f"SectorPe payout initiated - Status: {status}, Merchant Order ID: {reference_id}")

                        if status == 'SUCCESS':
                            debit_result = wallet_svc.debit_unsettled_wallet(
                                merchant_id=merchant_id,
                                amount=total_deduction,
                                description=f"Settle Fund: ₹{amount:.2f} + Charges: ₹{charges['charge_amount']:.2f}",
                                reference_id=txn_id
                            )
                            
                            if not debit_result['success']:
                                cursor.execute(\"\"\"
                                    UPDATE payout_transactions
                                    SET status = 'FAILED', error_message = %s, completed_at = NOW(), updated_at = NOW()
                                    WHERE txn_id = %s
                                \"\"\", (f"Wallet deduction failed: {debit_result['message']}", txn_id))
                                conn.commit()
                                conn.close()
                                return jsonify({
                                    'success': False,
                                    'message': f"Payout succeeded but wallet deduction failed: {debit_result['message']}",
                                    'txn_id': txn_id
                                }), 500
                            
                            print(f"✅ UNSETTLED WALLET DEBITED - Balance: ₹{debit_result['balance_before']:.2f} → ₹{debit_result['balance_after']:.2f}")
                            
                            cursor.execute(\"\"\"
                                UPDATE payout_transactions
                                SET status = %s, completed_at = NOW(), updated_at = NOW()
                                WHERE txn_id = %s
                            \"\"\", (status, txn_id))
                        elif status == 'FAILED':
                            cursor.execute(\"\"\"
                                UPDATE payout_transactions
                                SET status = %s, completed_at = NOW(), updated_at = NOW()
                                WHERE txn_id = %s
                            \"\"\", (status, txn_id))
                        else:
                            cursor.execute(\"\"\"
                                UPDATE payout_transactions
                                SET status = %s, updated_at = NOW()
                                WHERE txn_id = %s
                            \"\"\", (status, txn_id))

                        conn.commit()
                        
                        if status == 'INITIATED':
                            print(f"Checking status from SectorPe for merchant_order_id: {reference_id}")
                            import time
                            time.sleep(2)
                            
                            status_result = sectorpe_payout_service.check_payout_status(reference_id)
                            if status_result.get('success'):
                                updated_status = status_result.get('status', 'INITIATED')
                                updated_utr = status_result.get('utr')
                                
                                print(f"SectorPe status check result - Status: {updated_status}, UTR: {updated_utr}")
                                
                                if updated_status == 'SUCCESS' and status != 'SUCCESS':
                                    debit_result = wallet_svc.debit_unsettled_wallet(
                                        merchant_id=merchant_id,
                                        amount=total_deduction,
                                        description=f"Settle Fund: ₹{amount:.2f} + Charges: ₹{charges['charge_amount']:.2f}",
                                        reference_id=txn_id
                                    )
                                    
                                    if debit_result['success']:
                                        print(f"✅ UNSETTLED WALLET DEBITED - Balance: ₹{debit_result['balance_before']:.2f} → ₹{debit_result['balance_after']:.2f}")
                                
                                if updated_status in ['SUCCESS', 'FAILED']:
                                    cursor.execute(\"\"\"
                                        UPDATE payout_transactions
                                        SET status = %s, utr = %s, completed_at = NOW(), updated_at = NOW()
                                        WHERE txn_id = %s
                                    \"\"\", (updated_status, updated_utr, txn_id))
                                else:
                                    cursor.execute(\"\"\"
                                        UPDATE payout_transactions
                                        SET status = %s, utr = %s, updated_at = NOW()
                                        WHERE txn_id = %s
                                    \"\"\", (updated_status, updated_utr, txn_id))
                                
                                conn.commit()
                                status = updated_status
                        
                        cursor.execute(\"\"\"
                            SELECT balance
                            FROM merchant_unsettled_wallet
                            WHERE merchant_id = %s
                        \"\"\", (merchant_id,))
                        current_wallet = cursor.fetchone()
                        current_balance = float(current_wallet['balance']) if current_wallet else 0.00
                        
                        conn.close()

                        return jsonify({
                            'success': True,
                            'message': 'Settle fund request processed successfully',
                            'txn_id': txn_id,
                            'reference_id': reference_id,
                            'requested_amount': amount,
                            'charges': charges['charge_amount'],
                            'total_to_deduct': total_deduction,
                            'amount_to_beneficiary': net_amount,
                            'status': status,
                            'unsettled_wallet_balance': current_balance,
                            'note': 'Wallet will be deducted when payout is successful' if status not in ['SUCCESS', 'FAILED'] else None
                        }), 200
                    else:
                        cursor.execute(\"\"\"
                            UPDATE payout_transactions
                            SET status = 'FAILED', error_message = %s, updated_at = NOW()
                            WHERE txn_id = %s
                        \"\"\", (sectorpe_result.get('message', 'SectorPe payout failed'), txn_id))
                        conn.commit()

                        conn.close()
                        return jsonify({
                            'success': False,
                            'message': 'Payout failed',
                            'txn_id': txn_id,
                            'error': sectorpe_result.get('message')
                        }), 400
                
                \\1"""
content = re.sub(settle_maxpe_pattern, settle_sectorpe_block, content, count=1)


# Client Direct Payout (approx line 2907)
direct_maxpe_pattern = r"(elif pg_partner_upper in \['MAXPE', 'NODEPAY'\]:\s+# Use MaxPe or NodePay for payout \(IMPS\)\s+# Get the appropriate service based on pg_partner\s+payout_service_instance = get_payout_service\(pg_partner_upper\))"
direct_sectorpe_block = """elif pg_partner_upper == 'SECTORPE':
                    # Use SectorPe for payout (IMPS)
                    sectorpe_result = sectorpe_payout_service.call_payout_api(
                        account_number=data['account_number'],
                        ifsc_code=data['ifsc_code'],
                        bank_name=data['bank_name'],
                        merchant_order_id=reference_id,
                        amount=net_amount_to_bank,
                        payee_name=data['account_holder_name'],
                        email=bene_email or 'merchant@orchpay.in',
                        mobile=bene_mobile or '9999999999',
                        mode='IMPS'
                    )

                    if sectorpe_result['success']:
                        status = sectorpe_result.get('status', 'INITIATED')

                        print(f"SectorPe payout initiated - Status: {status}, Merchant Order ID: {reference_id}")

                        if status == 'SUCCESS':
                            debit_result = wallet_svc.debit_merchant_wallet(
                                merchant_id=merchant_id,
                                amount=total_deduction,
                                description=f"Payout: ₹{amount:.2f} + Charges: ₹{charges['charge_amount']:.2f}",
                                reference_id=txn_id
                            )
                            
                            if not debit_result['success']:
                                cursor.execute(\"\"\"
                                    UPDATE payout_transactions
                                    SET status = 'FAILED', error_message = %s, completed_at = NOW(), updated_at = NOW()
                                    WHERE txn_id = %s
                                \"\"\", (f"Wallet deduction failed: {debit_result['message']}", txn_id))
                                conn.commit()
                                conn.close()
                                return jsonify({
                                    'success': False,
                                    'message': f"Payout succeeded but wallet deduction failed: {debit_result['message']}",
                                    'txn_id': txn_id
                                }), 500
                            
                            print(f"✅ WALLET DEBITED - Balance: ₹{debit_result['balance_before']:.2f} → ₹{debit_result['balance_after']:.2f}")
                            
                            cursor.execute(\"\"\"
                                UPDATE payout_transactions
                                SET status = %s, completed_at = NOW(), updated_at = NOW()
                                WHERE txn_id = %s
                            \"\"\", (status, txn_id))
                        elif status == 'FAILED':
                            cursor.execute(\"\"\"
                                UPDATE payout_transactions
                                SET status = %s, completed_at = NOW(), updated_at = NOW()
                                WHERE txn_id = %s
                            \"\"\", (status, txn_id))
                        else:
                            cursor.execute(\"\"\"
                                UPDATE payout_transactions
                                SET status = %s, updated_at = NOW()
                                WHERE txn_id = %s
                            \"\"\", (status, txn_id))

                        conn.commit()
                        
                        if status == 'INITIATED':
                            print(f"Checking status from SectorPe for merchant_order_id: {reference_id}")
                            import time
                            time.sleep(2)
                            
                            status_result = sectorpe_payout_service.check_payout_status(reference_id)
                            if status_result.get('success'):
                                updated_status = status_result.get('status', 'INITIATED')
                                updated_utr = status_result.get('utr')
                                
                                print(f"SectorPe status check result - Status: {updated_status}, UTR: {updated_utr}")
                                
                                if updated_status == 'SUCCESS' and status != 'SUCCESS':
                                    debit_result = wallet_svc.debit_merchant_wallet(
                                        merchant_id=merchant_id,
                                        amount=total_deduction,
                                        description=f"Payout: ₹{amount:.2f} + Charges: ₹{charges['charge_amount']:.2f}",
                                        reference_id=txn_id
                                    )
                                    
                                    if debit_result['success']:
                                        print(f"✅ WALLET DEBITED - Balance: ₹{debit_result['balance_before']:.2f} → ₹{debit_result['balance_after']:.2f}")
                                
                                if updated_status in ['SUCCESS', 'FAILED']:
                                    cursor.execute(\"\"\"
                                        UPDATE payout_transactions
                                        SET status = %s, utr = %s, completed_at = NOW(), updated_at = NOW()
                                        WHERE txn_id = %s
                                    \"\"\", (updated_status, updated_utr, txn_id))
                                else:
                                    cursor.execute(\"\"\"
                                        UPDATE payout_transactions
                                        SET status = %s, utr = %s, updated_at = NOW()
                                        WHERE txn_id = %s
                                    \"\"\", (updated_status, updated_utr, txn_id))
                                
                                conn.commit()
                                status = updated_status
                        
                        cursor.execute(\"\"\"
                            SELECT settled_balance, unsettled_balance
                            FROM merchant_wallet
                            WHERE merchant_id = %s
                        \"\"\", (merchant_id,))
                        current_wallet = cursor.fetchone()
                        current_balance = float(current_wallet['settled_balance']) if current_wallet else 0.00
                        
                        conn.close()

                        return jsonify({
                            'success': True,
                            'message': 'Payout initiated successfully' if status != 'SUCCESS' else 'Payout completed successfully',
                            'txn_id': txn_id,
                            'reference_id': reference_id,
                            'order_id': data['order_id'],
                            'requested_amount': amount,
                            'charges': charges['charge_amount'],
                            'total_to_deduct': total_deduction,
                            'amount_to_beneficiary': net_amount_to_bank,
                            'status': status,
                            'wallet_balance': current_balance,
                            'note': 'Wallet will be deducted when payout is successful' if status not in ['SUCCESS', 'FAILED'] else None,
                            'beneficiary': {
                                'name': data['account_holder_name'],
                                'account_number': data['account_number'],
                                'ifsc_code': data['ifsc_code'],
                                'bank_name': data['bank_name']
                            }
                        }), 200
                    else:
                        cursor.execute(\"\"\"
                            UPDATE payout_transactions
                            SET status = 'FAILED', error_message = %s, updated_at = NOW()
                            WHERE txn_id = %s
                        \"\"\", (sectorpe_result.get('message', 'SectorPe payout failed'), txn_id))
                        conn.commit()

                        conn.close()
                        return jsonify({
                            'success': False,
                            'message': 'Payout failed',
                            'txn_id': txn_id,
                            'error': sectorpe_result.get('message')
                        }), 400
                
                \\1"""
content = re.sub(direct_maxpe_pattern, direct_sectorpe_block, content, count=1)

with open('c:/Users/USER/Desktop/JAHARVIR INFINET/Orchpay/backend/payout_routes.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Update script finished successfully.')
