#!/usr/bin/env python3
"""Quick verification that ChAnki is operational"""

import requests
import json

print("=" * 60)
print("ChAnki Quick Verification")
print("=" * 60)

# Test 1: Health endpoint
try:
    r = requests.get("http://localhost:5173/api/health")
    data = r.json()
    print(f"\n✅ Server: ONLINE")
    print(f"   Database: {data['components']['database']['message']}")
    print(f"   Gemini: {data['components']['gemini']['message']}")
    print(f"   Anki: {data['components']['anki']['message']}")
except Exception as e:
    print(f"\n❌ Server: OFFLINE - {e}")
    exit(1)

# Test 2: Search
try:
    r = requests.get("http://localhost:5173/api/search?q=dog")
    data = r.json()
    print(f"\n✅ Search: WORKING ({data['count']} results for 'dog')")
    if data['count'] > 0:
        print(f"   First result: {data['results'][0]['simplified']} - {data['results'][0]['definitions'][0]}")
except Exception as e:
    print(f"\n❌ Search: FAILED - {e}")

# Test 3: Static file serving
try:
    r = requests.get("http://localhost:5173/")
    if "ChAnki" in r.text:
        print(f"\n✅ Frontend: SERVING")
    else:
        print(f"\n⚠️ Frontend: Unexpected content")
except Exception as e:
    print(f"\n❌ Frontend: FAILED - {e}")

print("\n" + "=" * 60)
print("If all tests pass, the issue is BROWSER CACHE.")
print("Solution: Open http://localhost:5173 in INCOGNITO mode")
print("=" * 60)
