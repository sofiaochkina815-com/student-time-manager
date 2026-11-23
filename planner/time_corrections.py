from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from .forms import TimeEntryForm
from .models import TimeEntry
from .services import correct_time


@login_required
def time_edit(request, pk):
    entry = get_object_or_404(TimeEntry.objects.select_related("task"), pk=pk, task__owner=request.user)
    form = TimeEntryForm(request.POST if request.method == "POST" else None, instance=entry)
    if request.method == "POST" and form.is_valid():
        try:
            correct_time(user=request.user, entry_id=entry.pk, **form.cleaned_data)
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Запись времени исправлена.")
            return redirect("time_entry", pk=entry.task_id)
    return render(request, "planner/time_edit.html", {"form": form, "entry": entry})


@login_required
def time_delete(request, pk):
    entry = get_object_or_404(TimeEntry.objects.select_related("task"), pk=pk, task__owner=request.user)
    if request.method == "POST":
        try:
            correct_time(user=request.user, entry_id=entry.pk, delete=True)
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
        else:
            messages.success(request, "Запись времени удалена.")
        return redirect("time_entry", pk=entry.task_id)
    return render(request, "planner/time_delete.html", {"entry": entry})
