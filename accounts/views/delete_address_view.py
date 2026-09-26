from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect

from ..models import Address



@login_required
def delete_address(request, address_id):

    if request.method != "POST":
        return redirect("address_list")


    address = Address.objects.filter(id = address_id,user = request.user).first()

    if not address:
        messages.error(request,"Address not found.")
        return redirect("address_list")

    address.delete()

    messages.success(request,"Address deleted successfully.")

    return redirect("address_list")
