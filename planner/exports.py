import csv
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseBadRequest
from .analytics import StudyPeriodForm, period_values, study_report
from .models import TimeEntry


def safe_cell(value):
    value = str(value or "")
    return "'"+value if value.lstrip().startswith(("=", "+", "-", "@")) else value


@login_required
def time_export(request):
    form = StudyPeriodForm(period_values(request))
    if not form.is_valid():
        return HttpResponseBadRequest(form.errors.as_text(), content_type="text/plain; charset=utf-8")
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="study-time.csv"'
    response.write("\ufeff")
    writer = csv.writer(response, delimiter=";", lineterminator="\n")
    writer.writerow(["date", "task", "subject", "minutes", "note"])
    for entry in TimeEntry.objects.filter(task__owner=request.user, date__range=(form.cleaned_data["start"], form.cleaned_data["end"])).select_related("task__subject").iterator():
        writer.writerow([entry.date.isoformat(), safe_cell(entry.task.title), safe_cell(entry.task.subject), entry.minutes, safe_cell(entry.note)])
    return response


@login_required
def summary_export(request):
    form = StudyPeriodForm(period_values(request))
    if not form.is_valid():
        return HttpResponseBadRequest(form.errors.as_text(), content_type="text/plain; charset=utf-8")
    report = study_report(request.user, **form.cleaned_data)
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="study-summary.csv"'
    response.write("\ufeff")
    writer = csv.writer(response, delimiter=";", lineterminator="\n")
    writer.writerow(["date", "planned_by_deadline_minutes", "actual_minutes"])
    for day in report["days"]:
        writer.writerow([day["date"].isoformat(), day["planned"], day["actual"]])
    return response
