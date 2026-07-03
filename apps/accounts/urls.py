from django.urls import path

from apps.accounts import views

app_name = "accounts"

urlpatterns = [
    path("", views.login_view, name="login"),
    path("deconnexion/", views.logout_view, name="logout"),
    path("mot-de-passe/", views.password_change_view, name="password_change"),
]
