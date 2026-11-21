from django import forms
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from .models import Feedback


class FeedbackForm(forms.ModelForm):
    website = forms.CharField(required=False, widget=forms.HiddenInput)

    class Meta:
        model = Feedback
        fields = ["subject", "email", "message"]
        widgets = {"message": forms.Textarea(attrs={"rows": 5})}


def feedback(request):
    form = FeedbackForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        now = timezone.now().timestamp()
        if form.cleaned_data.get("website"):
            return redirect("feedback")
        if now-request.session.get("feedback_submitted_at", 0) < 60:
            form.add_error(None, "Сообщение уже отправлено. Подождите минуту перед следующим.")
        else:
            item = form.save(commit=False)
            item.author = request.user if request.user.is_authenticated else None
            item.save()
            request.session["feedback_submitted_at"] = now
            messages.success(request, "Спасибо, обращение сохранено.")
            return redirect("feedback")
    return render(request, "planner/feedback.html", {"form": form})


@staff_member_required
def feedback_desk(request):
    statuses = dict(Feedback._meta.get_field("status").choices)
    if request.method == "POST":
        item = get_object_or_404(Feedback, pk=request.POST.get("pk") if str(request.POST.get("pk", "")).isdigit() else 0)
        status = request.POST.get("status")
        if status in statuses:
            item.status = status
            item.save(update_fields=["status"])
        return redirect("feedback_desk")
    status = request.GET.get("status", "open")
    items = Feedback.objects.all()
    if status in statuses:
        items = items.filter(status=status)
    return render(request, "planner/feedback_desk.html", {"page": Paginator(items, 25).get_page(request.GET.get("page")),
        "statuses": statuses.items(), "state": status})
