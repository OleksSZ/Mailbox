# modules/sync_combinations.py
"""
Синхронизация: помечает NameCombination.is_used=True
для всех комбинаций, по которым уже создан MailboxAccount.
Запуск: python sync_combinations.py
"""
import sys
import django

import other.Mailbox.mailbox_project.modules.load_django as load_django  # noqa: F401  (инициализирует Django)
from other.Mailbox.mailbox_project.parser_app.models import MailboxAccount, NameCombination
from other.Mailbox.mailbox_project.modules.name_generator import clean_name_for_form


def build_account_index():
    """Собираем set (country, cleaned_first, cleaned_last) из аккаунтов."""
    index = set()
    for acc in MailboxAccount.objects.all().only(
        "country", "first_name", "last_name"
    ):
        if not acc.country:
            continue
        index.add((
            acc.country.strip().upper(),
            (acc.first_name or "").strip(),
            (acc.last_name or "").strip(),
        ))
    return index


def sync(dry_run: bool = False) -> None:
    print("Строим индекс MailboxAccount...")
    account_index = build_account_index()
    print(f"  Аккаунтов учтено: {len(account_index)}")

    print("Проходим по NameCombination (is_used=False)...")
    qs = NameCombination.objects.filter(is_used=False).only(
        "id", "country", "first_name", "last_name"
    )

    to_mark = []
    total_scanned = 0

    for combo in qs.iterator(chunk_size=2000):
        total_scanned += 1
        cleaned_first = clean_name_for_form(combo.first_name).strip()
        cleaned_last = clean_name_for_form(combo.last_name).strip()
        key = (combo.country.upper(), cleaned_first, cleaned_last)
        if key in account_index:
            to_mark.append(combo.id)

    print(f"  Просканировано: {total_scanned}")
    print(f"  К пометке:      {len(to_mark)}")

    if dry_run:
        print("DRY-RUN — изменения не применялись.")
        return

    if to_mark:
        # батчами, чтобы не упереться в лимит SQL-переменных
        BATCH = 1000
        for i in range(0, len(to_mark), BATCH):
            chunk = to_mark[i:i + BATCH]
            NameCombination.objects.filter(id__in=chunk).update(is_used=True)
        print(f"Готово. Помечено is_used=True: {len(to_mark)}")
    else:
        print("Нечего помечать — всё уже синхронизировано.")


if __name__ == "__main__":
    dry = "--dry" in sys.argv
    sync(dry_run=dry)
    