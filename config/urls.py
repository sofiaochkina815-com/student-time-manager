from django.contrib import admin
from django.urls import include, path
from planner import views
from planner import groups
from planner import goals
from planner import sessions
from planner.profile import profile_edit
from planner.analytics import analytics

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/register/", views.register, name="register"),
    path("accounts/", include("django.contrib.auth.urls")),
    path("tasks/", views.task_list, name="task_list"),
    path("week/", views.weekly_plan, name="weekly_plan"),
    path("profile/", profile_edit, name="profile_edit"),
    path("analytics/", analytics, name="analytics"),
    path("sessions/", sessions.session_list, name="session_list"),
    path("sessions/new/", sessions.session_edit, name="session_create"),
    path("sessions/<int:pk>/edit/", sessions.session_edit, name="session_edit"),
    path("sessions/<int:pk>/finish/", sessions.session_finish, name="session_finish"),
    path("sessions/<int:pk>/cancel/", sessions.session_cancel, name="session_cancel"),
    path("goals/", goals.goal_list, name="goal_list"),
    path("goals/new/", goals.goal_edit, name="goal_create"),
    path("goals/<int:pk>/edit/", goals.goal_edit, name="goal_edit"),
    path("goals/<int:pk>/delete/", goals.goal_delete, name="goal_delete"),
    path("groups/", groups.group_list, name="group_list"),
    path("groups/new/", groups.group_create, name="group_create"),
    path("groups/join/", groups.group_join, name="group_join"),
    path("groups/<int:pk>/", groups.group_detail, name="group_detail"),
    path("groups/<int:pk>/consent/", groups.group_consent, name="group_consent"),
    path("groups/<int:pk>/leave/", groups.group_leave, name="group_leave"),
    path("groups/<int:pk>/invite/", groups.group_rotate_code, name="group_rotate_code"),
    path("references/", views.references, name="references"),
    path("references/<str:kind>/new/", views.reference_edit, name="reference_create"),
    path("references/<str:kind>/<int:pk>/edit/", views.reference_edit, name="reference_edit"),
    path("references/<str:kind>/<int:pk>/delete/", views.reference_delete, name="reference_delete"),
    path("tasks/new/", views.task_edit, name="task_create"),
    path("tasks/<int:pk>/edit/", views.task_edit, name="task_edit"),
    path("tasks/<int:pk>/toggle/", views.task_toggle, name="task_toggle"),
    path("tasks/<int:pk>/delete/", views.task_delete, name="task_delete"),
    path("tasks/<int:pk>/time/", views.time_entry, name="time_entry"),
    path("", views.home, name="home"),
]
