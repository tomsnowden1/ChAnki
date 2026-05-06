#!/usr/bin/env python3
"""Quick verification that ChAnki is operational"""

import requests
import json

BASE = "http://localhost:8000"

print("=" * 60)
print("ChAnki Quick Verification")
print("=" * 60)

# Test 1: Health endpoint
try:
    r = requests.get(f"{BASE}/api/health", timeout=5)
    data = r.json()
    print(f"\n✅ Server: ONLINE")
    print(f"   Database: {data['components']['database']['message']}")
    print(f"   OpenAI:   {data['components']['ai']['message']}")
    print(f"   Anki:     {data['components']['anki']['message']}")
except Exception as e:
    print(f"\n❌ Server: OFFLINE - {e}")
    exit(1)

# Test 2: Search
try:
    r = requests.get(f"{BASE}/api/search?q=dog", timeout=5)
    data = r.json()
    print(f"\n✅ Search: WORKING ({data['count']} results for 'dog')")
    if data['count'] > 0:
        first = data['results'][0]
        print(f"   First result: {first['simplified']} - {first['definitions'][0]}")
except Exception as e:
    print(f"\n❌ Search: FAILED - {e}")

# Test 3: Static file serving
try:
    r = requests.get(f"{BASE}/", timeout=5)
    if "ChAnki" in r.text:
        print(f"\n✅ Frontend: SERVING")
    else:
        print(f"\n⚠️  Frontend: Unexpected content")
except Exception as e:
    print(f"\n❌ Frontend: FAILED - {e}")

# Test 4: Sync stats (public endpoint, no auth needed)
try:
    r = requests.get(f"{BASE}/api/sync/stats", timeout=5)
    data = r.json()
    print(f"\n✅ Sync queue: pending={data['pending']}  synced={data['synced']}  total={data['total']}")
except Exception as e:
    print(f"\n❌ Sync stats: FAILED - {e}")

print("\n" + "=" * 60)
