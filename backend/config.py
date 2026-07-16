import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Database Configuration
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_USER = os.getenv('DB_USER', 'root')
    DB_PASSWORD = os.getenv('DB_PASSWORD', '')
    DB_NAME = os.getenv('DB_NAME', 'moneyone_db')
    
    # JWT Configuration
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'your-super-secret-jwt-key')
    JWT_ACCESS_TOKEN_EXPIRES = 3600  # 1 hour (longer than 15 min session timeout)
    
    # PayU Configuration
    PAYU_MERCHANT_KEY = os.getenv('PAYU_MERCHANT_KEY', '')
    PAYU_MERCHANT_SALT = os.getenv('PAYU_MERCHANT_SALT', '')
    PAYU_BASE_URL = os.getenv('PAYU_BASE_URL', 'https://secure.payu.in')
    PAYU_TEST_MODE = os.getenv('PAYU_TEST_MODE', 'True') == 'True'
    
    # PayU Legal Halt Configuration
    PAYU_LEGALHALT_MERCHANT_KEY = os.getenv('PAYU_LEGALHALT_MERCHANT_KEY', '')
    PAYU_LEGALHALT_MERCHANT_SALT = os.getenv('PAYU_LEGALHALT_MERCHANT_SALT', '')
    PAYU_LEGALHALT_BASE_URL = os.getenv('PAYU_LEGALHALT_BASE_URL', 'https://secure.payu.in')
    PAYU_LEGALHALT_TEST_MODE = os.getenv('PAYU_LEGALHALT_TEST_MODE', 'True') == 'True'
    
    # PayU Payout Configuration
    PAYU_PAYOUT_CLIENT_ID = os.getenv('PAYU_PAYOUT_CLIENT_ID', '')
    PAYU_PAYOUT_USERNAME = os.getenv('PAYU_PAYOUT_USERNAME', '')
    PAYU_PAYOUT_PASSWORD = os.getenv('PAYU_PAYOUT_PASSWORD', '')
    PAYU_PAYOUT_MERCHANT_ID = os.getenv('PAYU_PAYOUT_MERCHANT_ID', '')
    PAYU_PAYOUT_BASE_URL = os.getenv('PAYU_PAYOUT_BASE_URL', 'https://uatoneapi.payu.in')
    PAYU_PAYOUT_AUTH_URL = os.getenv('PAYU_PAYOUT_AUTH_URL', 'https://uat-accounts.payu.in')
    
    # Mudrape Configuration
    MUDRAPE_BASE_URL = os.getenv('MUDRAPE_BASE_URL', 'https://agentmudrape.com')
    MUDRAPE_API_KEY = os.getenv('MUDRAPE_API_KEY', 'pk_2580642bf7f031983a0390755ee52b9e')
    MUDRAPE_API_SECRET = os.getenv('MUDRAPE_API_SECRET', 'sk_af9c19bef57d63c100b01b174258ee3693761a6bb679d1676b6930dcb4985688')
    MUDRAPE_USER_ID = os.getenv('MUDRAPE_USER_ID', 'cmlujaiqv00tw01s6up9o7376')
    MUDRAPE_MERCHANT_MID = os.getenv('MUDRAPE_MERCHANT_MID', '')
    MUDRAPE_MERCHANT_EMAIL = os.getenv('MUDRAPE_MERCHANT_EMAIL', '')
    MUDRAPE_MERCHANT_SECRET = os.getenv('MUDRAPE_MERCHANT_SECRET', '')
    
    # Tourquest Configuration
    TOURQUEST_BASE_URL = os.getenv('TOURQUEST_BASE_URL', 'https://payment.tourquest.travel')
    TOURQUEST_SECRET_KEY = os.getenv('TOURQUEST_SECRET_KEY', '0DV7E5Zdw4WbEsGrfdsbEVQnJHNqttRc')
    TOURQUEST_SALT_KEY = os.getenv('TOURQUEST_SALT_KEY', 'iVsDOCf77pZWpfyyjbTjRbqlQobp34buQkfwEB4ab')
    
    # PayTouch Configuration
    PAYTOUCH_BASE_URL = os.getenv('PAYTOUCH_BASE_URL', 'https://dashboard.shreefintechsolutions.com')
    PAYTOUCH_TOKEN = os.getenv('PAYTOUCH_TOKEN', 'ON2gMaaJaIJG2HIyE3I7M9EwnmeKvE')
    
    # PayTouch2 Configuration (New Integration with Different Keys)
    PAYTOUCH2_BASE_URL = os.getenv('PAYTOUCH2_BASE_URL', 'https://dashboard.shreefintechsolutions.com')
    PAYTOUCH2_TOKEN = os.getenv('PAYTOUCH2_TOKEN', 'NEW_TOKEN_FROM_PAYTOUCH_DASHBOARD')
    
    # Airpay Configuration
    AIRPAY_BASE_URL = os.getenv('AIRPAY_BASE_URL', 'https://kraken.airpay.co.in')
    AIRPAY_CLIENT_ID = os.getenv('AIRPAY_CLIENT_ID', '')
    AIRPAY_CLIENT_SECRET = os.getenv('AIRPAY_CLIENT_SECRET', '')
    AIRPAY_MERCHANT_ID = os.getenv('AIRPAY_MERCHANT_ID', '')
    AIRPAY_USERNAME = os.getenv('AIRPAY_USERNAME', '')
    AIRPAY_PASSWORD = os.getenv('AIRPAY_PASSWORD', '')
    AIRPAY_ENCRYPTION_KEY = os.getenv('AIRPAY_ENCRYPTION_KEY', '')
    AIRPAY_SECRET = os.getenv('AIRPAY_SECRET', os.getenv('AIRPAY_CLIENT_SECRET', ''))  # Default to client_secret if not provided
    
    # Paytouchpayin Configuration (QR PAYIN API - Updated 2026)
    PAYTOUCHPAYIN_BASE_URL = os.getenv('PAYTOUCHPAYIN_BASE_URL', 'https://dashboard.shreefintechsolutions.com')
    PAYTOUCHPAYIN_TOKEN = os.getenv('PAYTOUCHPAYIN_TOKEN', 'izrfvcnddMzlf5B142yDH4PDkkoDUMPP')
    
    # SkrillPe Configuration
    SKRILLPE_BASE_URL = os.getenv('SKRILLPE_BASE_URL', 'https://clientapisrv.skrillpe.com/poutsaps')
    SKRILLPE_MID = os.getenv('SKRILLPE_MID', 'TESTCOMPANY')  # Merchant ID
    SKRILLPE_MOBILE_NUMBER = os.getenv('SKRILLPE_MOBILE_NUMBER', '7376582857')
    SKRILLPE_MPIN = os.getenv('SKRILLPE_MPIN', '28619924')
    SKRILLPE_API_KEY = os.getenv('SKRILLPE_API_KEY', 'F8D12F51-1732-4787-B8DD-7858A41E396F')
    SKRILLPE_API_PASSWORD = os.getenv('SKRILLPE_API_PASSWORD', '8DB03D51BB9A4CFDB8F35B1E7572433A')
    SKRILLPE_COMPANY_ALIAS = os.getenv('SKRILLPE_COMPANY_ALIAS', 'TESTCOMPANY')
    SKRILLPE_VPA = os.getenv('SKRILLPE_VPA', 'skrillpe@idfcbank')
    
    # Rang Configuration
    RANG_BASE_URL = os.getenv('RANG_BASE_URL', 'https://api.rangriwaz.in')
    RANG_SECRET_KEY = os.getenv('RANG_SECRET_KEY', 'OJYMJ8M3B9SV18DK')
    RANG_MID = os.getenv('RANG_MID', 'APIPA100015')
    RANG_EMAIL = os.getenv('RANG_EMAIL', 'indrajeet@mudrape.com')
    
    # VIYONAPAY Configuration
    VIYONAPAY_BASE_URL = os.getenv('VIYONAPAY_BASE_URL', 'https://core.viyonapay.com')
    VIYONAPAY_CLIENT_ID = os.getenv('VIYONAPAY_CLIENT_ID', '')
    VIYONAPAY_CLIENT_SECRET = os.getenv('VIYONAPAY_CLIENT_SECRET', '')
    VIYONAPAY_API_KEY = os.getenv('VIYONAPAY_API_KEY', '')
    VIYONAPAY_VPA = os.getenv('VIYONAPAY_VPA', 'vfipl.188690284791@kvb')
    VIYONAPAY_CLIENT_PRIVATE_KEY_PATH = os.getenv('VIYONAPAY_CLIENT_PRIVATE_KEY_PATH', 'keys/viyonapay_client_private.pem')
    VIYONAPAY_SERVER_PUBLIC_KEY_PATH = os.getenv('VIYONAPAY_SERVER_PUBLIC_KEY_PATH', 'keys/viyonapay_server_public.pem')
    VIYONAPAY_WEBHOOK_SECRET_KEY = os.getenv('VIYONAPAY_WEBHOOK_SECRET_KEY', '')  # 16-byte hex key for webhook decryption
    
    # VIYONAPAY Barringer Configuration
    VIYONAPAY_BARRINGER_CLIENT_ID = os.getenv('VIYONAPAY_BARRINGER_CLIENT_ID', '')
    VIYONAPAY_BARRINGER_CLIENT_SECRET = os.getenv('VIYONAPAY_BARRINGER_CLIENT_SECRET', '')
    VIYONAPAY_BARRINGER_API_KEY = os.getenv('VIYONAPAY_BARRINGER_API_KEY', '')
    VIYONAPAY_BARRINGER_VPA = os.getenv('VIYONAPAY_BARRINGER_VPA', '')
    VIYONAPAY_BARRINGER_CLIENT_PRIVATE_KEY_PATH = os.getenv('VIYONAPAY_BARRINGER_CLIENT_PRIVATE_KEY_PATH', 'keys/viyonapay_barringer_client_private.pem')
    VIYONAPAY_BARRINGER_SERVER_PUBLIC_KEY_PATH = os.getenv('VIYONAPAY_BARRINGER_SERVER_PUBLIC_KEY_PATH', 'keys/viyonapay_barringer_server_public.pem')
    VIYONAPAY_BARRINGER_WEBHOOK_SECRET_KEY = os.getenv('VIYONAPAY_BARRINGER_WEBHOOK_SECRET_KEY', os.getenv('VIYONAPAY_WEBHOOK_SECRET_KEY', ''))  # Falls back to Truaxis key if not set
    
    # MoneyOne Configuration
    MONEYONE_BASE_URL = os.getenv('MONEYONE_BASE_URL', 'https://api.moneyone.co.in')
    MONEYONE_MERCHANT_ID = os.getenv('MONEYONE_MERCHANT_ID', '8130055250')
    MONEYONE_PASSWORD = os.getenv('MONEYONE_PASSWORD', 'Test@123')
    MONEYONE_AUTH_KEY = os.getenv('MONEYONE_AUTH_KEY', 'mk_live_d17a85c063152927fa811fae8ca24060ba3f7d7cb41cec8414bdb094')
    MONEYONE_MODULE_SECRET = os.getenv('MONEYONE_MODULE_SECRET', 'sk_live_defcd75d8fa3cca0848d53d2')
    MONEYONE_AES_KEY = os.getenv('MONEYONE_AES_KEY', 'b42260dcddd3526d8aa448add2')
    MONEYONE_AES_IV = os.getenv('MONEYONE_AES_IV', 'OO921a_PC6E50NA5')
    
    # InstantPesa Configuration
    INSTANTPESA_BASE_URL = os.getenv('INSTANTPESA_BASE_URL', 'https://instantpesa.com')
    INSTANTPESA_TOKEN = os.getenv('INSTANTPESA_TOKEN', '')
    
    # Cinoright Configuration
    CINORIGHT_BASE_URL = os.getenv('CINORIGHT_BASE_URL', 'https://crm.cinoright.com')
    CINORIGHT_API_KEY = os.getenv('CINORIGHT_API_KEY', '')
    CINORIGHT_SECRET_KEY = os.getenv('CINORIGHT_SECRET_KEY', '')
    CINORIGHT_USER_ID = os.getenv('CINORIGHT_USER_ID', '')
    
    # Maxpe Configuration
    MAXPE_BASE_URL = os.getenv('MAXPE_BASE_URL', 'https://merchant.maxpe.tech')
    MAXPE_API_KEY = os.getenv('MAXPE_API_KEY', 'LJvMg0aYcOfwXlWFjy')
    MAXPE_API_SECRET = os.getenv('MAXPE_API_SECRET', '7PcBEkfgJUsVmqQAeXaCjGlhHMOnwD5rRIzvS6WY89tpF')
    
    # Nextpay Configuration
    NEXTPAY_BASE_URL = os.getenv('NEXTPAY_BASE_URL', 'https://nextpey.in')
    NEXTPAY_CLIENT_ID = os.getenv('NEXTPAY_CLIENT_ID', '')
    NEXTPAY_API_SECRET = os.getenv('NEXTPAY_API_SECRET', '')

    
    # NodePay Configuration (uses same integration as MaxPe but different credentials)
    NODEPAY_BASE_URL = os.getenv('NODEPAY_BASE_URL', 'https://merchant.nodepay.in')
    NODEPAY_API_KEY = os.getenv('NODEPAY_API_KEY', '')
    NODEPAY_API_SECRET = os.getenv('NODEPAY_API_SECRET', '')
    
    # Razorpay Configuration
    RAZORPAY_BASE_URL = os.getenv('RAZORPAY_BASE_URL', 'https://api.razorpay.com')
    RAZORPAY_KEY_ID = os.getenv('RAZORPAY_KEY_ID', '')
    RAZORPAY_KEY_SECRET = os.getenv('RAZORPAY_KEY_SECRET', '')
    
    # Paytm Configuration
    PAYTM_BASE_URL = os.getenv('PAYTM_BASE_URL', 'https://securestage.paytmpayments.com')  # Use https://secure.paytm.in for production
    PAYTM_MERCHANT_ID = os.getenv('PAYTM_MERCHANT_ID', 'wOXLNq62001505667648')
    PAYTM_MERCHANT_KEY = os.getenv('PAYTM_MERCHANT_KEY', '')  # Merchant key for checksum generation
    
    # ClocksPay Configuration
    CLOCKSPAY_BASE_URL = os.getenv('CLOCKSPAY_BASE_URL', 'https://crm.clockspay.com')
    CLOCKSPAY_TOKEN = os.getenv('CLOCKSPAY_TOKEN', '')
    
    # Risexpay Configuration
    RISEXPAY_BASE_URL = os.getenv('RISEXPAY_BASE_URL', 'https://risexpay.in')
    RISEXPAY_MID = os.getenv('RISEXPAY_MID', '')  # Merchant ID provided by Risexpay
    RISEXPAY_API_KEY = os.getenv('RISEXPAY_API_KEY', '')  # API authentication key
    RISEXPAY_SECRET_KEY = os.getenv('RISEXPAY_SECRET_KEY', '')  # Payin Secret Key for HMAC-SHA256 signing
    RISEXPAY_PAYOUT_SECRET_KEY = os.getenv('RISEXPAY_PAYOUT_SECRET_KEY', '')  # Payout Secret Key (generate from dashboard)
    
    # RockyPayz Configuration
    ROCKYPAYZ_BASE_URL = os.getenv('ROCKYPAYZ_BASE_URL', 'https://api.rockypayz.shop')
    ROCKYPAYZ_MID = os.getenv('ROCKYPAYZ_MID', '')
    ROCKYPAYZ_API_KEY = os.getenv('ROCKYPAYZ_API_KEY', '')
    ROCKYPAYZ_ROUTE = int(os.getenv('ROCKYPAYZ_ROUTE', '1'))  # Route for payout (typically 1)

    # SectorPe Configuration
    SECTORPE_BASE_URL = os.getenv('SECTORPE_BASE_URL', 'https://banking.sectorpe.com')
    SECTORPE_TOKEN = os.getenv('SECTORPE_TOKEN', '')

    # Alopna Configuration
    ALOPNA_PAYIN_BASE_URL = os.getenv('ALOPNA_PAYIN_BASE_URL', 'https://alopna.com/api')
    ALOPNA_PAYOUT_BASE_URL = os.getenv('ALOPNA_PAYOUT_BASE_URL', 'https://partner.alopna.in/api')
    ALOPNA_PAYIN_TOKEN = os.getenv('ALOPNA_PAYIN_TOKEN', '')
    ALOPNA_CLIENT_ID = os.getenv('ALOPNA_CLIENT_ID', '')
    ALOPNA_CLIENT_SECRET = os.getenv('ALOPNA_CLIENT_SECRET', '')

    # Acceptpay Configuration
    ACCEPTPAY_BASE_URL = os.getenv('ACCEPTPAY_BASE_URL', 'https://acceptpayfrontend.vercel.app')
    ACCEPTPAY_TOKEN = os.getenv('ACCEPTPAY_TOKEN', '')
    ACCEPTPAY_WEBHOOK_SECRET = os.getenv('ACCEPTPAY_WEBHOOK_SECRET', '')
    ACCEPTPAY_MERCHANT_ID = os.getenv('ACCEPTPAY_MERCHANT_ID', '')

    # OQPay Configuration
    OQPAY_PAYIN_BASE_URL = os.getenv('OQPAY_PAYIN_BASE_URL', 'https://payin.oqpay.co.in')
    OQPAY_PAYOUT_BASE_URL = os.getenv('OQPAY_PAYOUT_BASE_URL', 'https://payout.oqpay.co.in')
    OQPAY_REGISTRATION_ID = os.getenv('OQPAY_REGISTRATION_ID', 'OQP-XXXX')

    # Tpipay Configuration
    TPIPAY_BASE_URL = os.getenv('TPIPAY_BASE_URL', 'https://banking.mytpipay.com')
    TPIPAY_API_TOKEN = os.getenv('TPIPAY_API_TOKEN', '')

    # MakeMyPayment Configuration
    MAKEMYPAYMENT_BASE_URL = os.getenv('MAKEMYPAYMENT_BASE_URL', 'https://makemypayment.in')
    MAKEMYPAYMENT_API_KEY = os.getenv('MAKEMYPAYMENT_API_KEY', '')
    MAKEMYPAYMENT_API_SECRET = os.getenv('MAKEMYPAYMENT_API_SECRET', '')
    MAKEMYPAYMENT_WEBHOOK_SECRET = os.getenv('MAKEMYPAYMENT_WEBHOOK_SECRET', '')

    # Titanexam Configuration
    TITANEXAM_BASE_URL = os.getenv('TITANEXAM_BASE_URL', 'https://api.titanexam.online')
    TITANEXAM_MERCHANT_ID = os.getenv('TITANEXAM_MERCHANT_ID', '')
    TITANEXAM_SECRET_KEY = os.getenv('TITANEXAM_SECRET_KEY', '')

    # ORO Configuration
    ORO_BASE_URL = os.getenv('ORO_BASE_URL', 'http://oroitsolution.info/api')
    ORO_CLIENT_ID = os.getenv('ORO_CLIENT_ID', '')
    ORO_SECRET_ID = os.getenv('ORO_SECRET_ID', '')

    # SMTP Email Configuration
    SMTP_HOST = os.getenv('SMTP_HOST', 'smtp.gmail.com')
    SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
    SMTP_USERNAME = os.getenv('SMTP_USERNAME', '')
    SMTP_PASSWORD = os.getenv('SMTP_PASSWORD', '')
    SMTP_FROM_EMAIL = os.getenv('SMTP_FROM_EMAIL', 'noreply@moneyone.co.in')
    SMTP_FROM_NAME = os.getenv('SMTP_FROM_NAME', 'MoneyOne')
    SMTP_USE_TLS = os.getenv('SMTP_USE_TLS', 'True') == 'True'
    
    # CORS Configuration
    CORS_ORIGINS = os.getenv('CORS_ORIGINS', 'http://localhost:5173,http://localhost:5174').split(',')
    CORS_ALLOW_CREDENTIALS = os.getenv('CORS_ALLOW_CREDENTIALS', 'True') == 'True'
    
    # Uploads Configuration
    UPLOADS_BASE_URL = os.getenv('UPLOADS_BASE_URL', 'http://localhost:5000/uploads')
    UPLOADS_FOLDER = os.getenv('UPLOADS_FOLDER', 'uploads')
    MAX_UPLOAD_SIZE = int(os.getenv('MAX_UPLOAD_SIZE', '5242880'))  # 5MB default
    ALLOWED_EXTENSIONS = os.getenv('ALLOWED_EXTENSIONS', 'jpg,jpeg,png,pdf').split(',')
