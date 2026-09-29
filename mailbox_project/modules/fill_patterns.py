import os
import sys

import django

sys.path.append(r'/root/Mailbox/mailbox_project')#/root/Mailbox/mailbox_project

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mailbox_project.settings')
django.setup()

from other.Mailbox.mailbox_project.parser_app.models import EmailPattern

templates = [
    "{first_name}.{last_name}",
    "{first_name}{last_name}",
    "{first_name}_{last_name}",
    "{first_name}-{last_name}",
    "{f}.{last_name}",
    "{f}{last_name}",
    "{first_name}.{l}",
    "{first_name}{l}",
    "{last_name}.{first_name}",
    "{last_name}{first_name}",
    "{last_name}.{f}",
    "{first_name}{yy}",
    "{first_name}{yyyy}",
    "{first_name}.{last_name}{yy}",
    "{first_name}.{last_name}{yyyy}",
    "{first_name}{last_name}{yy}",
    "{first_name}{last_name}{yyyy}",
    "{f}{last_name}{yy}",
    "{last_name}{first_name}{yy}",
    "{last_name}.{first_name}{yy}"
]

for i, temp in enumerate(templates, start=1):
    EmailPattern.objects.get_or_create(
        name=f"pattern_{i}",
        defaults={"template": temp, "usage_count": 0}
    )
print("20 патернів успішно додано до бази!")