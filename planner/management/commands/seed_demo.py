from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from planner.demo import seed_demo


class Command(BaseCommand):
    help = "Заполнить пустой существующий аккаунт вымышленными учебными данными"

    def add_arguments(self, parser):
        parser.add_argument("--user", required=True)

    def handle(self, *args, **options):
        user = get_user_model().objects.filter(username=options["user"]).first()
        if user is None:
            raise CommandError("Сначала создайте отдельный учебный аккаунт.")
        try:
            marker, created = seed_demo(user)
        except ValidationError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(f"{'Создан' if created else 'Уже существует'} демонстрационный набор от {marker.reference_date}. Реальными наблюдениями не является.")
