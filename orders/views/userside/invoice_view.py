
from io import BytesIO
from xml.sax.saxutils import escape

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404
from django.utils import timezone

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from orders.models import Order


# Check whether the client expects a JSON response.
def wants_json(request):
    return "application/json" in request.headers.get("Accept", "")


# Generate and download a PDF invoice for an order owned by the logged-in user.
@login_required
def download_invoice(request, order_number):
    # Only allow GET requests for downloading invoices.
    if request.method != "GET":
        if wants_json(request):
            return JsonResponse(
                {"error": "Only GET requests are allowed."},
                status=405,
            )
        return HttpResponseNotAllowed(["GET"])

    # Find the order belonging to the logged-in user.
    order = get_object_or_404(
        Order.objects.select_related(
            "user",
            "order_address",
        ).prefetch_related("items"),
        order_number=order_number,
        user=request.user,
    )

    # Create an in-memory buffer to hold the generated PDF.
    buffer = BytesIO()

    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=35,
        leftMargin=35,
        topMargin=35,
        bottomMargin=35,
    )

    # Prepare the styles used throughout the invoice.
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "InvoiceTitle",
        parent=styles["Title"],
        alignment=TA_CENTER,
        textColor=colors.HexColor("#D71920"),
    )

    cell_style = ParagraphStyle(
        "InvoiceCell",
        parent=styles["Normal"],
        fontSize=8,
        leading=10,
    )

    # Add the invoice title and basic order information.
    content = [
        Paragraph("HOT WHEELS - INVOICE", title_style),
        Spacer(1, 18),
        Paragraph(
            f"Order Number: {escape(order.order_number)}",
            styles["Normal"],
        ),
        Paragraph(
            "Order Date: "
            + timezone.localtime(order.created_at).strftime(
                "%d %b %Y, %I:%M %p"
            ),
            styles["Normal"],
        ),
        Paragraph(
            f"Customer: {escape(order.user.username)}",
            styles["Normal"],
        ),
        Paragraph(
            f"Payment Method: {escape(order.delivery_method)}",
            styles["Normal"],
        ),
        Paragraph(
            f"Order Status: {escape(order.status.replace('_', ' ').title())}",
            styles["Normal"],
        ),
        Spacer(1, 12),
    ]

    # Add the saved delivery address when one is available.
    try:
        address = order.order_address
    except Order.order_address.RelatedObjectDoesNotExist:
        address = None

    if address:
        content.extend([
            Paragraph("Delivery Address", styles["Heading3"]),
            Paragraph(escape(address.full_name), styles["Normal"]),
            Paragraph(escape(address.phone), styles["Normal"]),
            Paragraph(escape(address.address_line1), styles["Normal"]),
            Paragraph(escape(address.address_line2 or ""), styles["Normal"]),
            Paragraph(
                escape(f"{address.city}, {address.state} - {address.pin}"),
                styles["Normal"],
            ),
            Paragraph(escape(address.country), styles["Normal"]),
            Spacer(1, 15),
        ])

    # Prepare the invoice table with its column headings.
    rows = [[
        "Product",
        "Qty",
        "Unit Price",
        "Discount",
        "Total",
        "Item Status",
    ]]

    # Add each ordered product to the invoice table.
    for item in order.items.all():
        item_status = item.get_item_status_display()

        rows.append([
            Paragraph(escape(item.product_name), cell_style),
            str(item.quantity),
            f"Rs. {item.unit_price:.2f}",
            f"Rs. {item.discount_amount:.2f}",
            f"Rs. {item.total_price:.2f}",
            Paragraph(escape(item_status), cell_style),
        ])

    # Format the invoice table for the PDF.
    table = Table(
        rows,
        colWidths=[135, 30, 75, 65, 75, 80],
        repeatRows=1,
    )

    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.black),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))

    # Add the table, order totals, and thank-you message.
    content.extend([
        table,
        Spacer(1, 18),
        Paragraph(
            f"Subtotal: Rs. {order.subtotal:.2f}",
            styles["Normal"],
        ),
        Paragraph(
            f"Discount: Rs. {order.discount_amount:.2f}",
            styles["Normal"],
        ),
        Paragraph(
            f"Shipping: Rs. {order.shipping_amount:.2f}",
            styles["Normal"],
        ),
        Spacer(1, 8),
        Paragraph(
            f"Grand Total: Rs. {order.total_amount:.2f}",
            styles["Heading2"],
        ),
        Spacer(1, 18),
        Paragraph(
            "Thank you for shopping with Hot Wheels!",
            styles["Normal"],
        ),
    ])

    # Build the PDF and prepare it for downloading.
    document.build(content)
    buffer.seek(0)

    response = HttpResponse(
        buffer.getvalue(),
        content_type="application/pdf",
        status=200,
    )

    # Set the filename shown when the invoice is downloaded.
    response["Content-Disposition"] = (
        f'attachment; filename="invoice-{order.order_number}.pdf"'
    )

    return response
