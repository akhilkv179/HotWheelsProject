
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from ..forms import AddressForm
from ..models import Address


# Validate and update an existing delivery address for the logged-in user.
@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def edit_address(request, address_id):
    """Validate and update an address belonging to the logged-in user."""

    # Find the address owned by the current user.
    address = Address.objects.filter(
        id=address_id,
        user=request.user,
    ).first()

    if not address:
        return JsonResponse(
            {
                "success": False,
                "message": "Address not found.",
            },
            status=404,
        )

    if request.method == "POST":
        form = AddressForm(request.POST)

        if form.is_valid():
            data = form.cleaned_data
            is_default = data["is_default"]

            # If this address becomes the default,
            # remove the default status from other addresses.
            if is_default:
                Address.objects.filter(
                    user=request.user,
                    is_default=True,
                ).exclude(
                    id=address.id,
                ).update(is_default=False)

            # Update the existing address with validated data.
            address.full_name = data["full_name"]
            address.phone = data["phone"]
            address.address_line1 = data["address_line1"]
            address.address_line2 = data["address_line2"]
            address.landmark = data["landmark"]
            address.city = data["city"]
            address.state = data["state"]
            address.postal_code = data["postal_code"]
            address.address_type = data["address_type"]
            address.is_default = is_default

            address.save()

            return JsonResponse(
                {
                    "success": True,
                    "message": "Address updated successfully.",
                },
                status=200,
            )

        # Return field-specific validation errors as JSON.
        return JsonResponse(
            {
                "success": False,
                "message": "Please correct the errors below.",
                "errors": form.errors.get_json_data(),
            },
            status=400,
        )

    # Initialise the form with the address's existing values.
    form = AddressForm(
        initial={
            "full_name": address.full_name,
            "phone": address.phone,
            "address_line1": address.address_line1,
            "address_line2": address.address_line2,
            "landmark": address.landmark,
            "city": address.city,
            "state": address.state,
            "postal_code": address.postal_code,
            "address_type": address.address_type,
            "is_default": address.is_default,
        }
    )

    # Render the existing edit address page for normal browser requests.
    return render(
        request,
        "accounts/edit_address.html",
        {
            "address": address,
            "form": form,
        },
    )
