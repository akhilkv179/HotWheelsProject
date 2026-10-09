from django.shortcuts import render, redirect
from django.contrib import messages
from admin_panel.decorators import admin_required
from categories.models import Category



def category_add(request):
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        description = request.POST.get("description", "").strip()
        image = request.FILES.get("image")

        if not name:
            messages.error(request, "Category name is required.")
            return redirect("admin_category_list")

        if not description:
            messages.error(request, "Category description is required.")
            return redirect("admin_category_list")

        # if not image:
        #     messages.error(request, "Category image is required.")
        #     return redirect("admin_category_list")

        if Category.objects.filter(name__iexact=name).exists():
            messages.error(request, "A category with this name already exists.")
            return redirect("admin_category_list")

        Category.objects.create(
            name=name,
            description=description,
            image=image
        )

        messages.success(request, "Category added successfully.")
        return redirect("admin_category_list")

    # return render(request, "adminside/category_add.html")