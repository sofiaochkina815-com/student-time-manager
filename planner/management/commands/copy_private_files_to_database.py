import hashlib
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from planner.models import TaskAttachment, PrivateFileBlob
from planner.storage import DatabasePrivateStorage


class Command(BaseCommand):
    help = "Копировать проверенные личные файлы из MEDIA_ROOT в БД без удаления исходников"

    def handle(self, *args, **options):
        source = FileSystemStorage(location=settings.MEDIA_ROOT)
        target = DatabasePrivateStorage()
        count = 0
        for item in TaskAttachment.objects.order_by("pk").iterator():
            name = item.file.name
            existing = PrivateFileBlob.objects.filter(name=name).first()
            if existing:
                if existing.size != item.size or hashlib.sha256(bytes(existing.content)).hexdigest() != item.sha256:
                    raise CommandError("Несовпадение уже сохранённого документа; копирование остановлено.")
                continue
            try:
                with source.open(name,"rb") as stream:
                    data = stream.read(5 * 1024 * 1024 + 1)
            except OSError as exc:
                raise CommandError("Исходный документ не найден; файл не подменён.") from exc
            if len(data) != item.size or hashlib.sha256(data).hexdigest() != item.sha256:
                raise CommandError("Размер или SHA-256 исходного документа не совпадает.")
            with transaction.atomic():
                target._save(name, ContentFile(data))
            count += 1
        self.stdout.write(f"Скопировано документов: {count}. Исходные файлы сохранены.")
