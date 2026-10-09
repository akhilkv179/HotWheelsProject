from django.shortcuts import render
from categories.models import Category
from django.core.paginator import Paginator
from django.db.models import Q



def user_category_list(request):


    search_query = request.GET.get("search","").strip()
    sort = request.GET.get("sort","name_az")
    
    categories = Category.objects.filter(is_active=True,is_deleted = False)

    if search_query:
        categories = categories.filter(Q(name__icontains=search_query)|Q(description__icontains = search_query))


    if sort == "name_az":
        categories = categories.order_by("name")
    elif sort == "name_za":
        categories = categories.order_by("-name")
    elif sort == "newest":
        categories = categories.order_by("-created_at")
    elif sort == "olderst":
        categories = categories.order_by("created_at")



    paginator = Paginator(categories,7)
    page_number = request.GET.get("page")

    page_obj = paginator.get_page(page_number)



    return render( request,"userside/category_list.html",{"page_obj": page_obj,"search_query": search_query,"sort": sort,})