from django.shortcuts import render
from django.views.decorators.cache import never_cache


# Render the home landing page for the store.
@never_cache
def home_view(request):
    return render(request, "accounts/home.html")