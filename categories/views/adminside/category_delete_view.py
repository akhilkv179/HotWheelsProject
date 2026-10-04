from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages

from admin_panel.decorators import admin_required
from categories.models import Category


@admin_required
def category_delete(request, category_id):

    category = get_object_or_404(
        Category,
        id=category_id
    )

    category.is_active = False
    category.save()

    messages.success(
        request,
        "Category deleted successfully."
    )

    return redirect("admin_category_list")