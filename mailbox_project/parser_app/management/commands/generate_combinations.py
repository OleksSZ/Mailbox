from django.core.management.base import BaseCommand

from other.Mailbox.mailbox_project.parser_app.models import FirstName, LastName, NameCombination
from other.Mailbox.mailbox_project.parser_app.signals import generate_for_country, DEFAULT_ROUNDS


class Command(BaseCommand):
    help = 'Генерирует комбинации имя+фамилия на N кругов для страны (или для всех стран)'

    def add_arguments(self, parser):
        parser.add_argument(
            'country', type=str, nargs='?', default='all',
            help='Код страны (IT, CA, AU, ...) или "all" для всех',
        )
        parser.add_argument('--rounds', type=int, default=DEFAULT_ROUNDS)
        parser.add_argument('--clear', action='store_true', help='Удалить старые комбинации для страны')

    def handle(self, *args, **options):
        country_arg = (options['country'] or 'all').strip()
        rounds = options['rounds']
        clear = options['clear']

        if country_arg.lower() == 'all':
            countries = sorted(set(
                list(FirstName.objects.values_list('country', flat=True).distinct()) +
                list(LastName.objects.values_list('country', flat=True).distinct())
            ))
        else:
            countries = [country_arg.upper()]

        if not countries:
            self.stderr.write('Нет стран в БД.')
            return

        self.stdout.write(f'Кругов: {rounds}')
        self.stdout.write(f'Clear: {clear}')
        self.stdout.write('')

        grand_total = 0
        for cc in countries:
            names = FirstName.objects.filter(country=cc).count()
            surnames = LastName.objects.filter(country=cc).count()
            pairs_per_round = min(names, surnames)
            expected = pairs_per_round * rounds

            self.stdout.write(f'=== {cc} ===')
            self.stdout.write(f'  Імён: {names}, Фамилий: {surnames}, Пар/круг: {pairs_per_round}')
            self.stdout.write(f'  Ожидается: {expected}')

            created = generate_for_country(cc, rounds=rounds, clear=clear)
            grand_total += created
            self.stdout.write(self.style.SUCCESS(f'  Создано: {created}'))
            self.stdout.write('')

        self.stdout.write(self.style.SUCCESS(f'ВСЕГО создано: {grand_total}'))