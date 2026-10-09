from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages

from admin_panel.decorators import admin_required
from categories.models import Category



def category_delete(request, category_id):

    category = get_object_or_404(
        Category,
        id=category_id
    )

    category.is_deleted = True 
    category.save(update_fields=["is_deleted"])

    messages.success(request,"Category deleted successfully.")
    return redirect("admin_category_list")

def category_unlisting(request,category_id):
    category = get_object_or_404(Category,id = category_id)

    category.is_active = not category.is_active
    category.save()

    if category.is_active:
        messages.success(request,"listed ")
    else:
        messages.success(request,"unlisted")

    return redirect("admin_category_list")

def category_restore(request,category_id):
    category = get_object_or_404(Category,id = category_id)

    category.is_deleted = False
    category.save(update_fields=["is_deleted"])

    messages.success(request,"Category restored")
    return redirect("admin_category_list")

