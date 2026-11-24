"""Текущая оценка незавершённой работы и недельного бюджета."""
from datetime import timedelta
from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Sum
from django.shortcuts import render
from django.utils import timezone
from .models import Task, TimeEntry, WeekPlan


class WorkloadForm(forms.Form):
    week = forms.DateField(label='Любой день недели', widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}))

    def clean_week(self):
        day = self.cleaned_data['week']
        today = timezone.localdate()
        start = day-timedelta(days=day.weekday())
        if start < today-timedelta(days=today.weekday()) or start > today+timedelta(days=366):
            raise forms.ValidationError('Выберите текущую или будущую неделю в пределах года.')
        return start


def workload_snapshot(user, week):
    form = WorkloadForm({'week': week})
    if not form.is_valid():
        raise ValidationError(form.errors.as_text())
    start = form.cleaned_data['week']
    end = start+timedelta(days=6)
    tasks = Task.objects.filter(owner=user, is_done=False, due_date__lte=end)
    if tasks.count() > 2000:
        raise ValidationError('Больше 2000 незавершённых задач со сроком. Сначала уточните список; частичный расчёт не формируется.')
    rows = []
    query = tasks.annotate(spent=Sum('time_entries__minutes')).order_by('due_date', '-priority', 'pk')
    for task in query:
        spent = task.spent or 0
        rows.append({'task': task, 'spent': spent, 'remaining': max(0, task.planned_minutes-spent),
                     'backlog': task.due_date < start})
    required = sum(row['remaining'] for row in rows)
    plan = WeekPlan.objects.filter(owner=user, week_start=start).first()
    actual = TimeEntry.objects.filter(task__owner=user, date__range=(start, end)).aggregate(total=Sum('minutes'))['total'] or 0
    available = max(0, plan.capacity_minutes-actual) if plan else None
    return {'start': start, 'end': end, 'rows': rows, 'required': required,
            'backlog': sum(row['remaining'] for row in rows if row['backlog']),
            'capacity': plan.capacity_minutes if plan else None, 'actual': actual, 'available': available,
            'gap': max(0, required-available) if plan else None,
            'undated': Task.objects.filter(owner=user, is_done=False, due_date__isnull=True).count(),
            'generated_at': timezone.now()}


@login_required
def workload(request):
    form = WorkloadForm(request.GET if request.GET else {'week': timezone.localdate()})
    report = page = None
    if form.is_valid():
        try:
            report = workload_snapshot(request.user, form.cleaned_data['week'])
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            page = Paginator(report['rows'], 50).get_page(request.GET.get('page'))
    query = request.GET.copy();query.pop('page', None)
    from .snapshots import CaptureForm
    from uuid import uuid4
    capture_form = CaptureForm(initial={"week": report["start"], "command_key": uuid4()}) if report else None
    return render(request, 'planner/workload.html', {'form': form, 'report': report, 'page': page, 'query': query.urlencode(), 'capture_form':capture_form})
