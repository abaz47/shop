"""
Утилиты корзины: получение/создание корзины, перенос при входе.
"""
from .models import Cart


def get_or_create_cart(request):
    """
    Возвращает корзину для текущего запроса (по user или session_key).
    Создаёт новую при отсутствии.
    """
    if request.user.is_authenticated:
        cart, _ = Cart.objects.get_or_create(
            user=request.user,
            defaults={},
        )
        return cart

    if not request.session.session_key:
        request.session.create()

    cart, _ = Cart.objects.get_or_create(
        session_key=request.session.session_key,
        defaults={"user": None},
    )
    return cart


def merge_carts(session_cart, user_cart):
    """
    Переносит позиции из корзины сессии в корзину пользователя.
    Совпадающие товары складываются по quantity, затем session_cart удаляется.
    """
    if session_cart.pk == user_cart.pk:
        return

    for item in session_cart.items.select_related("product"):
        user_item = user_cart.items.filter(product=item.product).first()
        if user_item:
            user_item.quantity += item.quantity
            user_item.save()
        else:
            item.cart = user_cart
            item.save()
    session_cart.delete()
