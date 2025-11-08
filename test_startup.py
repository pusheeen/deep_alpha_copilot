"""Test script to verify FastAPI app can start correctly."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

print("Testing FastAPI application startup...\n")

try:
    print("1. Loading environment variables...")
    from dotenv import load_dotenv
    load_dotenv()
    print("   ✓ Environment loaded\n")

    print("2. Importing FastAPI app...")
    from app.main import app
    print("   ✓ App imported successfully\n")

    print("3. Checking app configuration...")
    print(f"   - Title: {app.title}")
    print(f"   - Version: {app.version}")
    print(f"   - Routes registered: {len(app.routes)}")
    print("   ✓ App configured\n")

    print("4. Listing API routes...")
    routes = []
    for route in app.routes:
        if hasattr(route, 'methods') and hasattr(route, 'path'):
            methods = ','.join(route.methods)
            routes.append(f"   {methods:15} {route.path}")

    for route in sorted(routes):
        print(route)

    print(f"\n✅ SUCCESS: FastAPI app is ready to run!")
    print("\nTo start the server, run:")
    print("   uvicorn app.main:app --reload --port 8000")

except ImportError as e:
    print(f"\n❌ IMPORT ERROR: {e}")
    print("\nMissing dependency. Install with:")
    print("   pip install -r requirements.txt")
    sys.exit(1)

except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
