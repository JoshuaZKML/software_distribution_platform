# FILE: backend/tests/factories.py
import factory
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from backend.apps.accounts.models import User
from backend.apps.products.models import Software, SoftwareVersion
from backend.apps.licenses.models import ActivationCode, CodeBatch
from backend.apps.payments.models import Payment

User = get_user_model()


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    email = factory.Sequence(lambda n: f"user{n}@example.com")
    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name')
    is_active = True
    role = User.Role.USER


class SoftwareFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Software

    name = factory.Sequence(lambda n: f"Software {n}")
    app_code = factory.Sequence(lambda n: f"APP{n:03d}")
    is_active = True


class SoftwareVersionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = SoftwareVersion

    software = factory.SubFactory(SoftwareFactory)
    version_number = factory.Sequence(lambda n: f"1.{n}")
    is_active = True


class ActivationCodeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ActivationCode

    software = factory.SubFactory(SoftwareFactory)
    human_code = factory.Sequence(lambda n: f"CODE-{n:08d}")
    # Use choices if defined on the model; fallback to strings
    license_type = ActivationCode.LicenseType.STANDARD if hasattr(ActivationCode, 'LicenseType') else 'STANDARD'
    status = ActivationCode.Status.GENERATED if hasattr(ActivationCode, 'Status') else 'GENERATED'
    expires_at = factory.LazyFunction(lambda: timezone.now() + timedelta(days=365))


class CodeBatchFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = CodeBatch

    name = factory.Sequence(lambda n: f"Batch {n}")
    software = factory.SubFactory(SoftwareFactory)
    count = 10


class PaymentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Payment

    user = factory.SubFactory(UserFactory)
    software = factory.SubFactory(SoftwareFactory)
    amount = 99.99
    currency = 'USD'
    payment_method = 'PAYSTACK'
    status = Payment.Status.COMPLETED