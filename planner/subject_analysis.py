"""Распределение записанного времени и текущих планов по дисциплинам."""
import csv
import io
from decimal import Decimal
from urllib.parse import urlencode
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied,ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count,Q,Sum
from django.http import HttpResponse,HttpResponseBadRequest
from django.shortcuts import render
from django.utils import timezone
from .analytics import StudyPeriodForm
from .exports import safe_cell
from .models import Task,TimeEntry

MAX_SUBJECTS=2000


@transaction.atomic
def subject_report(user,start,end):
    if not get_user_model().objects.select_for_update().get(pk=user.pk).is_active:
        raise PermissionDenied
    form=StudyPeriodForm({'start':start,'end':end})
    if not form.is_valid():raise ValidationError(form.errors.as_text())
    start,end=form.cleaned_data['start'],form.cleaned_data['end']
    plans=list(Task.objects.filter(owner=user,due_date__range=(start,end)).order_by().values('subject_id','subject__name').annotate(
        tasks=Count('pk'),done=Count('pk',filter=Q(is_done=True)),planned=Sum('planned_minutes'))[:MAX_SUBJECTS+1])
    facts=list(TimeEntry.objects.filter(task__owner=user,date__range=(start,end)).order_by().values('task__subject_id','task__subject__name').annotate(
        actual=Sum('minutes'),records=Count('pk'))[:MAX_SUBJECTS+1])
    if len(plans)>MAX_SUBJECTS or len(facts)>MAX_SUBJECTS:
        raise ValidationError('Больше2000 дисциплин: сократите период. Неполный отчёт не формируется.')
    rows={}
    def row(identifier,name):
        return rows.setdefault(identifier,{'id':identifier,'name':name or 'Без дисциплины',
            'tasks':0,'done':0,'planned':0,'actual':0,'records':0})
    for item in plans:row(item['subject_id'],item['subject__name']).update({key:item[key] or 0 for key in ['tasks','done','planned']})
    for item in facts:row(item['task__subject_id'],item['task__subject__name']).update({key:item[key] or 0 for key in ['actual','records']})
    if len(rows)>MAX_SUBJECTS:raise ValidationError('Больше2000 дисциплин: сократите период.')
    totals={key:sum(item[key] for item in rows.values()) for key in ['tasks','done','planned','actual','records']}
    for item in rows.values():
        item['share']=Decimal(item['actual'])*100/totals['actual'] if totals['actual'] else Decimal(0)
        item['width']=f"{item['share']:.2f}"
        filters={'state':'all'}
        filters['subject' if item['id'] is not None else 'unassigned_subject']=item['id'] if item['id'] is not None else '1'
        item['tasks_query']=urlencode(filters)
    return {'start':start,'end':end,'rows':sorted(rows.values(),key=lambda item:(-item['actual'],item['name'].casefold(),item['id'] or 0)),
            'totals':totals,'generated_at':timezone.now()}


def subject_csv(report):
    stream=io.StringIO(newline='');writer=csv.writer(stream,delimiter=';',lineterminator='\n')
    keys=['tasks','done','planned','actual','records']
    writer.writerow(['type','subject_id','subject',*keys,'actual_share_percent','start','end','generated_at'])
    metadata=[report['start'].isoformat(),report['end'].isoformat(),report['generated_at'].isoformat()]
    writer.writerow(['summary','','Итого',*[report['totals'][key] for key in keys],'',*metadata])
    for item in report['rows']:
        writer.writerow(['subject',item['id'] if item['id'] is not None else '',safe_cell(item['name']),
                         *[item[key] for key in keys],f"{item['share']:.2f}",*metadata])
    response=HttpResponse('\ufeff'+stream.getvalue(),content_type='text/csv; charset=utf-8')
    response['Content-Disposition']='attachment; filename="study-subjects.csv"';response['Cache-Control']='private, no-store'
    return response


@login_required
def subjects(request):
    today=timezone.localdate();form=StudyPeriodForm(request.GET if request.GET else {'start':today.replace(day=1),'end':today})
    report=page=None;query=''
    if form.is_valid():
        try:report=subject_report(request.user,**form.cleaned_data)
        except ValidationError as exc:form.add_error(None,exc)
        else:
            page=Paginator(report['rows'],50).get_page(request.GET.get('page'))
            query=urlencode({key:value.isoformat() for key,value in form.cleaned_data.items()})
    if request.GET.get('format')=='csv':return subject_csv(report) if report else HttpResponseBadRequest('Проверьте период и ограничения отчёта.')
    return render(request,'planner/subject_analysis.html',{'form':form,'report':report,'page':page,'query':query})
