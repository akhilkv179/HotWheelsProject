from django.shortcuts import get_object_or_404, render, redirect
from django.contrib import messages

from admin_panel.decorators import admin_required
from categories.models import Category



def category_edit(request, category_id):

    category = get_object_or_404(
        Category,
        id=category_id
    )

    if request.method == "POST":

        name = request.POST.get("name", "").strip()
        description = request.POST.get("description", "").strip()

        if not name:
            messages.error(request, "Category name is required.")
            return render(
                request,
                "adminside/category_edit.html",
                {"category": category}
            )

        if not description:
            messages.error(request, "Category description is required.")
            return render(
                request,
                "adminside/category_edit.html",
                {"category": category}
            )

        if Category.objects.filter(
            name__iexact=name
        ).exclude(
            id=category.id
        ).exists():
            messages.error(
                request,
                "A category with this name already exists."
            )
            return render(
                request,
                "adminside/category_edit.html",
                {"category": category}
            )

        category.name = name
        category.description = description
        category.save()

        messages.success(
            request,
            "Category updated successfully."
        )

        return redirect("admin_category_list")

    return render(
        request,
        "adminside/category_edit.html",
        {"category": category}
    )