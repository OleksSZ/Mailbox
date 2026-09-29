import os
from django.contrib import admin, messages
from django.db import transaction
from django.db.models import Count, OuterRef, Subquery, IntegerField
from django.db.models.functions import Coalesce
from django.template.response import TemplateResponse

from .models import (
    MailboxAccount, CountryStatistic,
    FirstName, LastName, EmailPattern,
    NameCombination, BulkNameUpload,
)
from .signals import sync_all_combinations


# ============================================================
# MailboxAccount
# ============================================================

@admin.register(MailboxAccount)
class MailboxAccountAdmin(admin.ModelAdmin):
    list_display = (
        "email", "password", "full_name", "country", "gender",
        "created_at", "status", "provider", "used_pattern",
    )
    list_filter = ("country", "status", "provider")
    search_fields = ("email", "first_name", "last_name")

    @admin.display(description="Full Name")
    def full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip()


# ============================================================
# FirstName / LastName — usage status
# ============================================================

class _UsageCountMixin:
    name_field = None   # 'first_name' | 'last_name'

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        sub = (
            NameCombination.objects
            .filter(
                country=OuterRef("country"),
                is_used=True,
                **{self.name_field: OuterRef("name")},
            )
            .values("country")
            .annotate(c=Count("*"))
            .values("c")
        )
        return qs.annotate(
            used_count=Coalesce(Subquery(sub, output_field=IntegerField()), 0)
        )


@admin.register(FirstName)
class FirstNameAdmin(_UsageCountMixin, admin.ModelAdmin):
    name_field = "first_name"

    list_display = ("id", "name", "country", "gender", "usage_count")
    list_filter = ("country", "gender")
    search_fields = ("name",)
    list_display_links = ("id", "name")
    list_per_page = 200
    ordering = ("country", "id")

    @admin.display(description="Status", ordering="used_count")
    def usage_count(self, obj):
        return "Done" if obj.used_count else "New"


@admin.register(LastName)
class LastNameAdmin(_UsageCountMixin, admin.ModelAdmin):
    name_field = "last_name"

    list_display = ("id", "name", "country", "usage_count")
    list_filter = ("country",)
    search_fields = ("name",)
    list_display_links = ("id", "name")
    list_per_page = 200
    ordering = ("country", "id")

    @admin.display(description="Status", ordering="used_count")
    def usage_count(self, obj):
        return "Done" if obj.used_count else "New"


# ============================================================
# EmailPattern
# ============================================================

@admin.register(EmailPattern)
class EmailPatternAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "template", "usage_count")
    search_fields = ("name", "template")
    ordering = ("id",)


# ============================================================
# NameCombination
# ============================================================

@admin.register(NameCombination)
class NameCombinationAdmin(admin.ModelAdmin):
    list_display = ("id", "combination", "country", "round_number", "is_used", "created_at")
    list_filter = ("country", "round_number", "is_used")
    search_fields = ("first_name", "last_name")
    list_display_links = ("id", "combination")
    list_per_page = 200
    ordering = ("country", "round_number", "id")
    show_full_result_count = False

    @admin.display(description="Combination")
    def combination(self, obj):
        return f"{obj.first_name} {obj.last_name}"

    def has_add_permission(self, request):
        return False


# ============================================================
# BulkNameUpload — Excel/CSV + comma-text
# ============================================================

def _read_upload(path: str):
    """Возвращает list[dict] со строками Excel/CSV."""
    import pandas as pd
    ext = os.path.splitext(path)[1].lower()
    if ext in (".xlsx", ".xls"):
        df = pd.read_excel(path, dtype=str).fillna("")
    else:
        df = pd.read_csv(path, dtype=str).fillna("")
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    return df.to_dict(orient="records")


