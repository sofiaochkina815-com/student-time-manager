"""Административный кабинет с агрегатами и ограниченными действиями модерации."""
from django import forms
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from .analytics import StudyPeriodForm, period_values
from .models import Task, TimeEntry, Subject, TaskCategory, StudyGroup, Feedback, group_invite_code


class SearchForm(forms.Form):
    q = forms.CharField(label="Поиск", max_length=150, required=False)


@staff_member_required
def dashboard(request):
    return render(request, "planner/staff_dashboard.html", {"counts": {
        "Студенты": get_user_model().objects.filter(is_staff=False).count(), "Задачи": Task.objects.count(),
        "Учебные группы": StudyGroup.objects.count(), "Новые обращения": Feedback.objects.filter(status="open").count()}})


@staff_member_required
def users(request):
    form = SearchForm(request.GET)
    query = get_user_model().objects.order_by("username", "pk")
    query = query.filter(username__icontains=form.cleaned_data["q"]) if form.is_valid() else query.none()
    return render(request, "planner/staff_users.html", {"form": form, "page": Paginator(query, 30).get_page(request.GET.get("page")), "q": request.GET.get("q", "")})


@staff_member_required
@require_POST
@transaction.atomic
def user_toggle(request, pk):
    target = get_object_or_404(get_user_model().objects.select_for_update(), pk=pk)
    if target.is_staff or target.pk == request.user.pk:
        messages.error(request, "Состояние административного аккаунта здесь не изменяется.")
    else:
        target.is_active = not target.is_active
        target.save(update_fields=["is_active"])
    return redirect("staff_users")


@staff_member_required
def groups(request):
    form = SearchForm(request.GET)
    query = StudyGroup.objects.select_related("owner").annotate(students=Count("memberships")).order_by("name", "pk")
    query = query.filter(name__icontains=form.cleaned_data["q"]) if form.is_valid() else query.none()
    return render(request, "planner/staff_groups.html", {"form": form, "page": Paginator(query, 30).get_page(request.GET.get("page")), "q": request.GET.get("q", "")})


@staff_member_required
@require_POST
def group_revoke_code(request, pk):
    group = get_object_or_404(StudyGroup, pk=pk)
    group.invite_code = group_invite_code()
    group.save(update_fields=["invite_code"])
    messages.success(request, "Старое приглашение закрыто; новый код доступен создателю группы.")
    return redirect("staff_groups")


@staff_member_required
def catalog(request, kind):
    from django.http import Http404
    model, title = {"subjects": (Subject, "Дисциплины"), "categories": (TaskCategory, "Категории задач")}.get(kind, (None, None))
    if model is None:
        raise Http404
    form = SearchForm(request.GET)
    query = model.objects.select_related("owner").annotate(task_count=Count("task")).order_by("name", "pk")
    query = query.filter(name__icontains=form.cleaned_data["q"]) if form.is_valid() else query.none()
    return render(request, "planner/staff_catalog.html", {"form": form, "title": title,
        "page": Paginator(query, 30).get_page(request.GET.get("page")), "q": request.GET.get("q", "")})


@staff_member_required
def time_audit(request):
    form = StudyPeriodForm(period_values(request))
    query = TimeEntry.objects.none()
    if form.is_valid():
        query = TimeEntry.objects.filter(date__range=(form.cleaned_data["start"], form.cleaned_data["end"]))
    query = query.values("task__owner__username", "date").annotate(minutes=Sum("minutes"), records=Count("id")).order_by("-date", "task__owner__username")
    page = Paginator(query, 30).get_page(request.GET.get("page"))
    for row in page:
        row["invalid"] = row["minutes"] > 1440 or row["date"] > timezone.localdate()
    params = request.GET.copy();params.pop("page", None)
    return render(request, "planner/staff_time.html", {"form": form, "page": page, "page_query": params.urlencode()})
