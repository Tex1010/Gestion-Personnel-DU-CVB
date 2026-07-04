from apps.administration.models import LoginBranding


def branding(request):
    branding_item = LoginBranding.objects.first()
    if (
        branding_item
        and branding_item.announcement
        == "Bienvenue dans la version de demonstration de la gestion du personnel."
    ):
        branding_item.announcement = "Bienvenue dans la gestion du personnel du centre ValBio."
        branding_item.save(update_fields=["announcement"])
    floating_notification = None
    if hasattr(request, "session"):
        floating_notification = request.session.pop("floating_notification", None)
        if floating_notification is not None:
            request.session.modified = True
    return {
        "branding": branding_item,
        "floating_notification": floating_notification,
    }
