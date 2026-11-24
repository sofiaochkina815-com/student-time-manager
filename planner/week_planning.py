"""Сериализация бюджета с изменениями задач и учёта времени владельца."""
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from .models import WeekPlan


@transaction.atomic
def save_week_plan(user, start, expected_revision, capacity, note=''):
    if not get_user_model().objects.select_for_update().get(pk=user.pk).is_active:
        raise PermissionDenied
    plan=WeekPlan.objects.filter(owner=user,week_start=start).first()
    current=plan.revision if plan else 0
    if type(expected_revision) is not int or expected_revision!=current:
        raise ValidationError('Бюджет недели уже изменён в другой вкладке. Откройте неделю заново.')
    plan=plan or WeekPlan(owner=user,week_start=start)
    plan.capacity_minutes=capacity
    plan.note=note
    plan.revision=current+1
    plan.full_clean()
    plan.save()
    return plan
