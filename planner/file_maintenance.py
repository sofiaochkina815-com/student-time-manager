"""Удаляет только старые неиспользуемые DB-объекты поддерживаемого формата."""
import re
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from .models import PrivateFileBlob, TaskAttachment


def cleanup_blobs(*, delete=False, older_than_days=7, limit=1000):
    if type(older_than_days) is not int or not 1 <= older_than_days <= 3650:
        raise ValueError("Минимальный возраст — от 1 до 3650 дней.")
    if type(limit) is not int or not 1 <= limit <= 10000:
        raise ValueError("Размер пакета — от 1 до 10000.")
    cutoff = timezone.now()-timedelta(days=older_than_days)
    candidates = list(PrivateFileBlob.objects.filter(created_at__lt=cutoff)
        .exclude(name__in=TaskAttachment.objects.values("file"))
        .order_by("pk").values_list("pk", "name")[:limit])
    report = {"mode": "delete" if delete else "dry_run", "candidates": len(candidates),
        "eligible": 0, "deleted": 0, "preserved": 0, "unknown_names": 0, "bytes": 0}
    for pk, name in candidates:
        match = re.fullmatch(r"attachments/([1-9][0-9]*)/[a-f0-9]{32}\.(pdf|txt)", name)
        if not match:
            report["unknown_names"] += 1
            continue
        with transaction.atomic():
            # Та же последовательность блокировок, что у загрузки: пользователь, затем blob.
            get_user_model().objects.select_for_update().filter(pk=int(match[1])).first()
            item = PrivateFileBlob.objects.select_for_update().filter(pk=pk, name=name, created_at__lt=cutoff).first()
            if item is None or TaskAttachment.objects.filter(file=name).exists():
                report["preserved"] += 1
                continue
            report["eligible"] += 1
            report["bytes"] += item.size
            if delete:
                item.delete()
                report["deleted"] += 1
    return report
