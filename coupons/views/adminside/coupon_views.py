
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.db import transaction
from django.http import JsonResponse, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.db.models import Q

from coupons.form import CouponForm
from coupons.models import Coupon


LIST_TEMPLATE = "adminside/admin_coupon_list.html"
FORM_TEMPLATE = "adminside/admin_coupon_form.html"


def wants_json(request):
    return "application/json" in request.headers.get("Accept", "")


def serialize_coupon(coupon):
    return {
        "id": coupon.pk,
        "code": coupon.code,
        "coupon_name": coupon.coupon_name,
        "discount_type": coupon.discount_type,
        "discount_value": str(coupon.discount_value),
        "minimum_spend": str(coupon.minimum_spend),
        "maximum_discount": coupon.maximum_discount,
        "usage_limit": coupon.usage_limit,
        "used_count": coupon.used_count,
        "start_date": coupon.start_date.isoformat(),
        "expiry_date": coupon.expiry_date.isoformat(),
        "status": coupon.status,
    }


# List coupons, with optional search and pagination.
@staff_member_required(login_url="/d/admin_login/")
def admin_coupon_list(request):
    if request.method != "GET":
        if wants_json(request):
            return JsonResponse(
                {"error": "Only GET requests are allowed."},
                status=405,
            )
        return HttpResponseNotAllowed(["GET"])

    search_query = request.GET.get("search", "").strip()

    coupons = Coupon.objects.all().order_by("-created_at", "-pk")

    if search_query:
        coupons = coupons.filter(
            Q(code__icontains=search_query)
            | Q(coupon_name__icontains=search_query)
        )

    paginator = Paginator(coupons, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    if wants_json(request):
        return JsonResponse(
            {
                "coupons": [
                    serialize_coupon(coupon)
                    for coupon in page_obj.object_list
                ],
                "pagination": {
                    "current_page": page_obj.number,
                    "total_pages": paginator.num_pages,
                    "total_coupons": paginator.count,
                    "has_previous": page_obj.has_previous(),
                    "has_next": page_obj.has_next(),
                },
                "search_query": search_query,
            },
            status=200,
        )

    return render(
        request,
        LIST_TEMPLATE,
        {
            "coupons": page_obj,
            "page_obj": page_obj,
            "search_query": search_query,
        },
    )


# Create a coupon after validating all submitted fields.
@staff_member_required(login_url="/d/admin_login/")
def admin_coupon_create(request):
    if request.method not in ("GET", "POST"):
        if wants_json(request):
            return JsonResponse(
                {"error": "Only GET and POST requests are allowed."},
                status=405,
            )
        return HttpResponseNotAllowed(["GET", "POST"])

    if request.method == "GET":
        if wants_json(request):
            return JsonResponse(
                {
                    "message": "Submit the coupon fields to create a coupon.",
                    "fields": [
                        "code",
                        "coupon_name",
                        "discount_type",
                        "discount_value",
                        "minimum_spend",
                        "maximum_discount",
                        "usage_limit",
                        "start_date",
                        "expiry_date",
                        "status",
                    ],
                },
                status=200,
            )

        return render(
            request,
            FORM_TEMPLATE,
            {"form": CouponForm()},
        )

    form = CouponForm(request.POST)

    if not form.is_valid():
        if wants_json(request):
            return JsonResponse(
                {
                    "error": "Please correct the submitted coupon fields.",
                    "field_errors": form.errors.get_json_data(),
                },
                status=400,
            )

        messages.error(
            request,
            "Please correct the errors in the coupon form.",
        )
        return render(
            request,
            FORM_TEMPLATE,
            {"form": form},
            status=400,
        )

    coupon = form.save()

    if wants_json(request):
        return JsonResponse(
            {
                "message": "Coupon created successfully.",
                "coupon": serialize_coupon(coupon),
            },
            status=201,
        )

    messages.success(request, "Coupon created successfully.")
    return redirect("admin_coupon_list")


# Delete unused coupons. Preserve coupons referenced by orders or usage history.
@staff_member_required(login_url="/d/admin_login/")
def admin_coupon_delete(request, coupon_id):
    if request.method != "POST":
        if wants_json(request):
            return JsonResponse(
                {"error": "Only POST requests are allowed."},
                status=405,
            )
        return HttpResponseNotAllowed(["POST"])

    with transaction.atomic():
        coupon = get_object_or_404(
            Coupon.objects.select_for_update(),
            pk=coupon_id,
        )

        # Keep historical coupon usage and order references intact.
        if coupon.usages.exists() or coupon.orders.exists():
            error_message = (
                "This coupon has already been used or is linked to an "
                "order, so it cannot be deleted. Deactivate it instead."
            )

            if wants_json(request):
                return JsonResponse(
                    {"error": error_message},
                    status=400,
                )

            messages.error(request, error_message)
            return redirect("admin_coupon_list")

        deleted_coupon_id = coupon.pk
        deleted_coupon_code = coupon.code
        coupon.delete()

    if wants_json(request):
        return JsonResponse(
            {
                "message": "Coupon deleted successfully.",
                "coupon_id": deleted_coupon_id,
                "coupon_code": deleted_coupon_code,
            },
            status=200,
        )

    messages.success(request, "Coupon deleted successfully.")
    return redirect("admin_coupon_list")



# Edit an existing coupon using the same validated CouponForm.
# @staff_member_required(login_url="/d/admin_login/")
def admin_coupon_edit(request, coupon_id):
    if request.method not in ("GET", "POST"):
        if wants_json(request):
            return JsonResponse(
                {"error": "Only GET and POST requests are allowed."},
                status=405,
            )
        return HttpResponseNotAllowed(["GET", "POST"])

    if request.method == "GET":
        coupon = get_object_or_404(Coupon, pk=coupon_id)
        form = CouponForm(instance=coupon)

        if wants_json(request):
            return JsonResponse(
                {
                    "coupon": serialize_coupon(coupon),
                },
                status=200,
            )

        return render(
            request,
            FORM_TEMPLATE,
            {
                "form": form,
                "coupon": coupon,
                "is_edit": True,
            },
        )

    # Lock the coupon while processing an update.
    with transaction.atomic():
        coupon = get_object_or_404(
            Coupon.objects.select_for_update(),
            pk=coupon_id,
        )

        form = CouponForm(request.POST, instance=coupon)

        if not form.is_valid():
            if wants_json(request):
                return JsonResponse(
                    {
                        "error": "Please correct the submitted coupon fields.",
                        "field_errors": form.errors.get_json_data(),
                    },
                    status=400,
                )

            messages.error(
                request,
                "Please correct the errors in the coupon form.",
            )
            return render(
                request,
                FORM_TEMPLATE,
                {
                    "form": form,
                    "coupon": coupon,
                    "is_edit": True,
                },
                status=400,
            )

        updated_coupon = form.save()

    if wants_json(request):
        return JsonResponse(
            {
                "message": "Coupon updated successfully.",
                "coupon": serialize_coupon(updated_coupon),
            },
            status=200,
        )

    messages.success(request, "Coupon updated successfully.")
    return redirect("admin_coupon_list")


# List or unlist a coupon by changing its status.
@staff_member_required(login_url="/d/admin_login/")
def admin_coupon_toggle_status(request, coupon_id):
    if request.method != "POST":
        if wants_json(request):
            return JsonResponse(
                {"error": "Only POST requests are allowed."},
                status=405,
            )
        return HttpResponseNotAllowed(["POST"])

    with transaction.atomic():
        coupon = get_object_or_404(
            Coupon.objects.select_for_update(),
            pk=coupon_id,
        )

        current_status = (coupon.status or "").strip().lower()

        if current_status not in ("active", "inactive"):
            error_message = "This coupon has an unsupported status."

            if wants_json(request):
                return JsonResponse(
                    {"error": error_message},
                    status=400,
                )

            messages.error(request, error_message)
            return redirect("admin_coupon_list")

        if current_status == "active":
            coupon.status = "inactive"
            action_message = "Coupon unlisted successfully."
        else:
            coupon.status = "active"
            action_message = "Coupon listed successfully."

        coupon.save(update_fields=["status", "updated_at"])

    if wants_json(request):
        return JsonResponse(
            {
                "message": action_message,
                "coupon_id": coupon.pk,
                "coupon_code": coupon.code,
                "status": coupon.status,
            },
            status=200,
        )

    messages.success(request, action_message)
    return redirect("admin_coupon_list")
