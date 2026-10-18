from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.views.decorators.cache import never_cache

from ..forms import AddressForm
from ..models import Address


@never_cache
@login_required
def edit_address(request, address_id):
    """Validate and update an address belonging to the logged-in user."""

    # Find the address owned by the current user.
    address = Address.objects.filter(
        id=address_id,
        user=request.user,
    ).first()

    if not address:
        messages.error(request, "Address not found.")
        return redirect("address_list")

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

            messages.success(
                request,
                "Address updated successfully.",
            )

            return redirect("address_list")

        # Display validation errors using Django messages.
        for field_errors in form.errors.values():
            for error in field_errors:
                messages.error(request, error)

    else:
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

    return render(
        request,
        "accounts/edit_address.html",
        {
            "address": address,
            "form": form,
        },
    )