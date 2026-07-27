from django.urls import path

from apps.hr_events import views

app_name = "hr_events"

urlpatterns = [
    path("evenements-rh/", views.hr_events_list_view, name="list"),
    path("evenements-rh/nouveau/", views.hr_event_create_view, name="create"),
    path("evenements-rh/<int:event_id>/annuler/", views.hr_event_cancel_view, name="cancel"),
]
