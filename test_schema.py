#!/usr/bin/env python
import urllib.request
import sys

try:
    print("Requesting /api/schema/...")
    r = urllib.request.urlopen('http://127.0.0.1:8000/api/schema/', timeout=10)
    print(f"STATUS: {r.status}")
    body = r.read(2000).decode('utf-8', 'ignore')
    print("RESPONSE BODY:")
    print(body)
except urllib.error.HTTPError as e:
    print(f"HTTP ERROR {e.code}")
    print(e.read(2000).decode('utf-8', 'ignore'))
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")
    sys.exit(1)
