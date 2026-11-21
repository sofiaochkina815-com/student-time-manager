from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from .models import StudentProfile


class ProfileForm(forms.ModelForm):
    class Meta:
        model = StudentProfile
        fields = ["display_name", "study_program", "course", "default_session_minutes", "weekly_available_minutes"]


@login_required
def profile_edit(request):
    profile, _ = StudentProfile.objects.get_or_create(user=request.user)
    form = ProfileForm(request.POST if request.method == "POST" else None, instance=profile)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Профиль и значения для новых планов сохранены.")
        return redirect("profile_edit")
    return render(request, "planner/profile.html", {"form": form})
