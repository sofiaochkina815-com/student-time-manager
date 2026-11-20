from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from .forms import TaskForm
from .models import Task


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
    }
    if state != "all":
        tasks = tasks.filter(is_done=state == "done")
    context["tasks"] = tasks
    return render(request, "planner/tasks.html", context)


@login_required
def task_edit(request, pk=None):
    task = get_object_or_404(Task, pk=pk, owner=request.user) if pk else None
    form = TaskForm(request.POST if request.method == "POST" else None, instance=task)
    if request.method == "POST" and form.is_valid():
        task = form.save(commit=False)
        task.owner = request.user
        task.save()
        messages.success(request, "Задача сохранена.")
        return redirect("task_list")
    return render(request, "planner/task_form.html", {"form": form, "task": task})


@login_required
@require_POST
def task_toggle(request, pk):
    task = get_object_or_404(Task, pk=pk, owner=request.user)
    task.is_done = not task.is_done
    task.completed_at = timezone.now() if task.is_done else None
    task.save(update_fields=["is_done", "completed_at", "updated_at"])
    return redirect("task_list")


@login_required
def task_delete(request, pk):
    task = get_object_or_404(Task, pk=pk, owner=request.user)
    if request.method == "POST":
        task.delete()
        messages.success(request, "Задача удалена.")
        return redirect("task_list")
    return render(request, "planner/task_confirm_delete.html", {"task": task})
