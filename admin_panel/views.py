from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.shortcuts import render,redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from functools import wraps
from django.db.models import Q
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404

from accounts.models import User


def admin_login(request):
    if request.method == 'POST':
        u_name = request.POST.get("username","").strip()
        p_word = request.POST.get("password","")

        username = u_name

        if '@' in u_name:
            user = User.objects.filter(email__iexact = u_name).first()

            if user:
                username = user.username
            else:
                username = None

        if username:
            authenticated_user = authenticate(request,username=username,password=p_word)
        else:
            authenticated_user = None

        if authenticated_user is not None:
            if not authenticated_user.is_active:
                messages.error(request,"This account is inactive.")
            elif not authenticated_user.is_staff:
                messages.error(request,"You donot have admin access")
            else:
                login(request,authenticated_user)
                return redirect("admin_dashboard")
        else:
            messages.error(request,"invalid username or password.")

    return render(request,"admin_panel/admin_login.html")

def admin_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("/login/")

        if not request.user.is_staff:
            return HttpResponseForbidden(
                "You do not have permission to access this page."
            )

        return view_func(request, *args, **kwargs)

    return wrapper

@admin_required
@login_required(login_url="/login/")
def admin_dashboard(request):
    return render(request, "admin_panel/admin_dashboard.html")

@admin_required
def user_list(request):
    search_query = request.GET.get("search","").strip()

    users = User.objects.all()

    if search_query:
        users = users.filter(
            Q(username__icontains = search_query)|
            Q(email__icontains = search_query)|
            Q(first_name__icontains = search_query)|
            Q(last_name__icontains = search_query)
        ) 
    users = User.objects.all().order_by("-date_joined")

    paginator = Paginator(users,10)

    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)



    return render(request ,"admin_panel/user_list.html",{"page_obj":page_obj,"search_queary":search_query})

def toggle_user_status(request,user_id):
    user = get_object_or_404(User,id=user_id)

    user.is_active = not user.is_active
    user.save()

    return redirect("user_list")