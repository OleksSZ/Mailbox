from django.db import models


class MailboxAccount(models.Model):
    email = models.CharField(max_length=255, unique=True, verbose_name="Email")
    password = models.CharField(max_length=255, verbose_name="Password")

    first_name = models.CharField(max_length=100, verbose_name="First Name")
    last_name = models.CharField(max_length=100, verbose_name="Last Name")
    country = models.CharField(max_length=100, verbose_name="Country")

    created_at = models.DateField(null=True, blank=True, verbose_name="Created At")
    status = models.CharField(max_length=100, null=True, blank=True, verbose_name="Status")

    provider = models.CharField(max_length=100, null=True, blank=True, verbose_name="Provider")
    gender = models.CharField(max_length=10, null=True, blank=True, verbose_name="Gender")

    used_pattern = models.CharField(max_length=40, null=True, verbose_name="Used Pattern")

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def __str__(self):
        return f"{self.email} | {self.country}"

    class Meta:
        verbose_name = "Mailbox Account"
        verbose_name_plural = "Mailbox Accounts"


class FirstName(models.Model):
    name = models.CharField(max_length=100, verbose_name="Name")
    country = models.CharField(max_length=2, verbose_name="Country Code")
    gender = models.CharField(max_length=10, verbose_name="Gender (M/F)")

    def __str__(self):
        return f"[{self.country}] {self.name} ({self.gender})"

    class Meta:
        verbose_name = "First Name"
        verbose_name_plural = "First Names"
        indexes = [
            models.Index(fields=["country", "gender"]),
            models.Index(fields=["country", "name"]),
        ]


class LastName(models.Model):
    name = models.CharField(max_length=100, verbose_name="Last Name")
    country = models.CharField(max_length=2, verbose_name="Country Code")

    def __str__(self):
        return f"[{self.country}] {self.name}"

    class Meta:
        verbose_name = "Last Name"
        verbose_name_plural = "Last Names"
        indexes = [
            models.Index(fields=["country"]),
            models.Index(fields=["country", "name"]),
        ]


class EmailPattern(models.Model):
    name = models.CharField(max_length=50, unique=True, verbose_name="Name (ID)")
    template = models.CharField(max_length=100, verbose_name="Template")
    usage_count = models.IntegerField(default=0, verbose_name="Usage Count")

    def __str__(self):
        return f"{self.name} | {self.template}"

    class Meta:
        verbose_name = "Email Pattern"
        verbose_name_plural = "Email Patterns"
        ordering = ("id",)


class CountryStatistic(MailboxAccount):
    class Meta:
        proxy = True
        verbose_name = "Country Statistic"
        verbose_name_plural = "Country Statistics"


class NameCombination(models.Model):
    first_name = models.CharField(max_length=100, verbose_name="First Name")
    last_name = models.CharField(max_length=100, verbose_name="Last Name")
    country = models.CharField(max_length=2, db_index=True, verbose_name="Country Code")
    round_number = models.PositiveSmallIntegerField(db_index=True, verbose_name="Round")
    is_used = models.BooleanField(default=False, db_index=True, verbose_name="Used")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created At")

    def __str__(self):
        return f"[{self.country}] R{self.round_number} {self.first_name} {self.last_name}"

    class Meta:
        verbose_name = "Name Combination"
        verbose_name_plural = "Name Combinations"
        ordering = ("country", "round_number", "id")
        indexes = [
            models.Index(fields=["country", "round_number", "is_used"]),
            models.Index(fields=["country", "is_used"]),
            models.Index(fields=["country", "first_name"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["first_name", "last_name", "country", "round_number"],
                name="uniq_name_combo_per_country_round",
            ),
        ]


class BulkNameUpload(models.Model):
    """
    Одна запись = один импорт. Читаем файл Excel/CSV построчно.
    Каждая строка: country, first_name, last_name, gender
    Любую колонку, кроме country, можно оставить пустой.
    """
    MODE_CHOICES = [
        ("auto", "Auto (read file)"),
        ("text", "Comma-separated text"),
    ]

    country = models.CharField(
        max_length=2, blank=True, default="",
        verbose_name="Default Country",
        help_text="Used when a row has no country column. Leave blank if every row has its own.",
    )
    mode = models.CharField(
        max_length=10, choices=MODE_CHOICES, default="auto", verbose_name="Input Mode",
    )
    upload_file = models.FileField(
        upload_to="bulk_uploads/", null=True, blank=True,
        verbose_name="File (XLSX / XLS / CSV)",
        help_text="Columns: country, first_name, last_name, gender. Only 'country' is required per row.",
    )
    names_bulk = models.TextField(
        blank=True, verbose_name="First Names (comma-separated)",
        help_text="Used only when mode = text. Marco, Luca, Giovanni, ...",
    )
    last_names_bulk = models.TextField(
        blank=True, verbose_name="Last Names (comma-separated)",
        help_text="Used only when mode = text. Rossi, Ferrari, Bianchi, ...",
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Date")
    created_first = models.IntegerField(default=0, verbose_name="First Names Created")
    created_last = models.IntegerField(default=0, verbose_name="Last Names Created")
    created_combos = models.IntegerField(default=0, verbose_name="Combinations Created")
    skipped = models.IntegerField(default=0, verbose_name="Duplicates Skipped")

    class Meta:
        verbose_name = "Bulk Upload"
        verbose_name_plural = "Bulk Uploads"
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.country or 'MULTI'} / {self.get_mode_display()} / {self.created_at:%Y-%m-%d %H:%M}"