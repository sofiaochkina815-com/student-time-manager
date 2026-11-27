"""Проверка сохранённого отчёта до показа или выгрузки."""
from datetime import date,datetime,timedelta


def valid_snapshot(value):
    try:
        if not isinstance(value,dict) or value.get('schema_version')!=1:return False
        start=date.fromisoformat(value['start']);end=date.fromisoformat(value['end'])
        if end-start!=timedelta(days=6):return False
        if datetime.fromisoformat(value['generated_at']).tzinfo is None:return False
        rows=value['rows']
        if not isinstance(rows,list) or len(rows)>2000:return False
        for row in rows:
            if not isinstance(row,dict):return False
            if type(row['task_id']) is not int or row['task_id']<=0:return False
            if not isinstance(row['title'],str) or not 1<=len(row['title'])<=200:return False
            if date.fromisoformat(row['due_date'])>end:return False
            if type(row['backlog']) is not bool:return False
            if row['backlog']!=(date.fromisoformat(row['due_date'])<start):return False
            if any(type(row[key]) is not int or row[key]<0 for key in ['planned','spent','remaining']):return False
            if row['remaining']!=max(0,row['planned']-row['spent']):return False
        for key in ['required','backlog','actual','undated']:
            if type(value[key]) is not int or value[key]<0:return False
        if value['required']!=sum(row['remaining'] for row in rows):return False
        if value['backlog']!=sum(row['remaining'] for row in rows if row['backlog']):return False
        for key in ['capacity','available','gap']:
            if value[key] is not None and (type(value[key]) is not int or value[key]<0):return False
        if value['capacity'] is None:return value['available'] is None and value['gap'] is None
        return value['available']==max(0,value['capacity']-value['actual']) and value['gap']==max(0,value['required']-value['available'])
    except (KeyError,ValueError,TypeError,OverflowError):return False
