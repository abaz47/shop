"""
Контекст-процессор корзины: количество позиций для хэдера.
"""


def cart(request):
    """Добавляет в контекст количество товаров в корзине."""
    if not hasattr(request, "session"):
        return {"cart_count": 0}

    from .utils import get_or_create_cart

    try:
        cart_obj = get_or_create_cart(request)
        count = cart_obj.total_quantity
    except Exception:
        count = 0
    return {"cart_count": count}
