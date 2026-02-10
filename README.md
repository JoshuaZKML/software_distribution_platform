# Software Distribution Platform

A comprehensive three-tier permission software distribution platform with activation keys, built with Django 4.2.28 and React.

## Features
- **Super Admin**: Full system control and monitoring
- **Admin (Staff)**: Manage users, licenses, payments, and software
- **Users**: Purchase software, manage activation keys, download software
- **Security**: Advanced abuse detection, rate limiting, device fingerprinting
- **Activation Keys**: Secure key generation, validation, and management

## Tech Stack
- **Backend**: Django 4.2.28, Django REST Framework, PostgreSQL, Redis, Celery, JWT
- **Frontend**: React, Material-UI, Redux/Zustand, Axios
- **Security**: drf-spectacular, django-guardian, cryptography, rate limiting
- **DevOps**: Docker, Nginx, Gunicorn, Whitenoise

## Project Structure
- `backend/`: Django source code
- `frontend/`: React source code
- `docs/`: System documentation
