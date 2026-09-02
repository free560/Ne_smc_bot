from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages
from apps.brokers.models import BrokerAccount
from apps.brokers.services import connect_broker_account


@login_required
def broker_management(request):
    if request.method == 'POST':
        broker_name = request.POST.get('broker_name', '').strip()
        account_type = request.POST.get('account_type', '').strip()
        api_token = request.POST.get('api_token', '').strip()

        valid_brokers = dict(BrokerAccount.BROKER_CHOICES).keys()
        valid_types = dict(BrokerAccount.ACCOUNT_TYPE_CHOICES).keys()

        if broker_name not in valid_brokers:
            messages.error(request, "Broker invalide.")
            return redirect('broker_management')

        if account_type not in valid_types:
            messages.error(request, "Type de compte invalide.")
            return redirect('broker_management')

        if not api_token:
            messages.error(request, "Le token API est requis.")
            return redirect('broker_management')

        broker_account = BrokerAccount(
            user=request.user,
            broker_name=broker_name,
            account_type=account_type,
        )
        broker_account.set_credentials(api_token)
        broker_account.save()

        result = connect_broker_account(broker_account)

        if result['success']:
            messages.success(request, f"Compte connecté avec succès — solde : {result['balance']}")
        else:
            messages.error(request, f"Échec de connexion : {result['error']}")
            broker_account.delete()

        return redirect('broker_management')

    user_accounts = BrokerAccount.objects.filter(user=request.user)
    broker_choices = BrokerAccount.BROKER_CHOICES
    account_type_choices = BrokerAccount.ACCOUNT_TYPE_CHOICES

    return render(request, 'brokers/broker_management.html', {
        'accounts': user_accounts,
        'broker_choices': broker_choices,
        'account_type_choices': account_type_choices,
    })


@login_required
def disconnect_broker(request, account_id):
    account = BrokerAccount.objects.filter(id=account_id, user=request.user).first()
    if account:
        account.delete()
        messages.success(request, "Compte broker déconnecté.")
    return redirect('broker_management')