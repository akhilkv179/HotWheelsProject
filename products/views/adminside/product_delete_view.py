from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from products.models import Product

def delete_product(request, product_id):
    product = get_object_or_404(Product, id=product_id)

    product.is_deleted = True
    product.save(update_fields=["is_deleted"])

    messages.success(request, "Product deleted successfully.")
    return redirect("admin_product_list")

def restore_product(request, product_id):
    product = get_object_or_404(Product, id=product_id)

    product.is_deleted = False
    product.save(update_fields=["is_deleted"])

    messages.success(request, "Product restored successfully.")
    return redirect("admin_product_list")