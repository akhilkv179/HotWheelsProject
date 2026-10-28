from django.urls import path

from reviews.views.userside.review_view import (
    submit_review,
    delete_review,
)

urlpatterns = [
    path(
        "orders/<str:order_number>/items/<int:item_id>/review/",
        submit_review,
        name="submit_review",
    ),
    path(
        "reviews/<int:review_id>/delete/",
        delete_review,
        name="delete_review",
    ),
]