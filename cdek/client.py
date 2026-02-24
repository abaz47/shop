"""
Клиент СДЭК API v2.
Один товар — одно грузовое место; при quantity > 1 — несколько одинаковых мест.
"""
import logging
import time
from typing import Any

import requests

logger = logging.getLogger(__name__)

# Тарифы «Посылка» (коды 136–139) по официальной схеме СДЭК:
TARIFF_WAREHOUSE_WAREHOUSE = 136      # Посылка склад-склад (ПВЗ)
TARIFF_WAREHOUSE_DOOR = 137           # Посылка склад-дверь
TARIFF_DOOR_WAREHOUSE = 138           # Посылка дверь-склад (не используем)
TARIFF_DOOR_DOOR = 139                # Посылка дверь-дверь (не используем)

# Экономичные тарифы «Посылка»
TARIFF_WAREHOUSE_WAREHOUSE_ECO = 234  # Экономичная посылка склад-склад
TARIFF_WAREHOUSE_DOOR_ECO = 233       # Экономичная посылка склад-дверь
TARIFF_WAREHOUSE_POSTAMAT_ECO = 482   # Экономичная посылка склад-постамат


class CdekAPIError(Exception):
    """Ошибка вызова API СДЭК."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        response: dict | None = None
    ):
        self.status_code = status_code
        self.response = response or {}
        super().__init__(message)


class CdekClient:
    """
    Клиент для работы с СДЭК API v2.
    Настройки берутся из django.conf.settings.
    """

    def __init__(
        self,
        account: str,
        secure: str,
        *,
        test: bool = False,
        timeout: int = 15,
    ):
        self.account = account
        self.secure = secure
        self.timeout = timeout
        self._base_url = (
            "https://api.edu.cdek.ru" if test
            else "https://api.cdek.ru"
        )
        self._token: str | None = None
        self._token_expires_at: float = 0

    def _get_token(self) -> str:
        """Получает OAuth-токен (с кэшем до истечения)."""
        if self._token and time.monotonic() < self._token_expires_at:
            return self._token

        url = f"{self._base_url}/v2/oauth/token"
        data = {
            "grant_type": "client_credentials",
            "client_id": self.account,
            "client_secret": self.secure,
        }
        try:
            resp = requests.post(
                url,
                data=data,
                timeout=self.timeout,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            resp.raise_for_status()
            payload = resp.json()
        except requests.RequestException as e:
            logger.exception("CDEK OAuth request failed: %s", e)
            raise CdekAPIError(
                f"Не удалось получить токен СДЭК: {e}",
                status_code=getattr(e.response, "status_code", None),
                response=getattr(e.response, "json", lambda: {})(),
            ) from e

        self._token = payload.get("access_token")
        expires_in = int(payload.get("expires_in", 3600))
        # обновляем токен за 60 сек до истечения
        self._token_expires_at = time.monotonic() + max(0, expires_in - 60)
        if not self._token:
            raise CdekAPIError(
                "В ответе СДЭК нет access_token",
                response=payload
            )
        return self._token

    @staticmethod
    def _packages_to_api_format(
        packages: list[dict[str, int]]
    ) -> list[dict[str, int]]:
        """
        Приводит грузовые места к формату СДЭК API: размеры в см, вес в г.
        На входе: weight (г), length/width/height (мм).
        Объёмный вес СДЭК: (Д×Ш×В см)/5000.
        """
        out = []
        for p in packages:
            weight = max(1, int(p.get("weight", 0)))
            length = max(1, round(int(p.get("length", 0)) / 10))
            width = max(1, round(int(p.get("width", 0)) / 10))
            height = max(1, round(int(p.get("height", 0)) / 10))
            out.append({
                "weight": weight,
                "length": length,
                "width": width,
                "height": height,
            })
        return out

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict | None = None,
    ) -> dict[str, Any]:
        """Выполняет запрос к API с подставленным Bearer-токеном."""
        url = f"{self._base_url}{path}"
        token = self._get_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        try:
            if method.upper() == "GET":
                resp = requests.get(
                    url,
                    headers=headers,
                    timeout=self.timeout
                )
            else:
                resp = requests.post(
                    url,
                    headers=headers,
                    json=json,
                    timeout=self.timeout
                )
            resp.raise_for_status()
            return resp.json() if resp.content else {}
        except requests.RequestException as e:
            status_code = getattr(e.response, "status_code", None)
            try:
                response_body = e.response.json() if e.response else {}
            except Exception:
                response_body = {}
            logger.warning(
                "CDEK API %s %s failed: %s, body=%s",
                method,
                path,
                e,
                response_body,
            )
            raise CdekAPIError(
                f"Ошибка СДЭК API: {e}",
                status_code=status_code,
                response=response_body,
            ) from e

    def calculate_tariff(
        self,
        from_city_code: int,
        to_city_code: int,
        packages: list[dict[str, int]],
        *,
        tariff_code: int = TARIFF_WAREHOUSE_DOOR,
        from_address: str = "",
    ) -> dict[str, Any]:
        """
        Расчёт стоимости и срока доставки по одному тарифу.

        :param from_city_code: Код города отправителя (СДЭК). СПб = 137.
        :param to_city_code: Код города получателя (СДЭК).
        :param packages: Список грузовых мест.
            Каждый элемент: {
                "weight": вес в граммах,
                "length": длина мм,
                "width": ширина мм,
                "height": высота мм
            }.
        :param tariff_code: Код тарифа (136, 137, 233 и т.д.).
        :param from_address: Адрес отправки (улица) для уточнения расчёта.
        :return: Ответ API с полями delivery_sum, period_min, period_max и др.
        """
        from_location: dict[str, Any] = {"code": from_city_code}
        if from_address:
            from_location["address"] = from_address
        body = {
            "type": 1,
            "tariff_code": tariff_code,
            "from_location": from_location,
            "to_location": {"code": to_city_code},
            "packages": self._packages_to_api_format(packages),
        }
        logger.debug("CDEK tariff request: %s", body)
        return self._request("POST", "/v2/calculator/tariff", json=body)

    def calculate_tariff_list(
        self,
        from_city_code: int,
        to_city_code: int,
        packages: list[dict[str, int]],
        *,
        from_address: str = "",
    ) -> dict[str, Any]:
        """
        Расчёт по всем доступным тарифам между городами.

        :param from_city_code: Код города отправителя (СДЭК). СПб = 137.
        :param to_city_code: Код города получателя (СДЭК).
        :param packages: Список грузовых мест
            (weight в г, length/width/height в мм).
        :param from_address: Адрес отправки (улица) для уточнения расчёта.
        :return: Ответ с массивом тарифов
            (tariff_codes, delivery_sum, period_min, period_max).
        """
        from_location: dict[str, Any] = {"code": from_city_code}
        if from_address:
            from_location["address"] = from_address
        body = {
            "type": 1,
            "from_location": from_location,
            "to_location": {"code": to_city_code},
            "packages": self._packages_to_api_format(packages),
        }
        logger.debug("CDEK tarifflist request: %s", body)
        return self._request("POST", "/v2/calculator/tarifflist", json=body)

    def get_cities(
        self,
        *,
        country_code: str = "RU",
        region_code: int | None = None
    ) -> list[dict]:
        """
        Список городов (справочник).
        Для фильтрации по названию — фильтровать на своей стороне.

        :param country_code: Код страны (RU).
        :param region_code: Код региона (опционально).
        :return: Список словарей с полями code, city, country_code, region...
        """
        path = "/v2/location/cities"
        params = [("country_code", country_code)]
        if region_code is not None:
            params.append(("region_code", region_code))
        qs = "&".join(f"{k}={v}" for k, v in params)
        url = f"{self._base_url}{path}?{qs}"
        token = self._get_token()
        headers = {"Authorization": f"Bearer {token}"}
        try:
            resp = requests.get(url, headers=headers, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json() if resp.content else []
        except requests.RequestException as e:
            logger.warning("CDEK get_cities failed: %s", e)
            raise CdekAPIError(
                f"Не удалось получить список городов: {e}",
                status_code=getattr(e.response, "status_code", None),
            ) from e
