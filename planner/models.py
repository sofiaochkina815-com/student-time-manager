from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError


class NamedReference(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="%(class)s_items")
    name = models.CharField("Название", max_length=120)
    description = models.TextField("Описание", max_length=1000, blank=True)

    class Meta:
        abstract = True
        ordering = ["name"]
        constraints = [models.UniqueConstraint(fields=["owner", "name"], name="%(class)s_unique_owner_name")]

    def __str__(self):
        return self.name


class Subject(NamedReference):
    """Дисциплина для группировки учебных задач студента."""


class TaskCategory(NamedReference):
    """Тип учебной работы: доклад, практика, подготовка к экзамену."""


class Task(models.Model):
    """Учебная задача принадлежит одному студенту."""
    class Priority(models.IntegerChoices):
        LOW = 1, "Низкий"
        NORMAL = 2, "Обычный"
        HIGH = 3, "Высокий"

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="study_tasks")
    subject = models.ForeignKey(Subject, verbose_name="Дисциплина", on_delete=models.SET_NULL, null=True, blank=True)
    category = models.ForeignKey(TaskCategory, verbose_name="Категория", on_delete=models.SET_NULL, null=True, blank=True)
    title = models.CharField("Название", max_length=200)
    description = models.TextField("Описание", max_length=5000, blank=True)
    due_date = models.DateField("Дедлайн", null=True, blank=True)
    priority = models.PositiveSmallIntegerField("Приоритет", choices=Priority.choices, default=Priority.NORMAL)
    planned_minutes = models.PositiveIntegerField("План, минут", default=60, validators=[MinValueValidator(1), MaxValueValidator(10080)])
    is_done = models.BooleanField("Завершена", default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["is_done", "-priority", "created_at"]
        constraints = [models.CheckConstraint(condition=models.Q(planned_minutes__gt=0), name="task_positive_plan")]

    def __str__(self):
        return self.title

    def clean(self):
        for field, model in [("subject", Subject), ("category", TaskCategory)]:
            pk = getattr(self, field + "_id")
            if pk and not model.objects.filter(pk=pk, owner_id=self.owner_id).exists():
                raise ValidationError({field: "Нельзя использовать чужой справочник."})


class TimeEntry(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="time_entries")
    date = models.DateField("Дата работы", default=timezone.localdate)
    minutes = models.PositiveIntegerField("Потрачено минут", validators=[MinValueValidator(1), MaxValueValidator(1440)])
    note = models.CharField("Комментарий", max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-created_at"]
        constraints = [models.CheckConstraint(condition=models.Q(minutes__gte=1, minutes__lte=1440), name="entry_valid_minutes")]


class WeekPlan(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    week_start = models.DateField("Начало недели")
    capacity_minutes = models.PositiveIntegerField("Доступно минут на неделю", default=600, validators=[MaxValueValidator(10080)])
    note = models.TextField("Заметка к плану", max_length=1000, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["owner", "week_start"], name="week_plan_unique_owner_start")]

    def clean(self):
        if self.week_start and self.week_start.weekday() != 0:
            raise ValidationError({"week_start": "Неделя должна начинаться с понедельника."})
