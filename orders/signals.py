"""
Сигналы заказов: письмо при передаче в доставку.
"""
import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Order
from .services import get_cdek_tracking_number

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Order)
def order_in_delivery_email(sender, instance, created, **kwargs):
    """
    При переходе заказа в статус «Передан в доставку» отправляем письмо
    с трек-номером СДЭК (если есть).
    """
    if created:
        return
    if instance.status != Order.Status.IN_DELIVERY:
        return
    if instance.email_in_delivery_sent:
        return
    from orders.emails import send_order_in_delivery_email
    tracking = get_cdek_tracking_number(instance)
    send_order_in_delivery_email(instance, tracking_number=tracking)
    Order.objects.filter(pk=instance.pk).update(email_in_delivery_sent=True)
