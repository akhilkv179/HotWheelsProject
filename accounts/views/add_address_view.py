from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.views.decorators.cache import never_cache

from ..forms import AddressForm
from ..models import Address


@never_cache
@login_required
def add_address(request):
    """Validate and save a new address for the logged-in user."""

    if request.method == "POST":
        form = AddressForm(request.POST)

        if form.is_valid():
            # Get the validated and cleaned field values.
            data = form.cleaned_data
            is_default = data["is_default"]

            # If this address is the default, remove the previous default.
            if is_default:
                Address.objects.filter(
                    user=request.user,
                    is_default=True,
                ).update(is_default=False)

            # Create the new address.
            Address.objects.create(
                user=request.user,
                full_name=data["full_name"],
                phone=data["phone"],
                address_line1=data["address_line1"],
                address_line2=data["address_line2"],
                landmark=data["landmark"],
                city=data["city"],
                state=data["state"],
                postal_code=data["postal_code"],
                address_type=data["address_type"],
                is_default=is_default,
            )

            messages.success(
                request,
                "Address added successfully.",
            )

            return redirect("address_list")

        # Preserve the existing Django messages-based error feedback.
        for field_errors in form.errors.values():
            for error in field_errors:
                messages.error(request, error)

    else:
        form = AddressForm()

    return render(
        request,
        "accounts/add_address.html",
        {"form": form},
    )