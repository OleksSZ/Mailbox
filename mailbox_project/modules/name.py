import os
import sys
import django

sys.path.append('/home/oleks/Works/Mailbox/mailbox_project')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mailbox_project.settings')
django.setup()

from other.Mailbox.mailbox_project.parser_app.models import FirstName, LastName

country = 'US'

# 20 мужских и 20 
first_names = [
    ('Marco', 'M'), ('Luca', 'M'), ('Giuseppe', 'M'), ('Antonio', 'M'),
    ('Giovanni', 'M'), ('Francesco', 'M'), ('Andrea', 'M'), ('Mario', 'M'),
    ('Alessandro', 'M'), ('Matteo', 'M'), ('Sofia', 'F'), ('Giulia', 'F'),
    ('Alessia', 'F'), ('Francesca', 'F'), ('Elisa', 'F'), ('Valentina', 'F'),
    ('Chiara', 'F'), ('Martina', 'F'), ('Elena', 'F'), ('Lucia', 'F'),
]

last_names = [
    'Rossi', 'Russo', 'Ferrari', 'Esposito', 'Bianchi', 'Romano', 'Colombo',
    'Ricci', 'Marino', 'Greco', 'Bruno', 'Gallo', 'Conti', 'De Luca', 'Mancini',
    'Costa', 'Giordano', 'Rizzo', 'Lombardi', 'Moretti', 'Barbieri', 'Fontana',
    'Santoro', 'Marchetti', 'Rinaldi', 'Caruso', 'Ferrara', 'Galli', 'Martini',
    'Leone', 'Longo', 'Gentile', 'Martinelli', 'Vitale', 'Lombardo', 'Serra',
    'Cattaneo', 'Grassi', 'Palmieri', 'Valentini'
]

added = 0
for name, gender in first_names:
    obj, created = FirstName.objects.get_or_create(
        name=name,
        gender=gender,
        country=country,
        defaults={'is_used': False}
    )
    if created:
        added += 1

for surname in last_names:
    obj, created = LastName.objects.get_or_create(
        name=surname,
        country=country,
        defaults={'is_used': False}
    )
    if created:
        added += 1

print(f"Добавлено {added} записей (имён и фамилий) для {country}.")
print(f"Всего имён: {FirstName.objects.filter(country=country).count()}")
print(f"Всего фамилий: {LastName.objects.filter(country=country).count()}")