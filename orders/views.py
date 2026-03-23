"""
Представления заказов: оформление заказа и список заказов.
"""
import json
from decimal import Decimal, ROUND_UP

import requests
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_http_methods

from cart.utils import get_or_create_cart
from cdek.services import (
    calculate_delivery,
    calculate_tarifflist,
    cart_items_to_packages,
    delivery_sum_to_decimal,
    search_cities,
)
from tbank.client import TbankClient, build_default_urls
from tbank.utils import build_receipt, make_tbank_order_id

from .forms import CheckoutForm
from .models import Order, OrderItem
from .services import create_cdek_order, get_cdek_tracking_number


def _parse_tariffs_request_payload(request):
    """
    Разбирает JSON body запроса checkout_tariffs.
    Возвращает (mode, point_type, to_city_code, city_name, formatted_address).
    При ошибке — (None, None, None, "", "").
    """
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return None, None, None, "", ""
    mode = (payload.get("mode") or "").strip()
    point_type = (payload.get("point_type") or "").strip().upper()
    to_city_code = payload.get("city_code")
    city_name = (payload.get("city") or "").strip()
    formatted_address = (
        payload.get("formatted") or payload.get("address") or ""
    ).strip()
    try:
        to_city_code = int(to_city_code)
    except (TypeError, ValueError):
        to_city_code = None
    return mode, point_type, to_city_code, city_name, formatted_address


def _is_allowed_tariff_family(name: str) -> bool:
    """Только тарифы семейства «Посылка» (включая экономичную)."""
    n = (name or "").lower().strip()
    return (
        n.startswith("посылка ")
        or n == "посылка"
        or n.startswith("экономичная посылка ")
    )


def _tariff_kind_by_name(name: str) -> str | None:
    """
    Классификация тарифа по названию: только отправка из ПВЗ
    (склад → склад/постамат/дверь). Возвращает office|pickup|door|None.
    """
    title = (name or "").lower().replace(" ", " ").strip()
    normalized = title.replace(" - ", "-").replace(" – ", "-")
    if not normalized:
        return None
    if "дверь-дверь" in normalized or "дверь дверь" in normalized:
        return None
    if "дверь-склад" in normalized or "дверь склад" in normalized:
        return None
    if "дверь-постамат" in normalized or "дверь постамат" in normalized:
        return None
    if "склад-склад" in normalized or "склад - склад" in title:
        return "office"
    has_postamat = "склад-постамат" in normalized or (
        "постамат" in normalized and "склад" in normalized
    )
    if has_postamat:
        return "pickup"
    if (
        "склад-двер" in normalized
        or "до двери" in normalized
        or "курьер" in normalized
    ):
        return "door"
    return None


def _adjust_delivery_cost_for_customer(
    raw_sum: Decimal | int | float | None
) -> Decimal:
    """
    Увеличивает стоимость доставки на 10%
    и округляет до 10 рублей в большую сторону.
    """
    if raw_sum is None:
        return Decimal("0")
    try:
        value = Decimal(str(raw_sum))
    except Exception:
        return Decimal("0")
    if value <= 0:
        return Decimal("0")
    increased = (value * Decimal("1.10")).quantize(
        Decimal("1"), rounding=ROUND_UP
    )
    # Округление вверх до ближайших 10 рублей
    tens = (
        (increased + Decimal("9")) // Decimal("10")
    ) * Decimal("10")
    return tens


def _adjust_delivery_period(value, extra_days: int):
    """
    Прибавляет дополнительное число дней к сроку доставки.
    """
    if value is None:
        return None
    try:
        return int(value) + extra_days
    except (TypeError, ValueError):
        return None


