
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from wallet.models import Wallet


@login_required
def wallet_view(request):
    # Find the logged-in user's wallet without creating a new one.
    wallet = Wallet.objects.filter(
        user=request.user,
        is_active=True,
    ).first()

    # Get wallet transactions from newest to oldest.
    transactions = (
        wallet.transactions.order_by("-created_at")
        if wallet
        else []
    )

    # Display the wallet balance and transaction history.
    return render(
        request,
        "userside/wallet.html",
        {
            "wallet": wallet,
            "transactions": transactions,
        },
    )
