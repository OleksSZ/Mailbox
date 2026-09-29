import random

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import FirstName, LastName, NameCombination


DEFAULT_ROUNDS = 10


def sync_all_combinations(country: str, target_rounds: int = DEFAULT_ROUNDS) -> int:
    country = (country or "").strip().upper()
    if not country:
        return 0

    names = list(FirstName.objects.filter(country=country).values_list("name", flat=True))
    surnames = list(LastName.objects.filter(country=country).values_list("name", flat=True))

    if not names or not surnames:
        return 0

    existing = {}
    for fn, ln, r in (
        NameCombination.objects
        .filter(country=country)
        .values_list("first_name", "last_name", "round_number")
    ):
        info = existing.setdefault(fn, {"surnames": set(), "rounds": set()})
        info["surnames"].add(ln)
        info["rounds"].add(r)

    to_create = []
    for fn in names:
        info = existing.get(fn, {"surnames": set(), "rounds": set()})
        used_surnames = info["surnames"]
        used_rounds = info["rounds"]

        for r in range(1, target_rounds + 1):
            if r in used_rounds:
                continue
            available = [s for s in surnames if s not in used_surnames]
            if not available:
                break
            ln = random.choice(available)
            used_surnames.add(ln)
            used_rounds.add(r)
            to_create.append(NameCombination(
                first_name=fn, last_name=ln,
                country=country, round_number=r, is_used=False,
            ))

    if to_create:
        NameCombination.objects.bulk_create(
            to_create, ignore_conflicts=True, batch_size=1000,
        )
    return len(to_create)


def generate_for_country(country: str, rounds: int = DEFAULT_ROUNDS, clear: bool = False) -> int:
    country = country.strip().upper()
    if clear:
        NameCombination.objects.filter(country=country).delete()
    return sync_all_combinations(country, target_rounds=rounds)


def ensure_name_has_all_rounds(name: str, country: str, rounds: int = DEFAULT_ROUNDS) -> int:
    return sync_all_combinations(country, target_rounds=rounds)


@receiver(post_save, sender=FirstName)
def on_first_name_created(sender, instance, created, **kwargs):
    if not created:
        return
    n = sync_all_combinations(instance.country)
    if n:
        print(f"[signals] +{instance.name} ({instance.country}): generated {n} combinations")


@receiver(post_save, sender=LastName)
def on_last_name_created(sender, instance, created, **kwargs):
    if not created:
        return
    n = sync_all_combinations(instance.country)
    if n:
        print(f"[signals] +{instance.name} ({instance.country}): generated {n} combinations")