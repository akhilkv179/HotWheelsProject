
from datetime import datetime, timedelta
from io import BytesIO

from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponse, HttpResponseNotAllowed, JsonResponse
from django.utils import timezone

from openpyxl import Workbook
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle

from orders.models import Order


# Fetch order details using the selected date filter.
def get_order_report_data(request=None):

    orders = Order.objects.select_related("user").order_by("-created_at")

    # Apply date filters when a request is provided.
    if request:
        date_filter = request.GET.get("filter", "all")

        today = timezone.localdate()

        start_date = None
        end_date = None

        if date_filter == "daily":
            start_date = today
            end_date = today

        elif date_filter == "weekly":
            start_date = today - timedelta(days=today.weekday())
            end_date = today

        elif date_filter == "monthly":
            start_date = today.replace(day=1)
            end_date = today

        elif date_filter == "custom":
            start_date_input = request.GET.get("start_date")
            end_date_input = request.GET.get("end_date")

            try:
                if start_date_input:
                    start_date = datetime.strptime(
                        start_date_input,
                        "%Y-%m-%d"
                    ).date()

                if end_date_input:
                    end_date = datetime.strptime(
                        end_date_input,
                        "%Y-%m-%d"
                    ).date()

            except ValueError:
                start_date = None
                end_date = None

        # Apply the selected date range.
        if start_date:
            orders = orders.filter(
                created_at__date__gte=start_date
            )

        if end_date:
            orders = orders.filter(
                created_at__date__lte=end_date
            )

    rows = [
        [
            "Order Number", "Customer", "Email", "Status",
            "Subtotal", "Discount", "Shipping", "Total", "Date"
        ]
    ]

    for order in orders:
        rows.append([
            order.order_number,
            order.user.username,
            order.user.email,
            order.status,
            float(order.subtotal),
            float(order.discount_amount),
            float(order.shipping_amount),
            float(order.total_amount),
            timezone.localtime(order.created_at).strftime(
                "%d-%m-%Y %H:%M"
            ),
        ])

    return rows


# Generate and download an Excel spreadsheet of all customer orders.
@staff_member_required
def export_orders_excel(request):

    if request.method != "GET":
        if "application/json" in request.headers.get("Accept", ""):
            return JsonResponse(
                {
                    "success": False,
                    "message": "Only GET requests are allowed."
                },
                status=405
            )

        return HttpResponseNotAllowed(["GET"])

    # Keep Excel export unchanged: download all orders.
    rows = get_order_report_data()

    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Orders"

    for row in rows:
        worksheet.append(row)

    for column in worksheet.columns:
        max_length = max(
            len(str(cell.value or "")) for cell in column
        )

        worksheet.column_dimensions[
            column[0].column_letter
        ].width = min(max_length + 2, 30)

    output = BytesIO()
    workbook.save(output)
    output.seek(0)

    response = HttpResponse(
        output.getvalue(),
        content_type=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
    )

    response["Content-Disposition"] = (
        'attachment; filename="hotwheels_orders.xlsx"'
    )

    return response


# Generate and download a filtered PDF sales report.
@staff_member_required
def export_orders_pdf(request):

    if request.method != "GET":
        if "application/json" in request.headers.get("Accept", ""):
            return JsonResponse(
                {
                    "success": False,
                    "message": "Only GET requests are allowed."
                },
                status=405
            )

        return HttpResponseNotAllowed(["GET"])

    # Pass the request so the selected date filter is applied.
    rows = get_order_report_data(request)

    output = BytesIO()

    document = SimpleDocTemplate(
        output,
        pagesize=landscape(A4),
        rightMargin=20,
        leftMargin=20,
        topMargin=25,
        bottomMargin=25,
    )

    table = Table(rows, repeatRows=1)

    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E31837")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        (
            "ROWBACKGROUNDS", (0, 1), (-1, -1),
            [colors.white, colors.HexColor("#F2F2F2")]
        ),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))

    document.build([table])
    output.seek(0)

    response = HttpResponse(
        output.getvalue(),
        content_type="application/pdf"
    )

    response["Content-Disposition"] = (
        'attachment; filename="hotwheels_orders.pdf"'
    )

    return response
