from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.brokers.models import BrokerAccount
from apps.brokers.services import connect_broker_account

User = get_user_model()


class Command(BaseCommand):
    help = "Connecte un compte broker pour un utilisateur (test CLI)"

    def add_arguments(self, parser):
        parser.add_argument('username', type=str)
        parser.add_argument('broker_name', type=str)
        parser.add_argument('account_type', type=str)
        parser.add_argument('api_token', type=str)

    def handle(self, *args, **options):
        user = User.objects.get(username=options['username'])

        broker_account = BrokerAccount(
            user=user, broker_name=options['broker_name'], account_type=options['account_type']
        )
        broker_account.set_credentials(options['api_token'])
        broker_account.save()

        result = connect_broker_account(broker_account)

        if result['success']:
            self.stdout.write(self.style.SUCCESS(f"✅ Connecté — solde: {result['balance']}"))
        else:
            self.stdout.write(self.style.ERROR(f"❌ Échec : {result['error']}"))