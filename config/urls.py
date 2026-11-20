from django.contrib import admin
from django.urls import include, path
from planner import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/register/", views.register, name="register"),
    path("accounts/", include("django.contrib.auth.urls")),
    path("tasks/", views.task_list, name="task_list"),
    path("tasks/new/", views.task_edit, name="task_create"),
    path("tasks/<int:pk>/edit/", views.task_edit, name="task_edit"),
    path("tasks/<int:pk>/toggle/", views.task_toggle, name="task_toggle"),
    path("tasks/<int:pk>/delete/", views.task_delete, name="task_delete"),
    path("", views.home, name="home"),
]
