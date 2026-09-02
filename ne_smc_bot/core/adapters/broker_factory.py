from decouple import config
from core.adapters.deriv_adapter import DerivAdapter


def get_adapter_for_account(broker_account):
    api_key = broker_account.get_api_key()

    if broker_account.broker_name == 'deriv':
        # Notre modèle BrokerAccount utilise 'demo'/'live', mais Deriv utilise 'demo'/'real'
        deriv_account_type = 'real' if broker_account.account_type == 'live' else 'demo'

        return DerivAdapter(
            api_token=api_key,
            app_id=config('DERIV_APP_ID'),
            account_type=deriv_account_type,
        )

    elif broker_account.broker_name == 'exness':
        raise NotImplementedError("ExnessAdapter pas encore implémenté")

    raise ValueError(f"Broker non supporté : {broker_account.broker_name}")