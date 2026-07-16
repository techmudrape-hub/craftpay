import re

file_path = "c:/Users/USER/Desktop/JAHARVIR INFINET/Orchpay/backend/payout_routes.py"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Add import
if "makemypayment_payout_service" not in content:
    content = content.replace(
        "from tpipay_payout_service import tpipay_payout_service",
        "from tpipay_payout_service import tpipay_payout_service\nfrom makemypayment_payout_service import makemypayment_payout_service"
    )

# 2. Add txn_id prefix logic (occurs in multiple places)
txn_id_str = """                elif pg_partner_upper == 'TPIPAY':
                    txn_id = f"TPI_TXN_{uuid.uuid4().hex[:12].upper()}"
"""
txn_id_repl = """                elif pg_partner_upper == 'TPIPAY':
                    txn_id = f"TPI_TXN_{uuid.uuid4().hex[:12].upper()}"
                elif pg_partner_upper == 'MAKEMYPAYMENT':
                    txn_id = f"MMP_TXN_{uuid.uuid4().hex[:12].upper()}"
"""
content = content.replace(txn_id_str, txn_id_repl)

# 3. Add admin_personal_payout logic
# We find where TPIPAY logic starts for admin_personal_payout
admin_tpipay_logic = """                elif pg_partner_upper == 'TPIPAY':
                    # Use Tpipay for payout (IMPS/NEFT) - Direct API call, NO wallet deduction
                    result = tpipay_payout_service.call_payout_api(
                        account_number=bank['account_number'],
                        ifsc_code=bank['ifsc_code'],
                        bank_name=bank['bank_name'],
                        merchant_order_id=reference_id,
                        amount=float(data['amount']),
                        payee_name=bank['account_holder_name'],
                        email=email_address,
                        mobile=mobile_number,
                        channel_id='2'  # 2 = IMPS
                    )
                    
                    if result['success']:
                        # NO WALLET DEDUCTION
                        status = result.get('status', 'INITIATED')
                        payid = result.get('payid', '')
                        utr = result.get('utr', '')
                        
                        print(f"Tpipay payout initiated - Status: {status}, Merchant Order ID: {reference_id}, PayID: {payid}")
                        
                        if status in ['SUCCESS', 'FAILED']:
                            cursor.execute(\"\"\"
                                UPDATE payout_transactions 
                                SET status = %s, pg_txn_id = %s, utr = %s, completed_at = NOW(), updated_at = NOW()
                                WHERE reference_id = %s
                            \"\"\", (status, payid, utr, reference_id))
                        else:
                            cursor.execute(\"\"\"
                                UPDATE payout_transactions 
                                SET status = %s, pg_txn_id = %s, utr = %s, updated_at = NOW()
                                WHERE reference_id = %s
                            \"\"\", (status, payid, utr, reference_id))
                        
                        conn.commit()
                        
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
                        }), 400"""

admin_makemypayment_logic = admin_tpipay_logic + """
                
                elif pg_partner_upper == 'MAKEMYPAYMENT':
                    result = makemypayment_payout_service.initiate_single_payout(
                        merchant_reference_id=reference_id,
                        account_holder=bank['account_holder_name'],
                        account_number=bank['account_number'],
                        ifsc_code=bank['ifsc_code'],
                        bank_name=bank['bank_name'],
                        mobile=mobile_number,
                        amount=str(float(data['amount'])),
                        mode='imps',
                        purpose='Payment',
                        email=email_address
                    )
                    
                    if result['success']:
                        status = result.get('status', 'INITIATED')
                        mmp_txn_id = result.get('transaction_id', '')
                        
                        print(f"MakeMyPayment payout initiated - Status: {status}, TxnID: {mmp_txn_id}")
                        
                        if status in ['SUCCESS', 'FAILED']:
                            cursor.execute(\"\"\"
                                UPDATE payout_transactions 
                                SET status = %s, pg_txn_id = %s, completed_at = NOW(), updated_at = NOW()
                                WHERE reference_id = %s
                            \"\"\", (status, mmp_txn_id, reference_id))
                        else:
                            cursor.execute(\"\"\"
                                UPDATE payout_transactions 
                                SET status = %s, pg_txn_id = %s, updated_at = NOW()
                                WHERE reference_id = %s
                            \"\"\", (status, mmp_txn_id, reference_id))
                        conn.commit()
                        
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
                        return jsonify({'success': False, 'message': result.get('message', 'Payout failed')}), 400"""

content = content.replace(admin_tpipay_logic, admin_makemypayment_logic)

