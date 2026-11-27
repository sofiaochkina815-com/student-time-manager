"""Явное сохранение текущей нагрузки без пересчёта прошлых снимков."""
import hashlib
import json
from datetime import timedelta
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from .models import WorkloadSnapshot
from .snapshot_validation import valid_snapshot
from .workload import WorkloadForm, workload_snapshot

LIMIT=100


class CaptureForm(WorkloadForm):
    command_key=forms.UUIDField(widget=forms.HiddenInput)


def digest(payload):
    return hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()


@transaction.atomic
def capture(user, values):
    if not get_user_model().objects.select_for_update().get(pk=user.pk).is_active:
        raise PermissionDenied
    key=forms.UUIDField().clean(values.get('command_key'))
    day=forms.DateField().clean(values.get('week'))
    week=day-timedelta(days=day.weekday())
    existing=WorkloadSnapshot.objects.filter(owner=user,command_key=key).first()
    if existing:
        if existing.week_start!=week:
            raise ValidationError('Ключ уже использован для другой недели. Откройте расчёт заново.')
        return existing
    form=CaptureForm(values)
    if not form.is_valid():
        raise ValidationError(form.errors.as_text())
    data=form.cleaned_data
    if WorkloadSnapshot.objects.filter(owner=user).count()>=LIMIT:
        raise ValidationError('Достигнут предел 100 снимков. Скачайте нужные и удалите лишние.')
    report=workload_snapshot(user,data['week'])
    rows=[]
    for row in report.pop('rows'):
        task=row['task']
        rows.append({'task_id':task.pk,'title':task.title,'due_date':task.due_date,
            'planned':task.planned_minutes,'spent':row['spent'],'remaining':row['remaining'],'backlog':row['backlog']})
    report.update(schema_version=1,rows=rows,limitations=[
        'Captured current unfinished tasks and current estimates; this is not a reconstructed past plan.',
        'Recorded minutes are self-reported and do not measure learning quality.',
        'Deleted snapshots may be recreated only by a new explicit capture; no permanent command journal is kept.'])
    payload=json.loads(json.dumps(report,cls=DjangoJSONEncoder,ensure_ascii=False))
    return WorkloadSnapshot.objects.create(owner=user,command_key=data['command_key'],week_start=data['week'],payload=payload,sha256=digest(payload))


@login_required
def snapshot_list(request):
    page=Paginator(WorkloadSnapshot.objects.filter(owner=request.user),20).get_page(request.GET.get('page'))
    return render(request,'planner/snapshots.html',{'page':page})


@login_required
@require_POST
def snapshot_capture(request):
    try:
        item=capture(request.user,request.POST)
    except ValidationError as exc:
        return render(request,'planner/snapshots.html',{'errors':exc.messages},status=400)
    return redirect('snapshot_detail',pk=item.pk)


@login_required
def snapshot_detail(request,pk):
    item=get_object_or_404(WorkloadSnapshot,owner=request.user,pk=pk)
    if not valid_snapshot(item.payload) or digest(item.payload)!=item.sha256:
        return render(request,'planner/snapshots.html',{'errors':['Нарушена целостность снимка. Содержимое не показано.']},status=409)
    if request.GET.get('format')=='json':
        response=JsonResponse({'sha256':item.sha256,'payload':item.payload},json_dumps_params={'ensure_ascii':False})
        response['Content-Disposition']=f'attachment; filename="workload-snapshot-{item.pk}.json"'
        response['Cache-Control']='private, no-store'
        return response
    return render(request,'planner/snapshot_detail.html',{'snapshot':item,'report':item.payload,'page':Paginator(item.payload['rows'],50).get_page(request.GET.get('page'))})


@login_required
@require_POST
@transaction.atomic
def snapshot_delete(request,pk):
    if not get_user_model().objects.select_for_update().get(pk=request.user.pk).is_active:
        raise PermissionDenied
    item=get_object_or_404(WorkloadSnapshot,owner=request.user,pk=pk)
    if request.POST.get('confirm')!=str(item.pk):
        return render(request,'planner/snapshots.html',{'errors':['Удаление не подтверждено.']},status=400)
    item.delete()
    return redirect('snapshot_list')
