from django.urls import path

from apps.hr_events import views

app_name = "hr_events"

urlpatterns = [
    path("evenements-rh/", views.hr_events_list_view, name="list"),
    path("evenements-rh/nouveau/", views.hr_event_create_view, name="create"),
    path("evenements-rh/<int:event_id>/annuler/", views.hr_event_cancel_view, name="cancel"),
    path("evenements-rh/<int:event_id>/supprimer/", views.hr_event_delete_view, name="delete"),
    path("evenements-rh/supprimer-tout/", views.hr_event_delete_all_view, name="delete_all"),
    path("evenements-rh/exporter/", views.hr_event_export_view, name="export"),
]
