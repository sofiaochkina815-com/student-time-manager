from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from .models import StudentProfile
from .forms import StudySessionForm


class ProfileTests(TestCase):
    def test_private_profile_and_defaults_for_new_plans(self):
        user = get_user_model().objects.create_user("profile-user")
        other = get_user_model().objects.create_user("profile-other")
        self.client.force_login(user)
        self.client.post(reverse("profile_edit"), {"user": other.pk, "display_name": "София", "course": 3,
            "default_session_minutes": 45, "weekly_available_minutes": 900})
        self.assertEqual(StudentProfile.objects.get().user, user)
        self.assertEqual(StudySessionForm(owner=user).initial["planned_minutes"], 45)
        response = self.client.get(reverse("weekly_plan"))
        self.assertEqual(response.context["form"].instance.capacity_minutes, 900)
        self.client.post(reverse("profile_edit"), {"course": 9, "default_session_minutes": 0, "weekly_available_minutes": -1})
        self.assertEqual(StudentProfile.objects.get().course, 3)
