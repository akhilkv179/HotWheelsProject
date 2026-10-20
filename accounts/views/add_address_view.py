from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from ..forms import AddressForm
from ..models import Address


# Handle adding and saving a new delivery address for the logged-in user.
@never_cache
@login_required
@require_http_methods(["GET", "POST"])
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

            return JsonResponse(
                {
                    "success": True,
                    "message": "Address added successfully.",
                },
                status=201,
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

    # Display the existing address form page.
    form = AddressForm()

    return render(
        request,
        "accounts/add_address.html",
        {"form": form},
    )