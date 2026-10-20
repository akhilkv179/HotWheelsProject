
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.cache import never_cache

from ..models import Address


# Display all saved delivery addresses belonging to the logged-in user.
@never_cache
@login_required
def address_list(request):

    # Show only the addresses belonging to the currently logged-in user.
    addresses = Address.objects.filter(
        user=request.user
    ).order_by("-is_default", "-id")

    # Return the addresses as JSON when requested by the frontend.
    if request.headers.get("Accept") == "application/json":
        address_data = list(
            addresses.values(
                "id",
                "full_name",
                "phone",
                "address_line1",
                "address_line2",
                "landmark",
                "city",
                "state",
                "postal_code",
                "address_type",
                "is_default",
            )
        )

        return JsonResponse(
            {
                "success": True,
                "addresses": address_data,
            },
            status=200,
        )

    # Render the existing address list page for normal browser requests.
    return render(
        request,
        "accounts/address_list.html",
        {"addresses": addresses},
    )