def _filter_tariffs_for_response(raw_tariffs, mode: str, point_type: str):
    """Фильтрует и сортирует тарифы по mode и point_type."""
    filtered = []
    for t in raw_tariffs:
        name_str = str(t.get("tariff_name") or "")
        if not _is_allowed_tariff_family(name_str):
            continue
        kind = _tariff_kind_by_name(name_str)
        if not kind:
            continue
        if mode == "office" and kind != "office":
            continue
        if mode == "door" and kind != "door":
            continue
        raw_sum = t.get("delivery_sum")
        adjusted_sum = int(
            _adjust_delivery_cost_for_customer(raw_sum)
        ) if raw_sum is not None else 0
        filtered.append(
            {
                "tariff_code": t.get("tariff_code"),
                "tariff_name": t.get("tariff_name"),
                "tariff_description": t.get("tariff_description"),
                "delivery_mode": t.get("delivery_mode"),
                "period_min": _adjust_delivery_period(
                    t.get("period_min"), extra_days=1
                ),
                "period_max": _adjust_delivery_period(
                    t.get("period_max"), extra_days=3
                ),
                "delivery_sum": adjusted_sum,
            }
        )

    filtered.sort(key=lambda x: (x.get("delivery_sum") or 0))
    return filtered


def _process_place_order(request, form, cart, items, products_total):
    """
    Обрабатывает действие «Оформить заказ». Возвращает redirect при успехе
    или None (тогда вызывающий продолжит рендер формы).
    """
    tariff_code = form.cleaned_data["delivery_tariff"]
    to_city_code = form.cleaned_data["city_code"]
    from_city_code = getattr(settings, "CDEK_FROM_CITY_CODE", 137)

    packages = cart_items_to_packages(
        cart.items.select_related("variant__product")
    )
    result = calculate_delivery(
        from_city_code=from_city_code,
        to_city_code=to_city_code,
        packages=packages,
        tariff_code=tariff_code,
    )
    if not result:
        messages.error(
            request,
            "Не удалось подтвердить стоимость доставки при "
            "оформлении заказа. Попробуйте ещё раз.",
        )
        return None

    base_cost = delivery_sum_to_decimal(result)
    delivery_cost = _adjust_delivery_cost_for_customer(base_cost)
    delivery_type = (
        Order.DeliveryType.COURIER
        if form.cleaned_data.get("delivery_mode") == "door"
        else Order.DeliveryType.PICKUP
    )

    # На этапе оформления считаем заказ не оплаченным.
    # Статус "Оплачен" должен выставляться логикой оплаты.
    status = Order.Status.UNPAID

    order = Order.objects.create(
        user=request.user,
        status=status,
        delivery_method=Order.DeliveryMethod.CDEK,
        delivery_type=delivery_type,
        delivery_tariff_code=tariff_code,
        products_total=products_total,
        delivery_cost=delivery_cost,
        total=products_total + delivery_cost,
        recipient_name=form.cleaned_data["recipient_name"],
        recipient_phone=form.cleaned_data["recipient_phone"],
        recipient_email=form.cleaned_data.get("recipient_email") or "",
        city_code=to_city_code,
        delivery_address=form.cleaned_data.get("delivery_address") or "",
        pvz_code=form.cleaned_data.get("pvz_code") or "",
        comment=form.cleaned_data.get("comment") or "",
    )
    for item in items:
        OrderItem.objects.create(
            order=order,
            variant=item.variant,
            price=item.variant.discounted_price,
            quantity=item.quantity,
        )
    cart.items.all().delete()

    cdek_uuid = create_cdek_order(order)
    if cdek_uuid:
        order.cdek_order_uuid = cdek_uuid
        order.save(update_fields=["cdek_order_uuid"])
        messages.success(
            request,
            f"Заказ #{order.pk} оформлен и зарегистрирован в СДЭК. "
            f"Итого: {order.total:.0f} ₽.",
        )
    else:
        messages.warning(
            request,
            f"Заказ #{order.pk} сохранён, но не удалось зарегистрировать "
            f"его в СДЭК автоматически. Пожалуйста, свяжитесь с нами — "
            f"мы оформим доставку вручную. Итого: {order.total:.0f} ₽.",
        )

    # Инициация оплаты в T‑Банке и редирект на платёжную форму.
    # Используем уникальный OrderId (pk + timestamp), так как T‑Банк требует
    # уникальности OrderId для каждой операции.
    tbank_order_id = make_tbank_order_id(order.pk)
    try:
        urls = build_default_urls(request, str(order.pk))
        client = TbankClient()
        result = client.init_payment(
            order_id=tbank_order_id,
            amount=order.total,
            description=f"Оплата заказа #{order.pk}",
            customer_key=(
                str(request.user.pk)
                if request.user.is_authenticated
                else None
            ),
            success_url=urls["success_url"],
            fail_url=urls["fail_url"],
            notification_url=urls["notification_url"],
            extra_data={"order_number": str(order.pk)},
            receipt=build_receipt(order),
        )
    except Exception:
        messages.error(
            request,
            "Заказ сохранён, но не удалось инициировать оплату в T‑Банке. "
            "Пожалуйста, свяжитесь с нами для завершения заказа.",
        )
        return redirect("orders:success", order_id=order.pk)

    if result.payment_id:
        order.tbank_payment_id = result.payment_id
        order.save(update_fields=["tbank_payment_id", "updated_at"])

    return redirect(result.payment_url)


