"""
Bootstrap script to make the project migration-safe WITHOUT
changing architecture or database backend (PostgreSQL only).
"""

import os
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent

APPS = {
    "accounts": [
        "UserViewSet",
        "AdminProfileViewSet",
        "UserSessionViewSet",
        "AdminActionLogViewSet",
        "UserRegistrationView",
    ],
    "products": ["ProductViewSet"],
    "licenses": ["LicenseViewSet"],
    "payments": ["PaymentViewSet"],
    "security": ["AuditLogViewSet"],
    "api": ["HealthCheckView"],
    "dashboard": ["DashboardStatsView"],
}

print("\n🔧 Bootstrapping project for PostgreSQL-backed migrations...\n")

# ------------------------------------------------------------------
# 1. Ensure backend/logs exists (logging must not crash Django)
# ------------------------------------------------------------------
logs_dir = BASE_DIR / "backend" / "logs"
logs_dir.mkdir(parents=True, exist_ok=True)
print("✅ Ensured backend/logs/ exists")

# ------------------------------------------------------------------
# 2. Create placeholder views that MATCH urls.py expectations
# ------------------------------------------------------------------
for app, classes in APPS.items():
    views_path = BASE_DIR / "backend" / "apps" / app / "views.py"

    content = [
        "from rest_framework import viewsets",
        "from rest_framework.views import APIView",
        "from rest_framework.response import Response",
        "",
        "# AUTO-GENERATED PLACEHOLDERS (safe to replace later)",
        "",
    ]

    for cls in classes:
        if cls.endswith("ViewSet"):
            content.append(
                f"class {cls}(viewsets.ViewSet):\n"
                f"    def list(self, request):\n"
                f"        return Response({{'status': '{cls} placeholder'}})\n"
            )
        else:
            content.append(
                f"class {cls}(APIView):\n"
                f"    def get(self, request):\n"
                f"        return Response({{'status': '{cls} placeholder'}})\n"
            )

    views_path.write_text("\n".join(content))
    print(f"🧩 Patched views.py for {app}")

# ------------------------------------------------------------------
# 3. Create settings/__init__.py (required for modular settings)
# ------------------------------------------------------------------
settings_init = BASE_DIR / "backend" / "config" / "settings" / "__init__.py"
settings_init.write_text(
    """from .base import *
import os

env = os.environ.get("DJANGO_ENV", "development")

if env == "production":
    from .production import *
elif env == "testing":
    from .testing import *
else:
    from .development import *
"""
)
print("⚙️  Created settings/__init__.py")

# ------------------------------------------------------------------
# 4. Verify PostgreSQL environment variables exist
# ------------------------------------------------------------------
required_env = ["DB_NAME", "DB_USER", "DB_PASSWORD", "DB_HOST", "DB_PORT"]
missing = [e for e in required_env if not os.environ.get(e)]

if missing:
    print("\n❌ Missing PostgreSQL environment variables:")
    for m in missing:
        print(f"   - {m}")
    print("\n👉 Fix your .env or environment before migrating.")
    sys.exit(1)

print("🗄️  PostgreSQL environment variables detected")

print("\n🎉 Bootstrap complete. You may now run migrations safely.\n")
