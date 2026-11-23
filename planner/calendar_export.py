"""Приватный снимок дедлайнов и занятий iCalendar (RFC5545)."""
from datetime import datetime, time, timedelta, timezone as dt_timezone
import hashlib
import hmac
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.utils import timezone
from .calendar_view import MonthForm, LIMIT
from .models import Task, StudySession


def text(value):
    value=str(value).replace('\r\n','\n').replace('\r','\n')
    value=''.join(char for char in value if ord(char)>=32 or char in '\n\t')
    return value.replace('\\','\\\\').replace('\n','\\n').replace(';','\\;').replace(',','\\,')


def fold(line):
    parts=[];current='';size=0
    for char in line:
        width=len(char.encode('utf-8'))
        if size+width>75:
            parts.append(current);current=' ';size=1
        current+=char;size+=width
    return '\r\n'.join([*parts,current])


def uid(kind, identifier):
    digest=hmac.new(settings.SECRET_KEY.encode(),f'calendar:{kind}:{identifier}'.encode(),hashlib.sha256).hexdigest()
    return digest+'@student-time.local'


def utc(value):
    return value.astimezone(dt_timezone.utc).strftime('%Y%m%dT%H%M%SZ')


def calendar_bytes(user, start):
    end=(start.replace(day=28)+timedelta(days=4)).replace(day=1)
    zone=timezone.get_current_timezone()
    first=timezone.make_aware(datetime.combine(start,time.min),zone)
    last=timezone.make_aware(datetime.combine(end,time.min),zone)
    tasks=list(Task.objects.filter(owner=user,due_date__gte=start,due_date__lt=end).order_by('pk')[:LIMIT+1])
    sessions=[item for item in StudySession.objects.filter(owner=user,starts_at__gte=first-timedelta(hours=4),starts_at__lt=last).select_related('task').order_by('starts_at','pk')[:LIMIT+1]]
    if len(tasks)>LIMIT or len(sessions)>LIMIT:raise ValueError('За месяц больше1000 задач или занятий: выгрузка отменена, неполный файл не создан.')
    lines=['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//Student Time//Local calendar//RU','CALSCALE:GREGORIAN']
    stamp=utc(timezone.now())
    for task in tasks:
        lines.extend(['BEGIN:VEVENT','UID:'+uid('task',task.pk),'DTSTAMP:'+stamp,
            'DTSTART;VALUE=DATE:'+task.due_date.strftime('%Y%m%d'),
            'DTEND;VALUE=DATE:'+(task.due_date+timedelta(days=1)).strftime('%Y%m%d'),
            'SUMMARY:'+text('Дедлайн: '+task.title),
            'DESCRIPTION:'+text('Завершена' if task.is_done else 'Текущий дедлайн учебной задачи'),
            'TRANSP:TRANSPARENT','END:VEVENT'])
    for session in sessions:
        if session.ends_at<=first:continue
        lines.extend(['BEGIN:VEVENT','UID:'+uid('session',session.pk),'DTSTAMP:'+stamp,
            'DTSTART:'+utc(session.starts_at),'DTEND:'+utc(session.ends_at),
            'SUMMARY:'+text('Занятие: '+session.task.title),
            'DESCRIPTION:'+text(session.get_status_display()),
            'STATUS:'+('CANCELLED' if session.status=='cancelled' else 'CONFIRMED'),
            'END:VEVENT'])
    lines.append('END:VCALENDAR')
    return ('\r\n'.join(fold(line) for line in lines)+'\r\n').encode('utf-8')


@login_required
def calendar_export(request):
    form=MonthForm(request.GET)
    if not form.is_valid():return HttpResponse('Укажите корректный месяц YYYY-MM.',status=400)
    start=form.cleaned_data['month']
    try:content=calendar_bytes(request.user,start)
    except ValueError as exc:return HttpResponse(str(exc),status=400)
    response=HttpResponse(content,content_type='text/calendar; charset=utf-8')
    response['Content-Disposition']=f'attachment; filename="study-{start:%Y-%m}.ics"'
    response['Cache-Control']='private, no-store'
    return response