def _get_checkout_context(request, cart, items, products_total):
    """
    Обрабатывает форму оформления заказа (GET/POST).
    Возвращает (redirect_response, context_dict).
    Если redirect_response не None — редирект после успешного place_order.
    Иначе context_dict содержит form, delivery_cost, total, cdek_service_url...
    """
    delivery_cost = None
    delivery_period_min = None
    delivery_period_max = None
    form = CheckoutForm(request.POST or None, user=request.user)

    if request.method == "POST":
        action = request.POST.get("action", "calculate")

        if form.is_valid():
            tariff_code = form.cleaned_data["delivery_tariff"]
            to_city_code = form.cleaned_data["city_code"]
            from_city_code = getattr(settings, "CDEK_FROM_CITY_CODE", 137)

            if action == "calculate":
                packages = cart_items_to_packages(
                    cart.items.select_related("variant__product")
                )
                result = calculate_delivery(
                    from_city_code=from_city_code,
                    to_city_code=to_city_code,
                    packages=packages,
                    tariff_code=tariff_code,
                )
                if result:
                    base_cost = delivery_sum_to_decimal(result)
                    delivery_cost = _adjust_delivery_cost_for_customer(
                        base_cost
                    )
                    delivery_period_min = _adjust_delivery_period(
                        result.get("period_min"), extra_days=1
                    )
                    delivery_period_max = _adjust_delivery_period(
                        result.get("period_max"), extra_days=3
                    )
                else:
                    messages.warning(
                        request,
                        "Не удалось рассчитать доставку. "
                        "Проверьте город или попробуйте позже.",
                    )
            elif action == "place_order":
                redirect_response = _process_place_order(
                    request, form, cart, items, products_total
                )
                if redirect_response is not None:
                    return redirect_response, None
        else:
            if action == "place_order":
                messages.error(
                    request,
                    "Исправьте ошибки в форме и нажмите "
                    "«Оформить заказ» снова.",
                )

    total = products_total + (delivery_cost or Decimal("0"))
    cdek_service_url = request.build_absolute_uri("/service.php")
    yandex_key = getattr(settings, "YANDEX_MAPS_API_KEY", "") or ""
    context = {
        "form": form,
        "products_total": products_total,
        "delivery_cost": delivery_cost,
        "delivery_period_min": delivery_period_min,
        "delivery_period_max": delivery_period_max,
        "total": total,
        "cdek_service_url": cdek_service_url,
        "yandex_maps_api_key": yandex_key,
    }
    return None, context


