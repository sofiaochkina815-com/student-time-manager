"""Явные переходы статуса с защитой устаревшей формы и журналом."""
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from .models import Task, TaskStateEvent


class StateForm(forms.Form):
    done = forms.TypedChoiceField(choices=[('0', 'В плане'), ('1', 'Завершена')], coerce=lambda x: x == '1')
    revision = forms.IntegerField(min_value=0)


@transaction.atomic
def set_task_state(user, task_id, done, revision):
    locked = get_user_model().objects.select_for_update().get(pk=user.pk)
    if not locked.is_active:
        raise PermissionDenied
    task = get_object_or_404(Task.objects.select_for_update(), owner=user, pk=task_id)
    if task.is_done == done:
        return task, False
    if task.status_revision != revision:
        raise ValidationError('Статус уже изменился. Обновите список и повторите действие.')
    now = timezone.now()
    TaskStateEvent.objects.create(owner=user, task=task, title=task.title, previous_done=task.is_done,
        is_done=done, due_date=task.due_date, planned_minutes=task.planned_minutes,
        revision=revision+1, recorded_at=now)
    task.is_done = done
    task.status_revision += 1
    task.completed_at = now if done else None
    task.save(update_fields=['is_done', 'status_revision', 'completed_at', 'updated_at'])
    return task, True


@login_required
def history(request):
    events = TaskStateEvent.objects.filter(owner=request.user)
    return render(request, 'planner/task_history.html', {'page': Paginator(events, 50).get_page(request.GET.get('page'))})
