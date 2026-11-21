from django import forms
from django.utils import timezone
from .models import Task, TimeEntry, Subject, TaskCategory, WeekPlan, StudyGroup, StudyGoal


class StudyGoalForm(forms.ModelForm):
    class Meta:
        model = StudyGoal
        fields = ["title", "subject", "starts_on", "ends_on", "target_minutes", "is_archived"]
        widgets = {field: forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}) for field in ["starts_on", "ends_on"]}

    def __init__(self, *args, owner, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.owner = owner
        self.fields["subject"].queryset = Subject.objects.filter(owner=owner)


class StudyGroupForm(forms.ModelForm):
    class Meta:
        model = StudyGroup
        fields = ["name", "description"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}


class JoinGroupForm(forms.Form):
    code = forms.CharField(label="Код приглашения", max_length=32, strip=True)
    share_summary = forms.BooleanField(label="Разрешить куратору видеть суммарные показатели", required=False,
        help_text="Количество задач и минуты работы за текущий месяц. Названия задач и заметки не передаются.")


class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ["title", "description", "subject", "category", "due_date", "priority", "planned_minutes"]
        widgets = {
            "due_date": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "description": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, owner, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.owner = owner
        self.fields["subject"].queryset = Subject.objects.filter(owner=owner)
        self.fields["category"].queryset = TaskCategory.objects.filter(owner=owner)


class ReferenceForm(forms.ModelForm):
    def __init__(self, *args, owner, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.owner = owner

    def clean_name(self):
        name = self.cleaned_data["name"]
        if self._meta.model.objects.filter(owner=self.instance.owner, name=name).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Такое название уже используется.")
        return name


class SubjectForm(ReferenceForm):
    class Meta:
        model = Subject
        fields = ["name", "description"]


class CategoryForm(ReferenceForm):
    class Meta:
        model = TaskCategory
        fields = ["name", "description"]


class TaskFilterForm(forms.Form):
    q = forms.CharField(label="Поиск по задаче", required=False, max_length=200)
    subject = forms.ModelChoiceField(label="Дисциплина", queryset=Subject.objects.none(), required=False, empty_label="Все дисциплины")
    category = forms.ModelChoiceField(label="Категория", queryset=TaskCategory.objects.none(), required=False, empty_label="Все категории")
    sort = forms.ChoiceField(label="Порядок", required=False, choices=[("priority", "По приоритету"), ("deadline", "По дедлайну"), ("newest", "Сначала новые")])

    def __init__(self, *args, owner, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["subject"].queryset = Subject.objects.filter(owner=owner)
        self.fields["category"].queryset = TaskCategory.objects.filter(owner=owner)


class WeekPlanForm(forms.ModelForm):
    class Meta:
        model = WeekPlan
        fields = ["capacity_minutes", "note"]
        widgets = {"note": forms.Textarea(attrs={"rows": 2})}


class TimeEntryForm(forms.ModelForm):
    class Meta:
        model = TimeEntry
        fields = ["date", "minutes", "note"]
        widgets = {"date": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"})}

    def clean_date(self):
        date = self.cleaned_data["date"]
        if date > timezone.localdate():
            raise forms.ValidationError("Фактическое время нельзя записать за будущую дату.")
        return date
