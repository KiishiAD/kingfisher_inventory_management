from supplychain.models import Organisation


class TenantMiddleware:
    """Populates request.organisation from session-stored organisation_id."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.organisation = None
        org_id = request.session.get("organisation_id")
        if org_id and request.user.is_authenticated:
            try:
                request.organisation = Organisation.objects.get(pk=org_id)
            except Organisation.DoesNotExist:
                pass
        return self.get_response(request)
