#!/usr/bin/env python3
# SPDX-License-Identifier: LicenseRef-AOTS6-ARR-1.0
# Copyright (c) 2025-2026 Alfredo Jhovany Alfaro Garcia
# github.com/fo22Alfaro/aots6
"""
aots6_client.py — Cliente Python para AOTS6 x402 API
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Uso:
  python3 aots6_client.py catalog              # ver catálogo
  python3 aots6_client.py health               # estado servidor
  python3 aots6_client.py buy quantum          # iniciar pago
  python3 aots6_client.py get quantum <token>  # obtener módulo
  python3 aots6_client.py verify <tx> <nonce>  # verificar pago
"""
import urllib.request, urllib.error, json, sys, os

BASE_URL = os.environ.get('AOTS6_API', 'http://localhost:8402')

def get(path, token=None):
    req = urllib.request.Request(f"{BASE_URL}{path}")
    if token:
        req.add_header('X-Access-Token', token)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())
    except Exception as ex:
        return 0, {"error": str(ex)}

def post(path, data):
    body = json.dumps(data).encode()
    req  = urllib.request.Request(
        f"{BASE_URL}{path}", data=body,
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())
    except Exception as ex:
        return 0, {"error": str(ex)}

def print_json(data, title=None):
    if title: print(f"\n{'━'*52}\n {title}\n{'━'*52}")
    print(json.dumps(data, indent=2))

# ── Comandos ──────────────────────────────────────────────

def cmd_catalog():
    status, data = get('/')
    print_json(data, "AOTS6 Catalog")

def cmd_health():
    status, data = get('/health')
    print_json(data, "Server Health")

def cmd_hashes(token=None):
    status, data = get('/hashes', token)
    if status == 402:
        print("\n  ⚠ Payment required:")
        print(f"  Amount: {data['payment']['amount_usdc']} USDC")
        print(f"  Wallet: {data['payment']['networks']['base']['recipient_address']}")
        print(f"  Nonce:  {data['payment']['nonce']}")
        print(f"\n  Pay and verify with:")
        print(f"  python3 aots6_client.py verify <tx_hash> {data['payment']['nonce']} hashes")
    else:
        print_json(data, "AOTS6 Hashes")

def cmd_buy(resource):
    path = f'/aots6/{resource}' if not resource.startswith('/') else resource
    status, data = get(path)
    if status == 402:
        pay = data['payment']
        print(f"\n{'━'*52}")
        print(f" Payment Required for: {resource}")
        print(f"{'━'*52}")
        print(f"  Amount:  ${pay['amount_usdc']} USDC")
        print(f"  Nonce:   {pay['nonce']}")
        print(f"\n  BASE NETWORK:")
        print(f"  USDC:    {pay['networks']['base']['usdc_contract']}")
        print(f"  To:      {pay['networks']['base']['recipient_address']}")
        print(f"  Amount:  {pay['networks']['base']['amount']} (raw units)")
        print(f"\n  INSTRUCTIONS:")
        for i, step in enumerate(pay['instructions'], 1):
            print(f"  {step}")
        print(f"\n  AFTER PAYING:")
        print(f"  python3 aots6_client.py verify <tx_hash> {pay['nonce']} {resource}")
    else:
        print_json(data)

def cmd_get(resource, token):
    path = f'/aots6/{resource}'
    status, data = get(path, token)
    print_json(data, f"Module: {resource}")
    if status == 200 and 'raw_url' in data:
        print(f"\n  Direct download:")
        print(f"  curl {data['raw_url']} -o {resource}.py")

def cmd_verify(tx_hash, nonce, resource='module'):
    network = input("Network (base/polygon/eth) [base]: ").strip() or 'base'
    status, data = post('/verify-payment', {
        'tx_hash':  tx_hash,
        'nonce':    nonce,
        'network':  network,
        'resource': resource,
    })
    if status == 200:
        token = data.get('access_token', '')
        print(f"\n  ✓ Payment verified!")
        print(f"  Access Token: {token}")
        print(f"  Expires: {data.get('expires_in','?')}")
        print(f"\n  Save token:")
        print(f"  export AOTS6_TOKEN={token}")
        print(f"\n  Use token:")
        print(f"  python3 aots6_client.py get {resource} {token}")
    else:
        print(f"\n  ✗ Verification failed:")
        print_json(data)

# ── Main ──────────────────────────────────────────────────

if __name__ == '__main__':
    args = sys.argv[1:]
    if not args or args[0] == 'catalog':
        cmd_catalog()
    elif args[0] == 'health':
        cmd_health()
    elif args[0] == 'hashes':
        cmd_hashes(args[1] if len(args) > 1 else None)
    elif args[0] == 'buy' and len(args) > 1:
        cmd_buy(args[1])
    elif args[0] == 'get' and len(args) > 2:
        cmd_get(args[1], args[2])
    elif args[0] == 'verify' and len(args) > 2:
        resource = args[3] if len(args) > 3 else 'module'
        cmd_verify(args[1], args[2], resource)
    else:
        print(__doc__)
