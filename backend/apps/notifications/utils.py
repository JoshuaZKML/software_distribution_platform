# FILE: backend/apps/notifications/utils.py
import logging
from django.template import Template, Context
from django.core.exceptions import ImproperlyConfigured
from .models import EmailTemplate

logger = logging.getLogger(__name__)


def render_template(template_code, context_dict, raise_if_missing=False):
    """
    Render an EmailTemplate by its code, using the provided context.
    Returns a tuple (subject, plain_body, html_body).
    If template not found and raise_if_missing=False, returns (None, None, None).
    """
    try:
        template = EmailTemplate.objects.get(code=template_code, is_active=True)
    except EmailTemplate.DoesNotExist:
        if raise_if_missing:
            raise ImproperlyConfigured(f"Email template '{template_code}' not found or inactive.")
        logger.warning(f"Email template '{template_code}' missing – returning None.")
        return None, None, None

    # Use Django's template engine to render subject and bodies
    subject_template = Template(template.subject)
    plain_template = Template(template.plain_body)
    html_template = Template(template.html_body)

    context = Context(context_dict)
    subject = subject_template.render(context)
    plain_body = plain_template.render(context)
    html_body = html_template.render(context)

    return subject, plain_body, html_body