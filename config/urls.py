from django.contrib import admin
from django.urls import include, path
from planner import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/register/", views.register, name="register"),
    path("accounts/", include("django.contrib.auth.urls")),
    path("tasks/", views.task_list, name="task_list"),
    path("week/", views.weekly_plan, name="weekly_plan"),
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
