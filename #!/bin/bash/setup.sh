#!/bin/bash
# FILE: /setup.sh (CREATE NEW)
echo "🚀 Setting up Software Distribution Platform..."

# Create necessary directories
echo "📁 Creating directory structure..."
mkdir -p backend/apps/accounts/templates/accounts/email
mkdir -p backend/apps/licenses/templates/licenses/email
mkdir -p backend/apps/products/templates/products/email
mkdir -p logs
mkdir -p media
mkdir -p static

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "🐍 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install requirements
echo "📦 Installing requirements..."
pip install --upgrade pip
pip install -r requirements.txt

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "⚙️ Creating .env file..."
    cat > .env << EOF
# Django Settings
DEBUG=True
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(50))")
DJANGO_SETTINGS_MODULE=backend.config.settings.development

# Database
DATABASE_URL=postgres://admin:secretpassword@localhost:5432/software_platform

# Redis
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0

# Email (Development - Console)
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
DEFAULT_FROM_EMAIL=noreply@software-platform.com
SUPPORT_EMAIL=support@software-platform.com
FRONTEND_URL=http://localhost:3000

# Security
ALLOWED_HOSTS=localhost,127.0.0.1
CORS_ALLOWED_ORIGINS=http://localhost:3000
EOF
    echo "✅ .env file created"
fi

# Start services with Docker Compose
echo "🐳 Starting services with Docker Compose..."
docker-compose up -d postgres redis

echo "⏳ Waiting for services to be ready..."
sleep 10

# Run migrations
echo "🗄️ Running migrations..."
python manage.py makemigrations
python manage.py migrate

# Create superuser
echo "👑 Creating superuser..."
python manage.py shell << EOF
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(email='admin@example.com').exists():
    User.objects.create_superuser(
        email='admin@example.com',
        password='admin123',
        first_name='Admin',
        last_name='User',
        role='SUPER_ADMIN'
    )
    print("✅ Superuser created: admin@example.com / admin123")
else:
    print("⚠️ Superuser already exists")
EOF

# Start Celery worker in background
echo "🔧 Starting Celery worker..."
celery -A backend.config.celery worker --loglevel=info --detach

# Start Celery beat in background
echo "⏰ Starting Celery beat..."
celery -A backend.config.celery beat --loglevel=info --detach

echo ""
echo "✅ Setup complete!"
echo ""
echo "To start the development server:"
echo "  python manage.py runserver"
echo ""
echo "To start all services with Docker Compose:"
echo "  docker-compose up"
echo ""
echo "Access the application at:"
echo "  Backend API: http://localhost:8000"
echo "  Admin interface: http://localhost:8000/admin"
echo "  API Documentation: http://localhost:8000/api/docs/"
echo ""
echo "Default admin credentials:"
echo "  Email: admin@example.com"
echo "  Password: admin123"