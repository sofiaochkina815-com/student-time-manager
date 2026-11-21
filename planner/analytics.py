"""Описательная аналитика личного учёта; причинный эффект приложения не оценивает."""
from datetime import timedelta
from decimal import Decimal
from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Sum
from django.shortcuts import render
from django.utils import timezone
from .models import Task, TimeEntry


class StudyPeriodForm(forms.Form):
    start = forms.DateField(label="С даты", widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}))
    end = forms.DateField(label="По дату", widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}))

    def clean(self):
        values = super().clean()
        if values.get("start") and values.get("end") and not 0 <= (values["end"]-values["start"]).days <= 92:
            self.add_error("end", "Выберите период от одного до 93 дней.")
        return values


def study_report(user, start, end):
    if not 0 <= (end-start).days <= 92:
        raise ValidationError("Недопустимый период аналитики.")
    tasks = Task.objects.filter(owner=user, due_date__range=(start, end))
    times = TimeEntry.objects.filter(task__owner=user, date__range=(start, end))
    planned = dict(tasks.values("due_date").annotate(total=Sum("planned_minutes")).values_list("due_date", "total"))
    actual = dict(times.values("date").annotate(total=Sum("minutes")).values_list("date", "total"))
    days = [{"date": start+timedelta(days=offset), "planned": planned.get(start+timedelta(days=offset), 0),
        "actual": actual.get(start+timedelta(days=offset), 0)} for offset in range((end-start).days+1)]
    peak = max((max(day["actual"], day["planned"]) for day in days), default=0)
    for day in days:
        day["planned_width"] = f"{day['planned']*100/peak:.2f}" if peak else "0"
        day["actual_width"] = f"{day['actual']*100/peak:.2f}" if peak else "0"
    estimates = list(tasks.filter(is_done=True).annotate(recorded=Sum("time_entries__minutes")).filter(recorded__gt=0))
    mae = sum(abs(task.recorded-task.planned_minutes) for task in estimates)/Decimal(len(estimates)) if estimates else None
    return {"start": start, "end": end, "days": days, "planned": sum(planned.values()), "actual": sum(actual.values()),
        "task_count": tasks.count(), "completed_count": tasks.filter(is_done=True).count(),
        "overdue_count": tasks.filter(is_done=False, due_date__lt=timezone.localdate()).count(),
        "estimate_count": len(estimates), "mae": mae,
        "subjects": list(times.values("task__subject__name").annotate(minutes=Sum("minutes")).order_by("-minutes"))}


def period_values(request):
    today = timezone.localdate()
    return request.GET if request.GET else {"start": today.replace(day=1), "end": today}


@login_required
def analytics(request):
    form = StudyPeriodForm(period_values(request))
    report = study_report(request.user, **form.cleaned_data) if form.is_valid() else None
    return render(request, "planner/analytics.html", {"form": form, "report": report, "export_query": request.GET.urlencode()})
