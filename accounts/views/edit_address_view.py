from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.views.decorators.cache import never_cache
from ..models import Address

@never_cache
@login_required
def edit_address(request,address_id):

    if not request.user.is_authenticated:
        return redirect("login")

    address = Address.objects.filter(id = address_id,user = request.user).first()

    if not address:
        messages.error(request,"Address not found.")
        return redirect("address_list")

    if request.method ==  "POST":

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
            return render(request,"accounts/edit_address.html",{"address": address})

        if not phone:
            messages.error(request, "Phone number is required.")
            return render(request,"accounts/edit_address.html",{"address": address})

        if not address_line1:
            messages.error(request, "Address line 1 is required.")
            return render(request,"accounts/edit_address.html",{"address": address})

        if not city:
            messages.error(request, "City is required.")
            return render(request,"accounts/edit_address.html",{"address": address})

        if not state:
            messages.error(request, "State is required.")
            return render(request,"accounts/edit_address.html",{"address": address})

        if not postal_code:
            messages.error(request, "Postal code is required.")
            return render(request,"accounts/edit_address.html",{"address": address})

        # Remove default status from other addresses
        if is_default:
            Address.objects.filter(
                user=request.user,
                is_default=True
            ).exclude(
                id=address.id
            ).update(is_default=False)

        address.full_name = full_name
        address.phone = phone
        address.address_line1 = address_line1
        address.address_line2 = address_line2
        address.landmark = landmark
        address.city = city
        address.state = state
        address.postal_code = postal_code
        address.address_type = address_type
        address.is_default = is_default

        address.save()
        messages.success(request,"Address updated successfully.")
        return redirect("address_list")

    return render(request,"accounts/edit_address.html",{"address": address})



