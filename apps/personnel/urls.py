from django.urls import path

from apps.personnel import views

app_name = "personnel"

urlpatterns = [
    path("tableau-de-bord/", views.dashboard_view, name="dashboard"),
    path("tableau-de-bord/donnees/", views.dashboard_data_view, name="dashboard_data"),
    path("photo-profil/modifier/", views.update_profile_photo_view, name="update_profile_photo"),
]
