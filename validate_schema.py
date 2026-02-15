#!/usr/bin/env python
import urllib.request
import json

try:
    print("Fetching /api/schema/...")
    r = urllib.request.urlopen('http://127.0.0.1:8000/api/schema/', timeout=10)
    data = json.load(r)
    
    print("✓ Valid OpenAPI JSON schema")
    print(f"\nTitle: {data['info']['title']}")
    print(f"Version: {data['info']['version']}")
    print(f"API Paths: {len(data['paths'])}")
    
    if 'components' in data and 'schemas' in data['components']:
        print(f"Schema Components: {len(data['components']['schemas'])}")
        print("\nFirst 10 schema names:")
        for i, name in enumerate(list(data['components']['schemas'].keys())[:10]):
            print(f"  - {name}")
    
    print("\n✓ Schema generation SUCCESSFUL - /api/schema/ endpoint is working!")
    
except json.JSONDecodeError as e:
    print(f"JSON Parse Error: {e}")
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")
