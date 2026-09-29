import os
import sys
import django

# 1. Прописуємо шлях до головної папки проєкту
sys.path.append(r'/root/Mailbox/mailbox_project')#/root/Mailbox/mailbox_project

# 2. Вказуємо, де лежать налаштування (settings.py)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mailbox_project.settings')

# 3. Запускаємо ініціалізацію Django
django.setup()