@require_http_methods(["GET", "POST"])
def checkout_view(request):
    """
    Редирект на единую страницу корзины/оформления.
    Оставлен для обратной совместимости ссылок.
    """
    if not request.user.is_authenticated:
        return redirect("cart:detail")
    cart = get_or_create_cart(request)
    if not cart.items.exists():
        messages.info(
            request,
            "Корзина пуста. Добавьте товары для оформления заказа.",
        )
        return redirect("cart:detail")
    return redirect("cart:detail")


@login_required
def checkout_success(request, order_id):
    """
    Страница заказа: детали заказа, сообщение об оплате/неоплате,
    трек-номер СДЭК при наличии.
    """
    order = (
        Order.objects.filter(user=request.user, pk=order_id)
        .prefetch_related("items__variant__product", "items__variant__images")
        .first()
    )
    if not order:
        messages.warning(request, "Заказ не найден.")
        return redirect("accounts:profile")
    payment_result = request.GET.get("payment")  # success | fail

    # Письма после первой попытки оплаты (редирект с T‑Банка)
    if payment_result == "fail":
        from orders.emails import send_order_payment_failed_email
        send_order_payment_failed_email(order)
    elif payment_result == "success" and not order.email_paid_sent:
        from orders.emails import send_order_paid_email
        send_order_paid_email(order)
        order.email_paid_sent = True
        order.save(update_fields=["email_paid_sent"])

    # Трек-номер СДЭК показываем только после передачи заказа в доставку.
    cdek_tracking_number = None
    if (
        order.status in (Order.Status.IN_DELIVERY, Order.Status.DELIVERED)
        and order.delivery_method == Order.DeliveryMethod.CDEK
        and order.cdek_order_uuid
    ):
        cdek_tracking_number = get_cdek_tracking_number(order)
    return render(
        request,
        "orders/checkout_success.html",
        {
            "order": order,
            "payment_result": payment_result,
            "cdek_tracking_number": cdek_tracking_number,
        },
    )


@require_GET
def checkout_cities(request):
    """API: список городов СДЭК для автодополнения (GET ?q=...)."""
    q = (request.GET.get("q") or "").strip()
    if len(q) < 2:
        return JsonResponse({"cities": []})
    cities = search_cities(q, limit=30)
    return JsonResponse({"cities": cities})


_DADATA_SUGGEST_URL = (
    "https://suggestions.dadata.ru/suggestions/api/4_1/rs/suggest/address"
)


def _dadata_suggestions_list_from_response(data: object) -> list:
    if not isinstance(data, dict):
        return []
    raw = data.get("suggestions")
    return raw if isinstance(raw, list) else []


def _dadata_items_to_suggestions(raw: list) -> list[dict]:
    result = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        val = item.get("value") or item.get("unrestricted_value") or ""
        val = val.strip()
        if val:
            result.append({"text": val, "address": val})
    return result


def _dadata_post_suggest(
    city: str,
    q: str,
    url: str,
    headers: dict,
    locations_boost: list | None,
) -> dict:
    payload: dict = {"query": f"{city}, {q}", "count": 10}
    if locations_boost is not None:
        payload["locations_boost"] = locations_boost
    resp = requests.post(url, json=payload, headers=headers, timeout=5)
    resp.raise_for_status()
    return resp.json()


def _dadata_address_suggest(city: str, q: str) -> tuple[list[dict], int]:
    """
    Подсказки адреса через DaData (нормализация).

    Возвращает список подсказок и число сырых ответов от DaData.
    Сначала запрос с locations_boost (город/посёлок), при пустом ответе —
    без ограничения.
    """
    api_key = getattr(settings, "DADATA_API_KEY", "").strip()
    if not api_key:
        return [], 0
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Token {api_key}",
    }
    secret = getattr(settings, "DADATA_SECRET_KEY", "").strip()
    if secret:
        headers["X-Secret"] = secret
    boost = [{"city": city}, {"settlement": city}]
    try:
        data = _dadata_post_suggest(
            city, q, _DADATA_SUGGEST_URL, headers, boost
        )
    except (requests.RequestException, ValueError):
        return [], 0
    raw = _dadata_suggestions_list_from_response(data)
    if not raw:
        try:
            data = _dadata_post_suggest(
                city, q, _DADATA_SUGGEST_URL, headers, None
            )
            raw = _dadata_suggestions_list_from_response(data)
        except (requests.RequestException, ValueError):
            raw = []
    result = _dadata_items_to_suggestions(raw)
    return result, len(raw)


