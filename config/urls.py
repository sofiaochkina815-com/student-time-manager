from django.contrib import admin
from django.urls import include, path
from planner import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/register/", views.register, name="register"),
    path("accounts/", include("django.contrib.auth.urls")),
    path("", views.home, name="home"),
]
