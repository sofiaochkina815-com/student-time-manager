from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
import secrets
import uuid
from pathlib import Path
from datetime import timedelta


def group_invite_code():
    return secrets.token_urlsafe(18)


class StudyGroup(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="curated_groups")
    name = models.CharField("Название группы", max_length=120)
    description = models.TextField("Описание", max_length=1000, blank=True)
    invite_code = models.CharField(max_length=32, unique=True, default=group_invite_code, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class GroupMembership(models.Model):
    group = models.ForeignKey(StudyGroup, on_delete=models.CASCADE, related_name="memberships")
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="study_memberships")
    share_summary = models.BooleanField("Разрешить куратору видеть мои суммарные показатели", default=False)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["group", "student"], name="group_unique_student")]


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
    status_revision = models.PositiveIntegerField(default=0)
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


class StudyGoal(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    title = models.CharField("Учебная цель", max_length=200)
    subject = models.ForeignKey(Subject, verbose_name="Дисциплина", on_delete=models.PROTECT, null=True, blank=True)
    starts_on = models.DateField("Начало", default=timezone.localdate)
    ends_on = models.DateField("Срок")
    target_minutes = models.PositiveIntegerField("Целевое время, минут", validators=[MinValueValidator(1), MaxValueValidator(525600)])
    is_archived = models.BooleanField("В архиве", default=False)

    class Meta:
        ordering = ["is_archived", "ends_on", "pk"]
        constraints = [models.CheckConstraint(condition=models.Q(target_minutes__gt=0), name="goal_positive_target"),
                       models.CheckConstraint(condition=models.Q(ends_on__gte=models.F("starts_on")), name="goal_valid_period")]

    def clean(self):
        if self.subject_id and not Subject.objects.filter(pk=self.subject_id, owner_id=self.owner_id).exists():
            raise ValidationError({"subject": "Выберите собственную дисциплину."})
        if self.starts_on and self.ends_on and not 0 <= (self.ends_on-self.starts_on).days <= 366:
            raise ValidationError({"ends_on": "Укажите период от одного до 367 дней."})

    def __str__(self):
        return self.title


class StudySession(models.Model):
    class Status(models.TextChoices):
        PLANNED = "planned", "Запланирована"
        COMPLETED = "completed", "Завершена"
        CANCELLED = "cancelled", "Отменена"

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    task = models.ForeignKey(Task, verbose_name="Задача", on_delete=models.PROTECT, related_name="study_sessions")
    starts_at = models.DateTimeField("Начало занятия")
    planned_minutes = models.PositiveSmallIntegerField("Длительность, минут", default=25, validators=[MinValueValidator(1), MaxValueValidator(240)])
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PLANNED)
    time_entry = models.OneToOneField(TimeEntry, on_delete=models.PROTECT, null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["starts_at", "pk"]
        constraints = [models.CheckConstraint(condition=models.Q(planned_minutes__gte=1, planned_minutes__lte=240), name="session_valid_plan"),
            models.CheckConstraint(condition=(models.Q(status="completed", time_entry__isnull=False, completed_at__isnull=False)
                | models.Q(status__in=["planned", "cancelled"], time_entry__isnull=True, completed_at__isnull=True)), name="session_completion_consistent")]

    @property
    def ends_at(self):
        return self.starts_at + timedelta(minutes=self.planned_minutes)

    def clean(self):
        if self.task_id and not Task.objects.filter(pk=self.task_id, owner_id=self.owner_id).exists():
            raise ValidationError({"task": "Выберите собственную задачу."})
        if self.starts_at and self.planned_minutes and self.status != self.Status.CANCELLED:
            try:
                earliest = self.starts_at - timedelta(minutes=240)
                end = self.ends_at
            except OverflowError as exc:
                raise ValidationError({"starts_at": "Дата выходит за допустимый календарь."}) from exc
            candidates = StudySession.objects.filter(owner_id=self.owner_id, starts_at__gte=earliest, starts_at__lt=end)
            candidates = candidates.exclude(pk=self.pk).exclude(status=self.Status.CANCELLED)
            if any(item.ends_at > self.starts_at for item in candidates):
                raise ValidationError({"starts_at": "В это время уже запланировано другое занятие."})


class StudentProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="time_profile")
    display_name = models.CharField("Как к вам обращаться", max_length=120, blank=True)
    study_program = models.CharField("Образовательная программа", max_length=120, blank=True)
    course = models.PositiveSmallIntegerField("Курс", default=1, validators=[MinValueValidator(1), MaxValueValidator(6)])
    default_session_minutes = models.PositiveSmallIntegerField("Обычная длительность занятия, минут", default=25, validators=[MinValueValidator(1), MaxValueValidator(240)])
    weekly_available_minutes = models.PositiveIntegerField("Обычный недельный бюджет, минут", default=600, validators=[MaxValueValidator(10080)])


class Feedback(models.Model):
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    subject = models.CharField("Тема", max_length=150)
    email = models.EmailField("Email для связи", blank=True)
    message = models.TextField("Сообщение", max_length=3000)
    status = models.CharField(max_length=10, default="open", choices=[("open", "Новое"), ("reviewed", "В работе"), ("closed", "Закрыто")])
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]


def attachment_path(instance, filename):
    return f"attachments/{instance.owner_id}/{uuid.uuid4().hex}{Path(filename).suffix.lower()}"


class TaskAttachment(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="attachments")
    file = models.FileField("PDF или текстовый файл", upload_to=attachment_path)
    original_name = models.CharField(max_length=150)
    size = models.PositiveIntegerField()
    sha256 = models.CharField(max_length=64)
    kind = models.CharField(max_length=3, choices=[("pdf", "PDF"), ("txt", "Текст UTF-8")])
    note = models.CharField("Описание", max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        constraints = [models.UniqueConstraint(fields=["owner", "task", "sha256"], name="attachment_unique_task_content")]

    def clean(self):
        if self.task_id and not Task.objects.filter(pk=self.task_id, owner_id=self.owner_id).exists():
            raise ValidationError("Вложение должно принадлежать владельцу задачи.")


class DemoDataset(models.Model):
    owner = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    reference_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)


class PrivateFileBlob(models.Model):
    name = models.CharField(max_length=255, unique=True)
    content = models.BinaryField()
    size = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)


class TaskStateEvent(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    task = models.ForeignKey(Task, null=True, on_delete=models.SET_NULL)
    title = models.CharField(max_length=200)
    previous_done = models.BooleanField()
    is_done = models.BooleanField()
    due_date = models.DateField(null=True)
    planned_minutes = models.PositiveIntegerField()
    revision = models.PositiveIntegerField()
    recorded_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        ordering = ['-recorded_at', '-pk']


class TimeCommand(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    key = models.UUIDField(unique=True)
    payload = models.JSONField()
    entry = models.ForeignKey(TimeEntry, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
