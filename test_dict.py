#!/usr/bin/env python3
"""Quick test of dictionary service"""
import sys
sys.path.insert(0, '/Users/jess/ChAnki')

from services.dictionary import DictionaryService

# Test the dictionary
dict_service = DictionaryService('/Users/jess/ChAnki/data/cedict_ts.u8')

print(f"Dictionary loaded: {len(dict_service.entries)} entries\n")

# Test 1: English search
print("=== Test 1: English → Chinese ===")
results = dict_service.search("hello")
for r in results[:3]:
    print(f"{r['hanzi']} ({r['pinyin']}): {', '.join(r['definitions'][:2])}")

print("\n=== Test 2: Pinyin → Chinese ===")
results = dict_service.search("ni hao")
for r in results[:3]:
    print(f"{r['hanzi']} ({r['pinyin']}): {', '.join(r['definitions'][:2])}")

print("\n=== Test 3: Hanzi → English ===")
results = dict_service.search("你好")
for r in results[:3]:
    print(f"{r['hanzi']} ({r['pinyin']}): {', '.join(r['definitions'][:2])}")

print("\n=== Test 4: More searches ===")
for query in ["love", "xihuan", "喜欢"]:
    results = dict_service.search(query)
    if results:
        r = results[0]
        print(f"'{query}' → {r['hanzi']} ({r['pinyin']})")
