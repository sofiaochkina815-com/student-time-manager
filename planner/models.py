from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Task(models.Model):
    """Учебная задача принадлежит одному студенту."""
    class Priority(models.IntegerChoices):
        LOW = 1, "Низкий"
        NORMAL = 2, "Обычный"
        HIGH = 3, "Высокий"

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="study_tasks")
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
