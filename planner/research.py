"""Сравнение личного учёта двух равных периодов без причинных выводов."""
from datetime import timedelta
from decimal import Decimal
from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from .models import TimeEntry, Task


class ComparisonForm(forms.Form):
    before_start = forms.DateField(label="Первый период: с", widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}))
    before_end = forms.DateField(label="Первый период: по", widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}))
    after_start = forms.DateField(label="Второй период: с", widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}))
    after_end = forms.DateField(label="Второй период: по", widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}))

    def clean(self):
        data = super().clean()
        if len(data) != 4:
            return data
        first = (data["before_end"]-data["before_start"]).days+1
        second = (data["after_end"]-data["after_start"]).days+1
        if not 1 <= first <= 93 or first != second:
            raise forms.ValidationError("Периоды должны иметь одинаковую длину от 1 до 93 дней.")
        if data["after_start"] <= data["before_end"]:
            raise forms.ValidationError("Второй период должен идти после первого без пересечения.")
        if data["after_end"] > timezone.localdate():
            raise forms.ValidationError("Сравнивайте фактические периоды не позже сегодняшнего дня.")
        return data


def compare_periods(user, **values):
    form = ComparisonForm(values)
    if not form.is_valid():
        raise ValidationError(form.errors.as_text())
    values = form.cleaned_data
    periods = []
    for prefix in ("before", "after"):
        start, end = values[prefix+"_start"], values[prefix+"_end"]
        length = (end-start).days+1
        entries = list(TimeEntry.objects.filter(task__owner=user, date__range=(start, end)).values_list("date", "minutes"))
        plans = list(Task.objects.filter(owner=user, due_date__range=(start, end)).values_list("planned_minutes", flat=True))
        actual = sum(minutes for day, minutes in entries)
        periods.append({"start": start, "end": end, "length": length,
            "actual": actual, "entries": len(entries), "active_days": len({day for day, minutes in entries}),
            "per_day": Decimal(actual)/length, "planned": sum(plans), "tasks": len(plans)})
    labels = {"actual": "Записано минут", "entries": "Записей времени", "active_days": "Дней с записями",
        "per_day": "Минут в среднем на календарный день", "planned": "План минут по дедлайнам", "tasks": "Задач с дедлайном"}
    rows = []
    for key, label in labels.items():
        first, second = periods[0][key], periods[1][key]
        rows.append({"key": key, "label": label, "before": first, "after": second,
            "delta": second-first, "relative_percent": Decimal(second-first)*100/first if first else None})
    return {"schema_version": 1, "periods": periods, "rows": rows,
        "limitations": ["Self-reported records; missing records do not prove absence of work.",
            "Current task estimates and deadlines are mutable, not historical snapshots.",
            "A change in recorded time does not measure learning quality or the causal effect of the application.",
            "Relative change is undefined when the first value is zero."]}


@login_required
def comparison(request):
    today = timezone.localdate()
    defaults = {"before_start": today-timedelta(days=13), "before_end": today-timedelta(days=7),
        "after_start": today-timedelta(days=6), "after_end": today}
    form = ComparisonForm(request.GET if request.GET else defaults)
    report = compare_periods(request.user, **form.cleaned_data) if form.is_valid() else None
    if request.GET.get("format") == "json" and report:
        response = JsonResponse(report, json_dumps_params={"ensure_ascii": False})
        response["Content-Disposition"] = 'attachment; filename="study-period-comparison.json"'
        response["Cache-Control"] = "private, no-store"
        return response
    query = request.GET.copy(); query["format"] = "json"
    if not request.GET:
        for key,value in defaults.items(): query[key] = value.isoformat()
    return render(request, "planner/comparison.html", {"form": form, "report": report, "export_query": query.urlencode()})
