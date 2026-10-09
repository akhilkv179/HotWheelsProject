
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.views.decorators.cache import never_cache
from ..models import Address
import re


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

        # Full name validation
        if not full_name:
            messages.error(request, "Full name is required.")
            return render(request, "accounts/add_address.html")

        if len(full_name) < 3:
            messages.error(
                request,
                "Full name must contain at least 3 characters."
            )
            return render(request, "accounts/add_address.html")

        if len(full_name) > 100:
            messages.error(
                request,
                "Full name cannot exceed 100 characters."
            )
            return render(request, "accounts/add_address.html")

        if not re.fullmatch(r"[A-Za-z ]+", full_name):
            messages.error(
                request,
                "Full name can contain only letters and spaces."
            )
            return render(request, "accounts/add_address.html")

        # Phone validation
        if not phone:
            messages.error(request, "Phone number is required.")
            return render(request, "accounts/add_address.html")

        if not phone.isdigit() or len(phone) != 10:
            messages.error(
                request,
                "Phone number must contain exactly 10 digits."
            )
            return render(request, "accounts/add_address.html")

        if phone[0] not in "6789":
            messages.error(
                request,
                "Phone number must start with 6, 7, 8, or 9."
            )
            return render(request, "accounts/add_address.html")

        # Address line 1 validation
        if not address_line1:
            messages.error(request, "Address line 1 is required.")
            return render(request, "accounts/add_address.html")

        if len(address_line1) < 5:
            messages.error(
                request,
                "Address line 1 must contain at least 5 characters."
            )
            return render(request, "accounts/add_address.html")

        if len(address_line1) > 255:
            messages.error(
                request,
                "Address line 1 cannot exceed 255 characters."
            )
            return render(request, "accounts/add_address.html")

        # Address line 2 validation
        if len(address_line2) > 255:
            messages.error(
                request,
                "Address line 2 cannot exceed 255 characters."
            )
            return render(request, "accounts/add_address.html")

        # Landmark validation
        if len(landmark) > 100:
            messages.error(
                request,
                "Landmark cannot exceed 100 characters."
            )
            return render(request, "accounts/add_address.html")

        # City validation
        if not city:
            messages.error(request, "City is required.")
            return render(request, "accounts/add_address.html")

        if len(city) < 2:
            messages.error(
                request,
                "City must contain at least 2 characters."
            )
            return render(request, "accounts/add_address.html")

        if len(city) > 100:
            messages.error(
                request,
                "City cannot exceed 100 characters."
            )
            return render(request, "accounts/add_address.html")

        if not re.fullmatch(r"[A-Za-z ]+", city):
            messages.error(
                request,
                "City can contain only letters and spaces."
            )
            return render(request, "accounts/add_address.html")

        # State validation
        if not state:
            messages.error(request, "State is required.")
            return render(request, "accounts/add_address.html")

        if len(state) < 2:
            messages.error(
                request,
                "State must contain at least 2 characters."
            )
            return render(request, "accounts/add_address.html")

        if len(state) > 100:
            messages.error(
                request,
                "State cannot exceed 100 characters."
            )
            return render(request, "accounts/add_address.html")

        if not re.fullmatch(r"[A-Za-z ]+", state):
            messages.error(
                request,
                "State can contain only letters and spaces."
            )
            return render(request, "accounts/add_address.html")

        # Postal code validation
        if not postal_code:
            messages.error(request, "Postal code is required.")
            return render(request, "accounts/add_address.html")

        if not postal_code.isdigit() or len(postal_code) != 6:
            messages.error(
                request,
                "Postal code must contain exactly 6 digits."
            )
            return render(request, "accounts/add_address.html")

        if postal_code[0] == "0":
            messages.error(
                request,
                "Postal code cannot start with 0."
            )
            return render(request, "accounts/add_address.html")

        # Address type validation
        if address_type not in ["home", "work"]:
            messages.error(
                request,
                "Invalid address type."
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



