import random
import datetime

from unidecode import unidecode
from django.db import transaction
from django.db.models import F

import other.Mailbox.mailbox_project.modules.load_django as load_django
from other.Mailbox.mailbox_project.parser_app.models import FirstName, LastName, EmailPattern, NameCombination


def transliterate_for_email(text: str) -> str:
    return unidecode(text).lower().replace(" ", "").replace("'", "")


def clean_name_for_form(text: str) -> str:
    """
    Точечно заменяет только те символы, которые не пропускает форма регистрации.
    Остальное (ä, ö, å, é) остаётся как есть.
    """
    replacements = {
        'œ': 'oe', 'Œ': 'Oe',
        'æ': 'ae', 'Æ': 'Ae',
        'š': 's', 'Š': 'S',
        'ž': 'z', 'Ž': 'Z',
        'ē': 'e', 'Ē': 'E',
        'ī': 'i', 'Ī': 'I',
        'ō': 'o', 'Ō': 'O',
        'ū': 'u', 'Ū': 'U',
        'ą': 'a', 'Ą': 'A',
        'ć': 'c', 'Ć': 'C',
        'ę': 'e', 'Ę': 'E',
        'ł': 'l', 'Ł': 'L',
        'ń': 'n', 'Ń': 'N',
        'ś': 's', 'Ś': 'S',
        'ź': 'z', 'Ź': 'Z',
        'ż': 'z', 'Ż': 'Z'
    }
    cleaned = text
    for bad, good in replacements.items():
        cleaned = cleaned.replace(bad, good)
    return cleaned


def get_next_email_pattern(email_first: str, email_last: str) -> tuple[str, str]:
    pattern_obj = EmailPattern.objects.order_by('usage_count').first()
    if not pattern_obj:
        raise ValueError('В БД нет ни одного паттерна. Сначала запусти fill_patterns.py')

    year_of_birth = random.randint(1975, 2006)

    context = {
        'first_name': email_first,
        'last_name': email_last,
        'f': email_first[:1],
        'l': email_last[:1],
        'yy': f'{year_of_birth % 100:02d}',
        'yyyy': str(year_of_birth),
    }
    email = pattern_obj.template.format(**context)

    EmailPattern.objects.filter(pk=pattern_obj.pk).update(
        usage_count=F('usage_count') + 1
    )
    return email, pattern_obj.template


class DatabaseNameGenerator:
    """
    Берёт комбинацию из очереди NameCombination.
    Сначала идут младшие круги, потом старшие.
    """

    def __init__(self, country_code: str):
        self.country_code = country_code.upper()

    def generate_next(self) -> dict:
        # Атомарно: берём свободную комбинацию и сразу помечаем is_used=True.
        # select_for_update(skip_locked=True) — если параллельный воркер
        # держит строку, мы не ждём, а берём следующую.
        with transaction.atomic():
            combo = (
                NameCombination.objects
                .select_for_update(skip_locked=True)
                .filter(country=self.country_code, is_used=False)
                .order_by('round_number', 'id')
                .first()
            )
            if combo is None:
                raise ValueError(f"Все комбинации для '{self.country_code}' исчерпаны!")

            combo.is_used = True
            combo.save(update_fields=['is_used'])

        # Пол для формы берём из FirstName (у NameCombination нет пола)
        gender = 'M'
        try:
            fn_obj = FirstName.objects.filter(
                country=self.country_code, name=combo.first_name
            ).first()
            if fn_obj and fn_obj.gender:
                gender = fn_obj.gender.upper()
        except Exception:
            pass

        original_first_name = clean_name_for_form(combo.first_name)
        original_last_name = clean_name_for_form(combo.last_name)

        email_first = transliterate_for_email(combo.first_name)
        email_last = transliterate_for_email(combo.last_name)

        email, pattern_name = get_next_email_pattern(email_first, email_last)

        return {
            "combo_id": combo.id,
            "first_name": original_first_name,
            "last_name": original_last_name,
            "gender": gender,
            "email": email,
            "pattern_used": pattern_name,
            "country": self.country_code,
            "round_number": combo.round_number,
        }


    @staticmethod
    def release(combo_id: int) -> None:
        """Возвращает комбинацию в пул (при ошибке регистрации)."""
        if not combo_id:
            return
        combo = NameCombination.objects.filter(id=combo_id).first()
        if combo and combo.is_used:
            combo.is_used = False
            combo.save(update_fields=["is_used"])
        NameCombination.objects.filter(id=combo_id).update(is_used=False)