@login_required
@require_GET
def checkout_address_suggest(request):
    """
    API: подсказки адреса в выбранном городе (DaData).
    GET ?city=...&q=... — возвращает нормализованные адреса для выбора.
    """
    city = (request.GET.get("city") or "").strip()
    q = (request.GET.get("q") or "").strip()
    if not city or not q:
        return JsonResponse({"suggestions": []})
    if not getattr(settings, "DADATA_API_KEY", "").strip():
        return JsonResponse({"suggestions": []})
    suggestions, dadata_raw_count = _dadata_address_suggest(city, q)
    out = {"suggestions": suggestions}
    if settings.DEBUG:
        out["_debug"] = {
            "count": len(suggestions),
            "dadata_raw_count": dadata_raw_count,
        }
    return JsonResponse(out)


@login_required
@require_http_methods(["POST"])
def checkout_tariffs(request):
    """
    API: список тарифов СДЭК по выбранному адресу / ПВЗ.

    Принимает JSON: mode (office|door), city_code, city, point_type.
    Возвращает JSON: {"tariffs": [...]}.
    """
    cart = get_or_create_cart(request)
    items = cart.items.select_related("variant__product")
    if not items.exists():
        return JsonResponse({"tariffs": []})

    mode, point_type, to_city_code, city_name, formatted_address = (
        _parse_tariffs_request_payload(request)
    )
    if mode is None:
        return JsonResponse({"error": "Некорректный JSON"}, status=400)
    if mode not in {"office", "door"}:
        return JsonResponse({"tariffs": []})

    # Только СДЭК: город задаётся выбором из справочника (шаг 1 в форме).
    # Для ПВЗ city_code приходит из виджета; для «до двери» — из поля города.
    if not to_city_code and city_name:
        matches = search_cities(city_name, limit=1)
        if matches:
            to_city_code = matches[0].get("code")
    if not to_city_code:
        return JsonResponse({"tariffs": []})

    from_city_code = getattr(settings, "CDEK_FROM_CITY_CODE", 137)
    packages = cart_items_to_packages(items)
    raw_tariffs = calculate_tarifflist(
        from_city_code=from_city_code,
        to_city_code=to_city_code,
        packages=packages,
    )
    filtered = _filter_tariffs_for_response(raw_tariffs, mode, point_type)
    response_data = {"tariffs": filtered}
    if to_city_code is not None:
        response_data["city_code"] = to_city_code
    return JsonResponse(response_data)


@login_required
def order_list_redirect(request):
    """Редирект на личный кабинет (список заказов отображается там)."""
    return redirect("accounts:profile")


@login_required
@require_http_methods(["POST"])
def repeat_order_view(request, order_id):
    """Повторить заказ:
    добавить товары заказа в корзину и перейти в корзину.
    """
    order = Order.objects.filter(
        user=request.user,
        pk=order_id,
    ).first()
    if not order:
        messages.warning(request, "Заказ не найден.")
        return redirect("accounts:profile")
    cart = get_or_create_cart(request)
    for item in order.items.select_related("variant"):
        cart_item, created = cart.items.get_or_create(
            variant=item.variant,
            defaults={"quantity": item.quantity},
        )
        if not created:
            cart_item.quantity += item.quantity
            cart_item.save(update_fields=["quantity"])
    messages.success(request, "Товары заказа добавлены в корзину.")
    return redirect("cart:detail")
