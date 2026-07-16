#!/usr/bin/env python3
"""
Check if chargeback routes are properly loaded
"""

from app import app

def check_routes():
    """Check all registered routes"""
    print("Checking chargeback routes...")
    print("=" * 80)
    
    chargeback_routes = []
    for rule in app.url_map.iter_rules():
        if 'chargeback' in rule.rule:
            chargeback_routes.append({
                'endpoint': rule.endpoint,
                'methods': ','.join(rule.methods - {'HEAD', 'OPTIONS'}),
                'path': rule.rule
            })
    
    if not chargeback_routes:
        print("❌ No chargeback routes found!")
        print("\nThis means the chargeback_bp blueprint is not properly registered.")
        print("Please check:")
        print("1. Is chargeback_routes.py in the backend folder?")
        print("2. Is 'from chargeback_routes import chargeback_bp' in app.py?")
        print("3. Is 'app.register_blueprint(chargeback_bp)' in app.py?")
        print("4. Has the Flask server been restarted?")
        return
    
    print(f"✅ Found {len(chargeback_routes)} chargeback routes:\n")
    
    for route in sorted(chargeback_routes, key=lambda x: x['path']):
        print(f"  {route['methods']:12} {route['path']}")
    
    print("\n" + "=" * 80)
    
    # Check specifically for the accept route
    accept_route = [r for r in chargeback_routes if 'accept' in r['path']]
    if accept_route:
        print("✅ Accept chargeback route is registered:")
        for route in accept_route:
            print(f"  {route['methods']:12} {route['path']}")
    else:
        print("❌ Accept chargeback route NOT found!")
        print("  Expected: POST /api/chargeback/merchant/accept/<int:chargeback_id>")
    
    print("\n" + "=" * 80)
    print("\nIf routes are missing, restart the Flask server:")
    print("  sudo systemctl restart orchpay")
    print("  # or")
    print("  pkill -f 'python.*app.py' && python3 app.py")

if __name__ == '__main__':
    check_routes()
