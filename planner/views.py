from .task_editing import save_task,EDITABLE_TASK_FIELDS
import uuid
from .forms import ManualTimeForm
from .task_history import StateForm, set_task_state
from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import F, Q, IntegerField, Sum, Value
from django.core.paginator import Paginator
from django.db.models.functions import Coalesce
from django.core.exceptions import ValidationError
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from .forms import TaskForm, TimeEntryForm, SubjectForm, CategoryForm, TaskFilterForm, WeekPlanForm
from .models import Task, TimeEntry, Subject, TaskCategory, WeekPlan, StudentProfile
from django.http import Http404
from .services import record_time, week_summary
from datetime import timedelta
from django.utils.dateparse import parse_date


def home(request):
    return render(request, "planner/home.html")


def register(request):
    if request.user.is_authenticated:
        return redirect("home")
    form = UserCreationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        login(request, form.save())
        return redirect("home")
    return render(request, "registration/register.html", {"form": form})


@login_required
def task_list(request):
    tasks = Task.objects.filter(owner=request.user)
    state = request.GET.get("state", "active")
    if state not in {"active", "done", "all"}:
        state = "active"
    active = tasks.filter(is_done=False)
    context = {
        "active_count": active.count(), "done_count": tasks.filter(is_done=True).count(),
        "planned_minutes": active.aggregate(total=Sum("planned_minutes"))["total"] or 0,
        "state": state,
        "actual_minutes": TimeEntry.objects.filter(task__owner=request.user).aggregate(total=Sum("minutes"))["total"] or 0,
    }
    if state != "all":
        tasks = tasks.filter(is_done=state == "done")
    filters = TaskFilterForm(request.GET, owner=request.user)
    ordering = ["-priority", "created_at", "pk"]
    if filters.is_valid():
        data = filters.cleaned_data
        if data["unassigned_subject"]:
            tasks=tasks.filter(subject__isnull=True)
        if data["q"]:
            tasks = tasks.filter(Q(title__icontains=data["q"]) | Q(description__icontains=data["q"]))
        for field in ["subject", "category"]:
            if data[field]:
                tasks = tasks.filter(**{field: data[field]})
        if data["sort"] == "deadline":
            ordering = [F("due_date").asc(nulls_last=True), "-priority", "pk"]
        elif data["sort"] == "newest":
            ordering = ["-created_at", "-pk"]
    else:
        tasks = tasks.none()
    tasks = tasks.select_related("subject", "category").annotate(spent_minutes=Coalesce(Sum("time_entries__minutes"), Value(0), output_field=IntegerField())).order_by(*ordering)
    page = Paginator(tasks, 20).get_page(request.GET.get("page"))
    params = request.GET.copy()
    params.pop("page", None)
    links = {}
    for value in ["active", "done", "all"]:
        params["state"] = value
        links[value] = "?" + params.urlencode()
    params["state"] = state
    context.update({"tasks": page.object_list, "page": page, "filters": filters, "state_links": links, "page_query": params.urlencode()})
    context["today"] = timezone.localdate()
    return render(request, "planner/tasks.html", context)


@login_required
def task_edit(request, pk=None):
    task = get_object_or_404(Task, pk=pk, owner=request.user) if pk else None
    form = TaskForm(request.POST if request.method == "POST" else None, instance=task, owner=request.user)
    if request.method == "POST" and form.is_valid():
        try:
            task=save_task(request.user,{key:form.cleaned_data[key] for key in EDITABLE_TASK_FIELDS},
                           task_id=pk,expected_updated_at=form.cleaned_data.get('expected_updated_at'))
        except ValidationError as exc:
            form.add_error(None,exc)
        else:
            messages.success(request, "Задача сохранена.")
            return redirect("task_list")
    return render(request, "planner/task_form.html", {"form": form, "task": task})


@login_required
@require_POST
def task_toggle(request, pk):
    task = get_object_or_404(Task, pk=pk, owner=request.user)
    form = StateForm(request.POST)
    if form.is_valid():
        try:
            set_task_state(request.user, task.pk, **form.cleaned_data)
        except ValidationError as exc:
            messages.error(request, str(exc.messages[0]))
    else:
        messages.error(request, 'Некорректная форма статуса. Обновите страницу.')
    return redirect("task_list")


@login_required
def task_delete(request, pk):
    task = get_object_or_404(Task, pk=pk, owner=request.user)
    if request.method == "POST":
        try:
            task.delete()
        except ProtectedError:
            messages.error(request, "С задачей связаны учебные сессии. Сохраните историю, отметив задачу завершённой.")
        else:
            messages.success(request, "Задача удалена.")
        return redirect("task_list")
    return render(request, "planner/task_confirm_delete.html", {"task": task})


@login_required
def time_entry(request, pk):
    task = get_object_or_404(Task, pk=pk, owner=request.user)
    form = ManualTimeForm(request.POST if request.method == "POST" else None, initial={"command_key": uuid.uuid4()})
    if request.method == "POST" and form.is_valid():
        try:
            record_time(user=request.user, task_id=task.pk, **form.cleaned_data)
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Время записано.")
            return redirect("task_list")
    return render(request, "planner/time_entry.html", {"form": form, "task": task, "entries": task.time_entries.all()})


@login_required
def references(request):
    return render(request, "planner/references.html", {"subjects": Subject.objects.filter(owner=request.user), "categories": TaskCategory.objects.filter(owner=request.user)})


def reference_type(kind):
    if kind == "subjects":
        return Subject, SubjectForm, "Дисциплина"
    if kind == "categories":
        return TaskCategory, CategoryForm, "Категория"
    raise Http404


@login_required
def reference_edit(request, kind, pk=None):
    model, form_class, heading = reference_type(kind)
    instance = get_object_or_404(model, pk=pk, owner=request.user) if pk else None
    form = form_class(request.POST if request.method == "POST" else None, owner=request.user, instance=instance)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Справочник сохранён.")
        return redirect("references")
    return render(request, "planner/reference_form.html", {"form": form, "heading": heading})


@login_required
def reference_delete(request, kind, pk):
    model, _, _ = reference_type(kind)
    instance = get_object_or_404(model, pk=pk, owner=request.user)
    if request.method == "POST":
        try:
            instance.delete()
        except ProtectedError:
            messages.error(request, "Дисциплина используется в учебной цели. Сначала измените или удалите цель.")
        else:
            messages.success(request, "Справочник удалён. Учебные задачи сохранены.")
        return redirect("references")
    return render(request, "planner/reference_delete.html", {"instance": instance})


@login_required
def weekly_plan(request):
    try:
        selected = parse_date(request.GET.get("week", "")) or timezone.localdate()
    except ValueError:
        selected = timezone.localdate()
    start = selected - timedelta(days=selected.weekday())
    instance = WeekPlan.objects.filter(owner=request.user, week_start=start).first()
    if instance is None:
        profile = StudentProfile.objects.filter(user=request.user).first()
        instance = WeekPlan(owner=request.user, week_start=start, capacity_minutes=profile.weekly_available_minutes if profile else 600)
    form = WeekPlanForm(request.POST if request.method == "POST" else None, instance=instance)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Бюджет учебного времени сохранён.")
        return redirect(f"{request.path}?week={start.isoformat()}")
    return render(request, "planner/week.html", {"form": form, "summary": week_summary(request.user, start),
        "previous_week": (start-timedelta(days=7)).isoformat(), "next_week": (start+timedelta(days=7)).isoformat()})
