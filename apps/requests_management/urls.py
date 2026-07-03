from django.urls import path

from apps.requests_management import views

app_name = "requests_management"

urlpatterns = [
    path("absence/nouvelle/", views.absence_request_view, name="absence_create"),
    path("conge/nouveau/", views.leave_request_view, name="leave_create"),
    path("recuperation/nouvelle/", views.recovery_request_view, name="recovery_create"),
    path("historique/<int:request_id>/imprimer/", views.print_request_view, name="print"),
    path("historique/<int:request_id>/supprimer/", views.delete_request_view, name="delete"),
]
