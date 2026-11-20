"""Правила учёта времени, общие для всех способов ввода."""
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from .models import Task, TimeEntry


@transaction.atomic
def record_time(*, user, task_id, date, minutes, note=""):
    # Блокировка пользователя сериализует проверку суточного лимита в PostgreSQL.
    get_user_model().objects.select_for_update().get(pk=user.pk)
    task = Task.objects.filter(pk=task_id, owner=user).first()
    if task is None:
        raise PermissionDenied("Нет доступа к этой задаче.")
    if date > timezone.localdate():
        raise ValidationError("Дата фактической работы не может быть в будущем.")
    entry = TimeEntry(task=task, date=date, minutes=minutes, note=note)
    entry.full_clean()
    used = TimeEntry.objects.filter(task__owner=user, date=date).aggregate(total=Sum("minutes"))["total"] or 0
    if used + minutes > 1440:
        raise ValidationError("Сумма записей за сутки не может превышать 24 часа.")
    entry.save()
    return entry
