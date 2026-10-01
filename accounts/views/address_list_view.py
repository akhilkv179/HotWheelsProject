from django.contrib.auth.decorators import login_required
from django.shortcuts import render,redirect
from django.views.decorators.cache import never_cache
from ..models import Address

@never_cache
@login_required
def address_list(request):

    if not request.user.is_authenticated:
        return redirect("login")


    # Show only the addresses belonging to the currently logged-in user.
    addresses = Address.objects.filter(user = request.user).order_by("-is_default","-id")

    return render(request,"accounts/address_list.html",{"addresses": addresses})

    