from django.urls import path

from apps.mobile_api import views

app_name = "mobile_api"

urlpatterns = [
    path("auth/login/", views.login_view, name="login"),
    path("auth/logout/", views.logout_view, name="logout"),
    path("bootstrap/", views.bootstrap_view, name="bootstrap"),
    path("me/", views.me_view, name="me"),
    path("dashboard/", views.dashboard_view, name="dashboard"),
    path("requests/", views.requests_view, name="requests"),
]
