from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from ..models import Address


def address_list(request):
    # Show only the addresses belonging to the currently logged-in user.
    addresses = Address.objects.filter(user = request.user).order_by("-is_default","-id")

    return render(request,"accounts/address_list.html",{"addresses": addresses})

    