from django.urls import path

from apps.administration import views

app_name = "administration"

urlpatterns = [
    path("tableau-de-bord/", views.dashboard_view, name="dashboard"),
    path("tableau-de-bord/donnees/", views.dashboard_data_view, name="dashboard_data"),
    path("demandes/", views.requests_overview_view, name="requests"),
    path("demandes/export/<str:export_format>/", views.export_requests_view, name="export_requests"),
    path("notifications/demandes/retour/", views.acknowledge_request_notification_view, name="acknowledge_request_notification"),
    path(
        "demandes/<int:request_id>/<str:action>/",
        views.request_action_view,
        name="request_action",
    ),
    path(
        "demandes/historique/<int:request_id>/supprimer/",
        views.request_history_delete_view,
        name="request_history_delete",
    ),
    path("parametres/", views.settings_view, name="settings"),
    path(
        "parametres/historique-comptes/<int:entry_id>/supprimer/",
        views.account_history_delete_view,
        name="account_history_delete",
    ),
]
