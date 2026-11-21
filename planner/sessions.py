"""Плановые занятия и однократное включение их результата в учёт времени."""
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError, PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from .forms import StudySessionForm, SessionCompletionForm
from .models import StudySession
from .services import record_time


@transaction.atomic
def save_session(user, session):
    get_user_model().objects.select_for_update().get(pk=user.pk)
    if session.owner_id != user.pk:
        raise PermissionDenied
    if session.pk and not StudySession.objects.filter(pk=session.pk, owner=user, status="planned").exists():
        raise ValidationError("Изменять можно только запланированное занятие.")
    session.full_clean()
    session.save()
    return session


@transaction.atomic
def finish_session(user, pk, minutes, note=""):
    get_user_model().objects.select_for_update().get(pk=user.pk)
    session = get_object_or_404(StudySession.objects.select_for_update(), pk=pk, owner=user)
    if session.status == StudySession.Status.COMPLETED:
        return session.time_entry
    if session.status != StudySession.Status.PLANNED:
        raise ValidationError("Отменённое занятие нельзя завершить.")
    if session.starts_at > timezone.now():
        raise ValidationError("Занятие ещё не началось. Фактическое время записывается после начала.")
    entry = record_time(user=user, task_id=session.task_id, date=timezone.localdate(session.starts_at), minutes=minutes, note=note)
    session.time_entry = entry
    session.status = StudySession.Status.COMPLETED
    session.completed_at = timezone.now()
    session.save(update_fields=["time_entry", "status", "completed_at"])
    return entry


@login_required
def session_list(request):
    state = request.GET.get("state", "planned")
    state = state if state in {"planned", "history", "all"} else "planned"
    sessions = StudySession.objects.filter(owner=request.user).select_related("task", "time_entry")
    if state == "planned":
        sessions = sessions.filter(status="planned")
    else:
        if state == "history":
            sessions = sessions.exclude(status="planned")
        sessions = sessions.order_by("-starts_at", "-pk")
    return render(request, "planner/sessions.html", {"state": state,
        "page": Paginator(sessions, 20).get_page(request.GET.get("page"))})


@login_required
def session_edit(request, pk=None):
    instance = get_object_or_404(StudySession, pk=pk, owner=request.user, status="planned") if pk else None
    form = StudySessionForm(request.POST if request.method == "POST" else None, instance=instance, owner=request.user)
    if request.method == "POST" and form.is_valid():
        try:
            save_session(request.user, form.save(commit=False))
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Занятие запланировано.")
            return redirect("session_list")
    return render(request, "planner/session_form.html", {"form": form, "heading": "План занятия"})


@login_required
def session_finish(request, pk):
    session = get_object_or_404(StudySession, owner=request.user, pk=pk)
    if session.status == "completed":
        return redirect("session_list")
    form = SessionCompletionForm(request.POST if request.method == "POST" else None,
        initial={"minutes": session.planned_minutes})
    if request.method == "POST" and form.is_valid():
        try:
            finish_session(request.user, pk, **form.cleaned_data)
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Занятие завершено, фактическое время добавлено к задаче.")
            return redirect("session_list")
    return render(request, "planner/session_form.html", {"form": form, "session": session, "heading": "Завершить занятие"})


@login_required
@require_POST
@transaction.atomic
def session_cancel(request, pk):
    get_user_model().objects.select_for_update().get(pk=request.user.pk)
    session = get_object_or_404(StudySession, owner=request.user, pk=pk)
    if session.status == "planned":
        session.status = "cancelled"
        session.save(update_fields=["status"])
        messages.success(request, "Занятие отменено, время в учёт не добавлено.")
    return redirect("session_list")
