from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from .forms import StudyGoalForm
from .models import StudyGoal
from .services import goal_progress


@login_required
def goal_list(request):
    goals = StudyGoal.objects.filter(owner=request.user).select_related("subject")
    show_archive = request.GET.get("archive") == "1"
    if not show_archive:
        goals = goals.filter(is_archived=False)
    page = Paginator(goals, 20).get_page(request.GET.get("page"))
    return render(request, "planner/goals.html", {"page": page, "show_archive": show_archive,
        "rows": [goal_progress(request.user, goal) for goal in page]})


@login_required
def goal_edit(request, pk=None):
    instance = get_object_or_404(StudyGoal, pk=pk, owner=request.user) if pk else None
    form = StudyGoalForm(request.POST if request.method == "POST" else None, instance=instance, owner=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Учебная цель сохранена.")
        return redirect("goal_list")
    return render(request, "planner/goal_form.html", {"form": form})


@login_required
def goal_delete(request, pk):
    goal = get_object_or_404(StudyGoal, owner=request.user, pk=pk)
    if request.method == "POST":
        goal.delete()
        messages.success(request, "Цель удалена; записи времени сохранены.")
        return redirect("goal_list")
    return render(request, "planner/goal_delete.html", {"goal": goal})
