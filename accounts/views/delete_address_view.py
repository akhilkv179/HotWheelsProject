
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseNotAllowed
from django.views.decorators.cache import never_cache

from ..models import Address


# Delete a specific saved address owned by the logged-in user.
@never_cache
@login_required
def delete_address(request, address_id):

    # Allow only POST requests for deleting an address.
    if request.method != "POST":
        return JsonResponse(
            {
                "success": False,
                "message": "Method not allowed.",
            },
            status=405,
        )

    # Find the address only if it belongs to the logged-in user.
    address = Address.objects.filter(
        id=address_id,
        user=request.user,
    ).first()

    # Return an error if the address does not exist or is not owned by the user.
    if not address:
        return JsonResponse(
            {
                "success": False,
                "message": "Address not found.",
            },
            status=404,
        )

    # Delete the selected address.
    address.delete()

    # Return a successful JSON response after deletion.
    return JsonResponse(
        {
            "success": True,
            "message": "Address deleted successfully.",
        },
        status=200,
    )
