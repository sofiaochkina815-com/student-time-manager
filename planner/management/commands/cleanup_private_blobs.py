import json
from django.core.management.base import BaseCommand, CommandError
from planner.file_maintenance import cleanup_blobs


class Command(BaseCommand):
    help = "Проверить старые неиспользуемые DB-файлы; удаление только с --delete"

    def add_arguments(self, parser):
        parser.add_argument("--delete", action="store_true")
        parser.add_argument("--older-than-days", type=int, default=7)
        parser.add_argument("--limit", type=int, default=1000)

    def handle(self, *args, **options):
        try:
            report = cleanup_blobs(delete=options["delete"], older_than_days=options["older_than_days"], limit=options["limit"])
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(json.dumps(report, ensure_ascii=False))
