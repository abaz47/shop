"""
Management-команда для удаления неоплаченных заказов старше 6 часов.

Запуск дважды в сутки по cron, например:
  0 8,20 * * * cd /path/to/project && python manage.py cleanup_unpaid_orders
"""
from django.core.management.base import BaseCommand

from orders.models import Order


class Command(BaseCommand):
    help = (
        "Удаляет заказы со статусом «Не оплачен», "
        "созданные более 6 часов назад. "
        "Они перестают отображаться в личном кабинете."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Только показать, какие заказы были бы удалены, не удалять.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        qs = Order.objects.unpaid_expired()
        order_ids = list(qs.values_list("pk", flat=True))
        count = len(order_ids)

        if count == 0:
            self.stdout.write("Нет неоплаченных заказов старше 6 часов.")
            return

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"Dry-run: Заказов к удалению: {count}, pk: {order_ids}"
                )
            )
            return

        deleted, _ = qs.delete()
        self.stdout.write(
            self.style.SUCCESS(f"Удалено неоплаченных заказов: {deleted}")
        )
