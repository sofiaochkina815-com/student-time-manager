"""Личный месячный календарь: текущие дедлайны, сессии и фактическое время."""
import calendar
from decimal import Decimal
from datetime import datetime, time, timedelta, timezone as dt_timezone
from django import forms
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import render
from django.utils import timezone
from .models import Task, StudySession, TimeEntry

LIMIT = 1000


class MonthForm(forms.Form):
    month = forms.DateField(label='Месяц', input_formats=['%Y-%m'], widget=forms.DateInput(format='%Y-%m',attrs={'type':'month'}))

    def clean_month(self):
        value=self.cleaned_data['month']
        if not 1900<=value.year<=2100:raise forms.ValidationError('Выберите год от1900 до2100.')
        return value.replace(day=1)


def month_data(user, start):
    end=(start.replace(day=28)+timedelta(days=4)).replace(day=1)
    zone=timezone.get_current_timezone()
    boundary=lambda day:timezone.make_aware(datetime.combine(day,time.min),zone).astimezone(dt_timezone.utc)
    first,last=boundary(start),boundary(end)
    tasks=list(Task.objects.filter(owner=user,due_date__gte=start,due_date__lt=end).select_related('subject').order_by('due_date','-priority','pk')[:LIMIT+1])
    sessions=list(StudySession.objects.filter(owner=user,starts_at__gte=first-timedelta(hours=4),starts_at__lt=last).select_related('task').order_by('starts_at','pk')[:LIMIT+1])
    truncated=len(tasks)>LIMIT or len(sessions)>LIMIT
    facts={row['date']:row['minutes'] for row in TimeEntry.objects.filter(task__owner=user,date__gte=start,date__lt=end).values('date').annotate(minutes=Sum('minutes'))}
    days={}
    for offset in range((end-start).days):
        day=start+timedelta(days=offset)
        days[day]={'date':day,'tasks':[],'sessions':[],'actual_minutes':facts.get(day,0),'today':day==timezone.localdate()}
    for task in tasks[:LIMIT]:days[task.due_date]['tasks'].append(task)
    for session in sessions[:LIMIT]:
        cursor=max(timezone.localdate(session.starts_at),start)
        final=min(timezone.localdate(session.ends_at-timedelta(microseconds=1)),end-timedelta(days=1))
        while cursor<=final:
            left=max(session.starts_at,boundary(cursor));right=min(session.ends_at,boundary(cursor+timedelta(days=1)))
            if right>left:
                duration=right-left
                microseconds=(duration.days*86400+duration.seconds)*1_000_000+duration.microseconds
                days[cursor]['sessions'].append({'session':session,'starts_at':left,'ends_at':right,
                    'minutes':Decimal(microseconds)/Decimal(60_000_000)})
            cursor+=timedelta(days=1)
    weeks=[[days.get(day) for day in week] for week in calendar.Calendar(0).monthdatescalendar(start.year,start.month)]
    return {'month':start,'weeks':weeks,'truncated':truncated,
        'previous':None if start.year==1900 and start.month==1 else (start-timedelta(days=1)).replace(day=1),
        'next':None if start.year==2100 and start.month==12 else end}


@login_required
def month_calendar(request):
    form=MonthForm(request.GET if request.GET else {'month':timezone.localdate().strftime('%Y-%m')})
    report=month_data(request.user,form.cleaned_data['month']) if form.is_valid() else None
    return render(request,'planner/calendar.html',{'form':form,'report':report})
