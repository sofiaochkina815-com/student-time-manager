"""Правила учёта времени, общие для всех способов ввода."""
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from .models import Task, TimeEntry, WeekPlan
from datetime import timedelta


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


def week_summary(user, week_start):
    start = week_start - timedelta(days=week_start.weekday())
    end = start + timedelta(days=6)
    tasks = Task.objects.filter(owner=user, due_date__range=(start, end))
    times = TimeEntry.objects.filter(task__owner=user, date__range=(start, end))
    plans_by_day = {row["due_date"]: row["total"] for row in tasks.values("due_date").annotate(total=Sum("planned_minutes"))}
    actuals_by_day = {row["date"]: row["total"] for row in times.values("date").annotate(total=Sum("minutes"))}
    days = [{"date": start+timedelta(days=offset), "planned": plans_by_day.get(start+timedelta(days=offset), 0), "actual": actuals_by_day.get(start+timedelta(days=offset), 0)} for offset in range(7)]
    planned = sum(day["planned"] for day in days)
    actual = sum(day["actual"] for day in days)
    plan = WeekPlan.objects.filter(owner=user, week_start=start).first()
    capacity = plan.capacity_minutes if plan else None
    return {"start": start, "end": end, "days": days, "planned": planned, "actual": actual,
            "capacity": capacity, "over_capacity": capacity is not None and planned > capacity,
            "difference": capacity-planned if capacity is not None else None,
            "task_count": tasks.count(), "completed_count": tasks.filter(is_done=True).count(),
            "undated_count": Task.objects.filter(owner=user, is_done=False, due_date__isnull=True).count()}


def goal_progress(user, goal, today=None):
    if goal.owner_id != user.pk:
        raise PermissionDenied
    today = today or timezone.localdate()
    entries = TimeEntry.objects.filter(task__owner=user, date__range=(goal.starts_on, min(goal.ends_on, today)))
    if goal.subject_id:
        entries = entries.filter(task__subject_id=goal.subject_id)
    actual = entries.aggregate(total=Sum("minutes"))["total"] or 0
    return {"goal": goal, "actual": actual, "remaining": max(0, goal.target_minutes-actual),
        "percentage": min(100, actual*100//goal.target_minutes), "reached": actual >= goal.target_minutes,
        "overdue": today > goal.ends_on and actual < goal.target_minutes}
