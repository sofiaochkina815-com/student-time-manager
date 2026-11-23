from django.contrib import admin
from django.urls import include, path
from planner import views
from planner import groups
from planner import goals
from planner import sessions
from planner.profile import profile_edit
from planner.analytics import analytics
from planner.exports import time_export, summary_export
from planner.feedback import feedback, feedback_desk
from planner.knowledge import public_page
from planner import attachments
from planner import staff
from planner.documents import study_pdf

from config.health import live, ready

from planner.research import comparison

from planner.time_corrections import time_edit, time_delete

from planner.calendar_view import month_calendar

from planner.calendar_export import calendar_export

from planner.task_history import history

from planner.workload import workload

urlpatterns = [
    path("workload/", workload, name="workload"),
    path("tasks/history/", history, name="task_history"),
    path("calendar/export.ics", calendar_export, name="calendar_export"),
    path("calendar/", month_calendar, name="month_calendar"),
    path("time/<int:pk>/edit/", time_edit, name="time_edit"),
    path("time/<int:pk>/delete/", time_delete, name="time_delete"),
    path("research/", comparison, name="comparison"),
    path("health/live/", live, name="health_live"),
    path("health/ready/", ready, name="health_ready"),
    path("admin/", admin.site.urls),
    path("accounts/register/", views.register, name="register"),
    path("accounts/", include("django.contrib.auth.urls")),
    path("tasks/", views.task_list, name="task_list"),
    path("tasks/<int:pk>/files/", attachments.attachment_list, name="attachment_list"),
    path("files/<int:pk>/download/", attachments.attachment_download, name="attachment_download"),
    path("files/<int:pk>/delete/", attachments.attachment_delete, name="attachment_delete"),
    path("week/", views.weekly_plan, name="weekly_plan"),
    path("profile/", profile_edit, name="profile_edit"),
    path("feedback/", feedback, name="feedback"),
    path("guide/<slug:slug>/", public_page, name="public_page"),
    path("cabinet/feedback/", feedback_desk, name="feedback_desk"),
    path("cabinet/", staff.dashboard, name="staff_dashboard"),
    path("cabinet/users/", staff.users, name="staff_users"),
    path("cabinet/users/<int:pk>/toggle/", staff.user_toggle, name="staff_user_toggle"),
    path("cabinet/groups/", staff.groups, name="staff_groups"),
    path("cabinet/groups/<int:pk>/revoke/", staff.group_revoke_code, name="staff_group_revoke"),
    path("cabinet/catalog/<str:kind>/", staff.catalog, name="staff_catalog"),
    path("cabinet/time/", staff.time_audit, name="staff_time"),
    path("analytics/", analytics, name="analytics"),
    path("reports/time.csv", time_export, name="time_export"),
    path("reports/study.pdf", study_pdf, name="study_pdf"),
    path("reports/summary.csv", summary_export, name="summary_export"),
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
