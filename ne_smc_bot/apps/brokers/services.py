from core.adapters.broker_factory import get_adapter_for_account


def connect_broker_account(broker_account) -> dict:
    """
    Valide les identifiants fournis par l'utilisateur en tentant une connexion
    réelle, avant de marquer le compte comme connecté.
    """
    try:
        adapter = get_adapter_for_account(broker_account)
        balance = adapter.get_balance()

        broker_account.is_connected = True
        broker_account.balance = balance
        broker_account.save()

        return {'success': True, 'balance': balance}

    except Exception as e:
        broker_account.is_connected = False
        broker_account.save()
        return {'success': False, 'error': str(e)}