# 4. Add client_direct_payout logic
client_tpipay_logic = """                elif pg_partner_upper == 'TPIPAY':
                    # Use Tpipay for payout (IMPS/NEFT)
                    tpipay_result = tpipay_payout_service.call_payout_api(
                        account_number=data['account_number'],
                        ifsc_code=data['ifsc_code'],
                        bank_name=data['bank_name'],
                        merchant_order_id=reference_id,
                        amount=net_amount_to_bank,
                        payee_name=data['account_holder_name'],
                        email=bene_email or 'merchant@orchpay.in',
                        mobile=bene_mobile or '9999999999',
                        channel_id='2'  # 2 = IMPS
                    )

                    if tpipay_result['success']:
                        status = tpipay_result.get('status', 'INITIATED')
                        payid = tpipay_result.get('payid', '')
                        utr = tpipay_result.get('utr', '')

                        print(f"Tpipay payout initiated - Status: {status}, Merchant Order ID: {reference_id}, PayID: {payid}")

                        # Deduct wallet ONLY if status is SUCCESS (pending goes via callback)
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

                            print(f"✅ WALLET DEBITED - Balance: ₹{debit_result['balance_before']:.2f} ➡️ ₹{debit_result['balance_after']:.2f}")
                            cursor.execute(\"\"\"
                                UPDATE payout_transactions
                                SET status = %s, pg_txn_id = %s, utr = %s, completed_at = NOW(), updated_at = NOW()
                                WHERE txn_id = %s
                            \"\"\", (status, payid, utr, txn_id))
                        elif status == 'FAILED':
                            cursor.execute(\"\"\"
                                UPDATE payout_transactions
                                SET status = %s, pg_txn_id = %s, utr = %s, completed_at = NOW(), updated_at = NOW()
                                WHERE txn_id = %s
                            \"\"\", (status, payid, utr, txn_id))
                        else:
                            cursor.execute(\"\"\"
                                UPDATE payout_transactions
                                SET status = %s, pg_txn_id = %s, utr = %s, updated_at = NOW()
                                WHERE txn_id = %s
                            \"\"\", (status, payid, utr, txn_id))

                        conn.commit()
                        
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
                            WHERE txn_id = %s
                        \"\"\", (tpipay_result.get('message', 'Payout failed'), txn_id))
                        conn.commit()
                        
                        return jsonify({
                            'success': False,
                            'message': tpipay_result.get('message', 'Payout failed')
                        }), 400"""

client_makemypayment_logic = client_tpipay_logic + """
                
                elif pg_partner_upper == 'MAKEMYPAYMENT':
                    mmp_result = makemypayment_payout_service.initiate_single_payout(
                        merchant_reference_id=reference_id,
                        account_holder=data['account_holder_name'],
                        account_number=data['account_number'],
                        ifsc_code=data['ifsc_code'],
                        bank_name=data['bank_name'],
                        mobile=bene_mobile or '9999999999',
                        amount=str(net_amount_to_bank),
                        mode=payment_type,
                        purpose=purpose,
                        email=bene_email or 'merchant@orchpay.in'
                    )

                    if mmp_result['success']:
                        status = mmp_result.get('status', 'INITIATED')
                        mmp_txn_id = mmp_result.get('transaction_id', '')

                        print(f"MakeMyPayment payout initiated - Status: {status}, Merchant Order ID: {reference_id}, TxnID: {mmp_txn_id}")

                        # Deduct wallet ONLY if status is SUCCESS (pending goes via callback)
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

                            print(f"✅ WALLET DEBITED - Balance: ₹{debit_result['balance_before']:.2f} ➡️ ₹{debit_result['balance_after']:.2f}")
                            cursor.execute(\"\"\"
                                UPDATE payout_transactions
                                SET status = %s, pg_txn_id = %s, completed_at = NOW(), updated_at = NOW()
                                WHERE txn_id = %s
                            \"\"\", (status, mmp_txn_id, txn_id))
                        elif status == 'FAILED':
                            cursor.execute(\"\"\"
                                UPDATE payout_transactions
                                SET status = %s, pg_txn_id = %s, completed_at = NOW(), updated_at = NOW()
                                WHERE txn_id = %s
                            \"\"\", (status, mmp_txn_id, txn_id))
                        else:
                            cursor.execute(\"\"\"
                                UPDATE payout_transactions
                                SET status = %s, pg_txn_id = %s, updated_at = NOW()
                                WHERE txn_id = %s
                            \"\"\", (status, mmp_txn_id, txn_id))

                        conn.commit()
                        
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
                            WHERE txn_id = %s
                        \"\"\", (mmp_result.get('message', 'Payout failed'), txn_id))
                        conn.commit()
                        
                        return jsonify({
                            'success': False,
                            'message': mmp_result.get('message', 'Payout failed')
                        }), 400"""

content = content.replace(client_tpipay_logic, client_makemypayment_logic)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)
print("Updated payout_routes.py successfully!")
