#!/usr/bin/env python
"""Quick test to verify /api/schema/ returns 200 without 500 errors."""
import urllib.request
import urllib.error

try:
    print("Testing /api/schema/...")
    req = urllib.request.Request('http://127.0.0.1:8000/api/schema/', method='GET')
    with urllib.request.urlopen(req, timeout=10) as response:
        status = response.getcode()
        body_size = len(response.read())
        print(f"✓ HTTP {status}")
        print(f"✓ Response size: {body_size} bytes")
        print("✓ /api/schema/ is working!")
except urllib.error.HTTPError as e:
    print(f"✗ HTTP {e.code}: {e.reason}")
    if e.code == 500:
        print("Schema generation still has errors.")
    print(f"Response: {e.read(500).decode('utf-8', 'ignore')}")
except Exception as e:
    print(f"✗ Error: {type(e).__name__}: {e}")