@admin.register(BulkNameUpload)
class BulkNameUploadAdmin(admin.ModelAdmin):
    list_display = (
        "id", "country", "mode", "created_at",
        "created_first", "created_last", "created_combos", "skipped",
    )
    list_filter = ("country", "mode")
    readonly_fields = (
        "created_at", "created_first", "created_last",
        "created_combos", "skipped",
    )
    fields = (
        "country", "mode",
        "upload_file",
        "names_bulk", "last_names_bulk",
        "created_at", "created_first", "created_last", "created_combos", "skipped",
    )

    def save_model(self, request, obj, form, change):
        default_country = (obj.country or "").strip().upper()

        rows = []   # list of (country, first_name, last_name, gender)

        # --- источник 1: файл ---
        if obj.upload_file:
            try:
                file_rows = _read_upload(obj.upload_file.path)
                for r in file_rows:
                    country = (r.get("country") or default_country).strip().upper()
                    fn = (r.get("first_name") or "").strip()
                    ln = (r.get("last_name") or "").strip()
                    g = (r.get("gender") or "").strip().upper() or "M"
                    if not country or len(country) != 2:
                        continue
                    if not fn and not ln:
                        continue
                    if g not in ("M", "F"):
                        g = "M"
                    rows.append((country, fn, ln, g))
            except Exception as e:
                messages.error(request, f"Could not read file: {e}")
                return

        # --- источник 2: текст через запятую ---
        if not rows:
            if len(default_country) != 2:
                messages.error(request, "Provide a valid 2-letter country for text input.")
                return
            names = [n.strip() for n in (obj.names_bulk or "").split(",") if n.strip()]
            lasts = [n.strip() for n in (obj.last_names_bulk or "").split(",") if n.strip()]
            names = list(dict.fromkeys(names))
            lasts = list(dict.fromkeys(lasts))
            for n in names:
                rows.append((default_country, n, "", "M"))
            for n in lasts:
                rows.append((default_country, "", n, ""))

        if not rows:
            messages.error(request, "Nothing to upload.")
            return

        # --- раскладываем по странам ---
        by_country = {}
        for country, fn, ln, g in rows:
            bucket = by_country.setdefault(country, {"f": set(), "l": set(), "genders": {}})
            if fn:
                bucket["f"].add(fn)
                bucket["genders"][fn] = g
            if ln:
                bucket["l"].add(ln)

        created_first = created_last = skipped = 0

        with transaction.atomic():
            for country, data in by_country.items():
                # FirstName
                if data["f"]:
                    existing = set(
                        FirstName.objects.filter(country=country).values_list("name", flat=True)
                    )
                    to_create = []
                    for n in data["f"]:
                        if n in existing:
                            skipped += 1
                        else:
                            to_create.append(FirstName(
                                name=n, country=country, gender=data["genders"].get(n, "M"),
                            ))
                    FirstName.objects.bulk_create(to_create, ignore_conflicts=True)
                    created_first += len(to_create)

                # LastName
                if data["l"]:
                    existing = set(
                        LastName.objects.filter(country=country).values_list("name", flat=True)
                    )
                    to_create = [n for n in data["l"] if n not in existing]
                    skipped += len(data["l"]) - len(to_create)
                    LastName.objects.bulk_create(
                        [LastName(name=n, country=country) for n in to_create],
                        ignore_conflicts=True,
                    )
                    created_last += len(to_create)

                sync_all_combinations(country)

            combos_total = sum(
                NameCombination.objects.filter(country=c).count()
                for c in by_country.keys()
            )

        obj.created_first = created_first
        obj.created_last = created_last
        obj.created_combos = combos_total
        obj.skipped = skipped
        super().save_model(request, obj, form, change)

        messages.success(
            request,
            f"Done. First names: {created_first}, last names: {created_last}, "
            f"combinations total: {combos_total}, duplicates skipped: {skipped}.",
        )

    def has_change_permission(self, request, obj=None):
        if obj is not None:
            return False
        return super().has_change_permission(request, obj)


# ============================================================
# Country statistics
# ============================================================

@admin.register(CountryStatistic)
class CountryStatisticAdmin(admin.ModelAdmin):
    def changelist_view(self, request, extra_context=None):
        countries = sorted(set(
            list(FirstName.objects.values_list("country", flat=True).distinct()) +
            list(LastName.objects.values_list("country", flat=True).distinct())
        ))

        stats = []
        for country in countries:
            n_total = FirstName.objects.filter(country=country).count()
            ln_total = LastName.objects.filter(country=country).count()

            accs = MailboxAccount.objects.filter(country=country)
            a_total = accs.count()
            a_free = accs.filter(status="New").count()

            c_total = NameCombination.objects.filter(country=country).count()
            c_used = NameCombination.objects.filter(country=country, is_used=True).count()

            stats.append({
                "country": country,
                "n_total": n_total,
                "ln_total": ln_total,
                "a_total": a_total, "a_free": a_free, "a_used": a_total - a_free,
                "c_total": c_total, "c_used": c_used, "c_free": c_total - c_used,
            })

        context = dict(
            self.admin_site.each_context(request),
            title="Country Statistics",
            stats=stats,
        )
        return TemplateResponse(
            request,
            "admin/parser_app/mailboxaccount/country_statistics.html",
            context,
        )