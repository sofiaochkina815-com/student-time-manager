"""Учебные группы: доступ по приглашению, сводки только с согласия студента."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q, Sum, Count
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from .forms import StudyGroupForm, JoinGroupForm
from .models import StudyGroup, GroupMembership, TimeEntry, Task, group_invite_code


def curator_summary(user, group):
    if group.owner_id != user.pk:
        raise PermissionDenied
    members = list(group.memberships.select_related("student").order_by("student__username"))
    allowed = [item.student_id for item in members if item.share_summary]
    today = timezone.localdate()
    times = dict(TimeEntry.objects.filter(task__owner_id__in=allowed, date__range=(today.replace(day=1), today))
        .values("task__owner_id").annotate(total=Sum("minutes")).values_list("task__owner_id", "total"))
    tasks = {item["owner_id"]: item for item in Task.objects.filter(owner_id__in=allowed).values("owner_id")
        .annotate(total=Count("id"), done=Count("id", filter=Q(is_done=True)))}
    return [{"membership": item, "minutes": times.get(item.student_id, 0) if item.share_summary else None,
             "tasks": tasks.get(item.student_id, {"total": 0, "done": 0}) if item.share_summary else None} for item in members]


@login_required
def group_list(request):
    return render(request, "planner/groups.html", {"owned": StudyGroup.objects.filter(owner=request.user),
        "memberships": GroupMembership.objects.filter(student=request.user).select_related("group"), "form": JoinGroupForm()})


@login_required
def group_create(request):
    form = StudyGroupForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        group = form.save(commit=False)
        group.owner = request.user
        group.save()
        return redirect("group_detail", pk=group.pk)
    return render(request, "planner/reference_form.html", {"form": form, "heading": "Новая учебная группа", "return_name": "group_list", "section_label": "Группы"})


@login_required
@require_POST
def group_join(request):
    form = JoinGroupForm(request.POST)
    if form.is_valid():
        group = StudyGroup.objects.filter(invite_code=form.cleaned_data["code"]).first()
        if not group:
            form.add_error("code", "Код недействителен. Уточните его у куратора.")
        elif group.owner_id == request.user.pk:
            return redirect("group_detail", pk=group.pk)
        else:
            # Повторное приглашение не меняет ранее выбранное согласие.
            GroupMembership.objects.get_or_create(group=group, student=request.user,
                defaults={"share_summary": form.cleaned_data["share_summary"]})
            return redirect("group_detail", pk=group.pk)
    return render(request, "planner/groups.html", {"owned": StudyGroup.objects.filter(owner=request.user),
        "memberships": GroupMembership.objects.filter(student=request.user).select_related("group"), "form": form})


@login_required
def group_detail(request, pk):
    group = get_object_or_404(StudyGroup.objects.filter(Q(owner=request.user) | Q(memberships__student=request.user)).distinct(), pk=pk)
    curator = group.owner_id == request.user.pk
    membership = None if curator else group.memberships.get(student=request.user)
    return render(request, "planner/group_detail.html", {"group": group, "curator": curator,
        "membership": membership, "rows": curator_summary(request.user, group) if curator else None})


@login_required
@require_POST
def group_consent(request, pk):
    item = get_object_or_404(GroupMembership, group_id=pk, student=request.user)
    item.share_summary = request.POST.get("share_summary") == "on"
    item.save(update_fields=["share_summary"])
    messages.success(request, "Доступ к сводным показателям обновлён.")
    return redirect("group_detail", pk=pk)


@login_required
@require_POST
def group_leave(request, pk):
    get_object_or_404(GroupMembership, group_id=pk, student=request.user).delete()
    return redirect("group_list")


@login_required
@require_POST
def group_rotate_code(request, pk):
    group = get_object_or_404(StudyGroup, pk=pk, owner=request.user)
    group.invite_code = group_invite_code()
    group.save(update_fields=["invite_code"])
    return redirect("group_detail", pk=pk)
