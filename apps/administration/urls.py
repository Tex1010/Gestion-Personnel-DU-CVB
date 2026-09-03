from django.urls import path

from apps.administration import views
from apps.administration.calendar_views import (
    calendar_employee_search_view,
    calendar_view,
)

app_name = "administration"

urlpatterns = [
    path("calendrier/", calendar_view, name="calendar"),
    path("calendrier/employes/recherche/", calendar_employee_search_view, name="calendar_employee_search"),
    path("tableau-de-bord/", views.dashboard_view, name="dashboard"),
    path("tableau-de-bord/donnees/", views.dashboard_data_view, name="dashboard_data"),
    path("presence/", views.presence_overview_view, name="presence_overview"),
    path(
        "presence/donnees/",
        views.presence_overview_data_view,
        name="presence_overview_data",
    ),
    path("exports/<str:table_key>/", views.export_table_view, name="export_table"),
    path("demandes/", views.requests_overview_view, name="requests"),
    path("demandes/donnees/", views.requests_overview_data_view, name="requests_overview_data"),
    path("demandes/export/<str:export_format>/", views.export_requests_view, name="export_requests"),
    path("absences-exceptionnelles/", views.exceptional_absences_view, name="exceptional_absences"),
    path("absences-exceptionnelles/donnees/", views.exceptional_absences_data_view, name="exceptional_absences_data"),
    path("absences-exceptionnelles/<int:request_id>/", views.exceptional_absence_detail_view, name="exceptional_absence_detail"),
    path("absences-exceptionnelles/<int:request_id>/imprimer/", views.exceptional_absence_print_view, name="exceptional_absence_print"),
    path("absences-exceptionnelles/<int:request_id>/marquer-retenue/", views.mark_salary_deduction_view, name="mark_salary_deduction"),
    path("absences-exceptionnelles/<int:request_id>/<str:action>/", views.request_action_view, name="exceptional_absence_action"),
    path("notifications/demandes/etat/", views.request_notifications_state_view, name="request_notifications_state"),
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
    path("notifications/", views.notifications_view, name="notifications"),
    path("notifications/donnees/", views.notifications_data_view, name="notifications_data"),
    path("notifications/<int:notification_id>/lue/", views.notification_mark_read_view, name="notification_mark_read"),
    path("notifications/toutes-lues/", views.notification_mark_all_read_view, name="notification_mark_all_read"),
    path("parametres/", views.settings_view, name="settings"),
    path("parametres/historique-comptes/<int:entry_id>/supprimer/", views.account_history_delete_view, name="account_history_delete"),
    path("logs/", views.logs_view, name="logs"),
    path("logs/donnees/", views.logs_data_view, name="logs_data"),
    path("logs/<int:log_id>/", views.log_detail_view, name="log_detail"),
    path("logs/nettoyer/", views.log_clear_old_view, name="logs_clear_old"),
    path("logs/supprimer/", views.logs_clear_view, name="logs_clear"),
]
