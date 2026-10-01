from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.views.decorators.cache import never_cache
from ..models import Address

@never_cache
@login_required
def add_address(request):

    if request.method == "POST":

        full_name = request.POST.get("full_name", "").strip()
        phone = request.POST.get("phone", "").strip()
        address_line1 = request.POST.get("address_line1", "").strip()
        address_line2 = request.POST.get("address_line2", "").strip()
        landmark = request.POST.get("landmark", "").strip()
        city = request.POST.get("city", "").strip()
        state = request.POST.get("state", "").strip()
        postal_code = request.POST.get("postal_code", "").strip()
        address_type = request.POST.get("address_type", "home")
        is_default = request.POST.get("is_default") == "on"

        if not full_name:
            messages.error(request, "Full name is required.")
            return render(request, "accounts/add_address.html")

        if not phone:
            messages.error(request, "Phone number is required.")
            return render(request, "accounts/add_address.html")

        # Phone number validation
        if not phone.isdigit() or len(phone) != 10:
            messages.error(
                request,
                "Phone number must contain exactly 10 digits."
            )
            return render(request, "accounts/add_address.html")

        if not address_line1:
            messages.error(request, "Address line 1 is required.")
            return render(request, "accounts/add_address.html")

        if not city:
            messages.error(request, "City is required.")
            return render(request, "accounts/add_address.html")

        if not state:
            messages.error(request, "State is required.")
            return render(request, "accounts/add_address.html")

        if not postal_code:
            messages.error(request, "Postal code is required.")
            return render(request, "accounts/add_address.html")

        # Postal code validation
        if not postal_code.isdigit() or len(postal_code) != 6:
            messages.error(
                request,
                "Postal code must contain exactly 6 digits."
            )
            return render(request, "accounts/add_address.html")

        # When the user chooses a new address as default,
        # their previous default address is no longer default.
        if is_default:
            Address.objects.filter(
                user=request.user,
                is_default=True
            ).update(is_default=False)

        Address.objects.create(
            user=request.user,
            full_name=full_name,
            phone=phone,
            address_line1=address_line1,
            address_line2=address_line2,
            landmark=landmark,
            city=city,
            state=state,
            postal_code=postal_code,
            address_type=address_type,
            is_default=is_default,
        )

        messages.success(
            request,
            "Address added successfully."
        )

        return redirect("address_list")

    return render(request, "accounts/add_address.html")