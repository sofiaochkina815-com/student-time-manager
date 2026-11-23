"""Наблюдаемые переходы статуса с явной границей начала журнала."""
from datetime import datetime,time,timedelta
from django.db.models import Count,Min,Q
from django.utils import timezone
from .models import TaskStateEvent


def history_statistics(user, periods):
    events=TaskStateEvent.objects.filter(owner=user)
    first=events.aggregate(first=Min('recorded_at'))['first']
    labels={'full':'Полный период','partial':'Часть периода','before':'Наблюдение ещё не началось','unavailable':'Нет сохранённых переходов'}
    result=[]
    for period in periods:
        start=timezone.make_aware(datetime.combine(period['start'],time.min))
        end=timezone.make_aware(datetime.combine(period['end']+timedelta(days=1),time.min))
        coverage='unavailable' if first is None else 'before' if first>=end else 'partial' if first>start else 'full'
        counts=events.filter(recorded_at__gte=start,recorded_at__lt=end).aggregate(
            completions=Count('pk',filter=Q(is_done=True)),reopenings=Count('pk',filter=Q(is_done=False)))
        if coverage in {'unavailable','before'}:
            counts={key:None for key in counts}
        result.append({**counts,'coverage':coverage,'coverage_label':labels[coverage],
                       'start':period['start'],'end':period['end']})
    comparable=all(period['coverage']=='full' for period in result)
    return {'first_observed_at':first,'periods':result,'comparable':comparable,
            'deltas':{key:result[1][key]-result[0][key] if comparable else None for key in ['completions','reopenings']}}
