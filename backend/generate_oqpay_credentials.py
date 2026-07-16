import os
import sys
import hashlib
import hmac
import base64
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

def generate_sha256_secret(registration_id):
    sha256 = hashlib.sha256()
    sha256.update(registration_id.encode('utf-8'))
    hash_bytes = sha256.digest()
    return base64.b64encode(hash_bytes).decode('utf-8')

def generate_client_secret(registration_id):
    secret_key = generate_sha256_secret(registration_id)
    h = hmac.new(
        secret_key.encode('utf-8'),
        registration_id.encode('utf-8'),
        hashlib.sha256
    )
    hash_bytes = h.digest()
    return base64.b64encode(hash_bytes).decode('utf-8')

def generate_rsa_keypair(keys_dir):
    os.makedirs(keys_dir, exist_ok=True)
    
    # Generate private key
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048
    )
    
    # Serialize private key to PEM
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    
    # Serialize public key to PEM
    public_key = private_key.public_key()
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    
    # Write to files
    private_path = os.path.join(keys_dir, 'oqpay_private.pem')
    public_path = os.path.join(keys_dir, 'oqpay_public.pem')
    
    with open(private_path, 'wb') as f:
        f.write(private_pem)
        
    with open(public_path, 'wb') as f:
        f.write(public_pem)
        
    return private_path, public_path, public_pem.decode('utf-8')

def main():
    reg_id = sys.argv[1] if len(sys.argv) > 1 else 'OQP-1009'
    
    print("\n" + "=" * 80)
    print("OQPAY CREDENTIALS & KEYS GENERATOR")
    print("=" * 80)
    
    # 1. Generate Client Secret
    secret = generate_client_secret(reg_id)
    print(f"\n1. Client Secret for Registration ID '{reg_id}':")
    print(f"   {secret}")
    
    # 2. Generate RSA Keypair
    current_dir = os.path.dirname(os.path.abspath(__file__))
    keys_dir = os.path.join(current_dir, 'keys')
    
    priv_path, pub_path, pub_key_pem = generate_rsa_keypair(keys_dir)
    print(f"\n2. Generated RSA 2048-bit Keypair:")
    print(f"   Private Key saved to: {priv_path}")
    print(f"   Public Key saved to:  {pub_path}")
    print(f"\nPublic Key PEM:")
    print("-" * 80)
    print(pub_key_pem.strip())
    print("-" * 80)
    
if __name__ == '__main__':
    main()
