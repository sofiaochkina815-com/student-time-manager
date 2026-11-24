"""Редактирование задачи с проверкой версии открытой формы."""
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied,ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from .models import Task

EDITABLE_TASK_FIELDS=('title','description','subject','category','due_date','priority','planned_minutes')


@transaction.atomic
def save_task(user,values,task_id=None,expected_updated_at=None):
    if not get_user_model().objects.select_for_update().get(pk=user.pk).is_active:
        raise PermissionDenied
    if set(values)!=set(EDITABLE_TASK_FIELDS):
        raise ValidationError('Неверный состав полей задачи.')
    if task_id:
        task=get_object_or_404(Task.objects.select_for_update(),owner=user,pk=task_id)
        if expected_updated_at is None or task.updated_at!=expected_updated_at:
            raise ValidationError('Задача уже изменилась в другой форме. Откройте её заново и проверьте актуальные данные.')
    else:
        task=Task(owner=user)
    for key,value in values.items():setattr(task,key,value)
    task.full_clean()
    task.save(update_fields=[*EDITABLE_TASK_FIELDS,'updated_at'] if task_id else None)
    return task
