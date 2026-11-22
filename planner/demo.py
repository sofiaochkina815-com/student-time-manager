from datetime import datetime, time, timedelta
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from .models import DemoDataset, Subject, TaskCategory, Task, WeekPlan, StudyGoal, StudySession
from .services import record_time


@transaction.atomic
def seed_demo(user):
    get_user_model().objects.select_for_update().get(pk=user.pk)
    existing = DemoDataset.objects.filter(owner=user).first()
    if existing:
        return existing, False
    for model in [Subject, TaskCategory, Task, WeekPlan, StudyGoal, StudySession]:
        if model.objects.filter(owner=user).exists():
            raise ValidationError("Демонстрационные данные создаются только в пустом учебном аккаунте.")
    today = timezone.localdate()
    subjects = [Subject.objects.create(owner=user,name=name) for name in ["ДЕМО · Математика", "ДЕМО · Информатика"]]
    category = TaskCategory.objects.create(owner=user,name="ДЕМО · Практика")
    for offset in range(14):
        day = today - timedelta(days=13-offset)
        task = Task.objects.create(owner=user,subject=subjects[offset % 2],category=category,title=f"ДЕМО · Задание {offset+1:02}",due_date=day,planned_minutes=40+offset*5,is_done=offset%3 != 0,
            completed_at=timezone.make_aware(datetime.combine(day,time(12))) if offset%3 != 0 and day < today else None)
        record_time(user=user,task_id=task.pk,date=day,minutes=30+offset*4,note="Симуляционные записи для демонстрации")
        if task.is_done and task.completed_at is None:
            task.completed_at=timezone.now();task.save(update_fields=["completed_at"])
    WeekPlan.objects.create(owner=user,week_start=today-timedelta(days=today.weekday()),capacity_minutes=600,note="Демонстрационный бюджет")
    StudyGoal.objects.create(owner=user,title="ДЕМО · Регулярная практика",subject=subjects[0],starts_on=today-timedelta(days=13),ends_on=today+timedelta(days=7),target_minutes=500)
    return DemoDataset.objects.create(owner=user,reference_date=today), True
