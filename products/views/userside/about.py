from django.http import JsonResponse
from django.shortcuts import render
from django.contrib.auth.decorators import login_required


@login_required
def about_view(request):

    if request.method != "GET":
        return JsonResponse(
            {
                "success": False,
                "message": "Method not allowed."
            },
            status=405
        )

    if request.headers.get("Accept") == "application/json":
        return JsonResponse(
            {
                "success": True,
                "message": "About page loaded successfully."
            },
            status=200
        )

    return render(
        request,
        'userside/about.html',
        status=200
    )