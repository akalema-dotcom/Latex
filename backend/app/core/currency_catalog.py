"""
app/core/currency_catalog.py
============================
Static catalog of supported ISO 4217 currencies.

This is the single source of truth for "which currencies does the system know
about at boot time". Additional currencies can be added by inserting rows into
the ``currencies`` table at runtime — the catalog is just the seed.

USD is the system default — but it is NOT the only currency.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CurrencyInfo:
    code: str             # ISO 4217 code, e.g. "USD"
    name: str
    symbol: str
    decimal_places: int
    country_code: str     # ISO 3166-1 alpha-2 of the primary country
    locale: str           # BCP 47 locale, e.g. "en-US"
    is_active: bool = True


# IMPORTANT: decimal_places follows ISO 4217.
#   - JPY, KRW, UGX, RWF, VND, etc. use 0 decimal places.
#   - Most others use 2.
#   - Bahrain, Iraq, Jordan, Kuwait, Oman use 3.
_CATALOG: tuple[CurrencyInfo, ...] = (
    # ----- Africa -----
    CurrencyInfo("UGX", "Ugandan Shilling",        "USh",  0, "UG", "en-UG"),
    CurrencyInfo("KES", "Kenyan Shilling",         "KSh",  2, "KE", "en-KE"),
    CurrencyInfo("TZS", "Tanzanian Shilling",      "TSh",  0, "TZ", "en-TZ"),
    CurrencyInfo("RWF", "Rwandan Franc",           "FRw",  0, "RW", "en-RW"),
    CurrencyInfo("NGN", "Nigerian Naira",          "₦",    2, "NG", "en-NG"),
    CurrencyInfo("ZAR", "South African Rand",      "R",    2, "ZA", "en-ZA"),
    CurrencyInfo("EGP", "Egyptian Pound",          "E£",   2, "EG", "ar-EG"),
    CurrencyInfo("GHS", "Ghanaian Cedi",           "GH₵",  2, "GH", "en-GH"),
    CurrencyInfo("ETB", "Ethiopian Birr",          "Br",   2, "ET", "en-ET"),
    CurrencyInfo("MAD", "Moroccan Dirham",         "DH",   2, "MA", "fr-MA"),
    CurrencyInfo("XOF", "West African CFA Franc",  "CFA",  0, "SN", "fr-SN"),
    CurrencyInfo("XAF", "Central African CFA Franc","FCFA",0, "CM", "fr-CM"),
    CurrencyInfo("ZMW", "Zambian Kwacha",          "ZK",   2, "ZM", "en-ZM"),
    CurrencyInfo("BWP", "Botswana Pula",           "P",    2, "BW", "en-BW"),
    CurrencyInfo("MUR", "Mauritian Rupee",         "₨",    2, "MU", "en-MU"),
    CurrencyInfo("LYD", "Libyan Dinar",            "LD",   3, "LY", "ar-LY"),
    CurrencyInfo("SDD", "Sudanese Pound",          "SDG",  2, "SD", "ar-SD"),

    # ----- Asia -----
    CurrencyInfo("INR", "Indian Rupee",            "₹",    2, "IN", "en-IN"),
    CurrencyInfo("JPY", "Japanese Yen",            "¥",    0, "JP", "ja-JP"),
    CurrencyInfo("CNY", "Chinese Yuan",            "¥",    2, "CN", "zh-CN"),
    CurrencyInfo("KRW", "South Korean Won",        "₩",    0, "KR", "ko-KR"),
    CurrencyInfo("SGD", "Singapore Dollar",        "S$",   2, "SG", "en-SG"),
    CurrencyInfo("HKD", "Hong Kong Dollar",        "HK$",  2, "HK", "en-HK"),
    CurrencyInfo("THB", "Thai Baht",               "฿",    2, "TH", "th-TH"),
    CurrencyInfo("MYR", "Malaysian Ringgit",       "RM",   2, "MY", "en-MY"),
    CurrencyInfo("IDR", "Indonesian Rupiah",       "Rp",   0, "ID", "id-ID"),
    CurrencyInfo("PHP", "Philippine Peso",         "₱",    2, "PH", "en-PH"),
    CurrencyInfo("VND", "Vietnamese Dong",         "₫",    0, "VN", "vi-VN"),
    CurrencyInfo("PKR", "Pakistani Rupee",         "₨",    2, "PK", "en-PK"),
    CurrencyInfo("BDT", "Bangladeshi Taka",        "৳",    2, "BD", "en-BD"),
    CurrencyInfo("AED", "UAE Dirham",              "AED",  2, "AE", "ar-AE"),
    CurrencyInfo("SAR", "Saudi Riyal",             "SAR",  2, "SA", "ar-SA"),
    CurrencyInfo("QAR", "Qatari Riyal",            "QAR",  2, "QA", "ar-QA"),
    CurrencyInfo("KWD", "Kuwaiti Dinar",           "KWD",  3, "KW", "ar-KW"),
    CurrencyInfo("BHD", "Bahraini Dinar",          "BHD",  3, "BH", "ar-BH"),
    CurrencyInfo("OMR", "Omani Rial",              "OMR",  3, "OM", "ar-OM"),
    CurrencyInfo("JOD", "Jordanian Dinar",         "JOD",  3, "JO", "ar-JO"),
    CurrencyInfo("ILS", "Israeli New Shekel",      "₪",    2, "IL", "he-IL"),
    CurrencyInfo("LKR", "Sri Lankan Rupee",        "Rs",   2, "LK", "en-LK"),
    CurrencyInfo("NPR", "Nepalese Rupee",          "Rs",   2, "NP", "en-NP"),

    # ----- Europe -----
    CurrencyInfo("EUR", "Euro",                    "€",    2, "DE", "de-DE"),
    CurrencyInfo("GBP", "Pound Sterling",          "£",    2, "GB", "en-GB"),
    CurrencyInfo("CHF", "Swiss Franc",             "CHF",  2, "CH", "de-CH"),
    CurrencyInfo("SEK", "Swedish Krona",           "kr",   2, "SE", "sv-SE"),
    CurrencyInfo("NOK", "Norwegian Krone",         "kr",   2, "NO", "nb-NO"),
    CurrencyInfo("DKK", "Danish Krone",            "kr",   2, "DK", "da-DK"),
    CurrencyInfo("PLN", "Polish Zloty",            "zł",   2, "PL", "pl-PL"),
    CurrencyInfo("CZK", "Czech Koruna",            "Kč",   2, "CZ", "cs-CZ"),
    CurrencyInfo("HUF", "Hungarian Forint",        "Ft",   0, "HU", "hu-HU"),
    CurrencyInfo("RON", "Romanian Leu",            "lei",  2, "RO", "ro-RO"),
    CurrencyInfo("BGN", "Bulgarian Lev",           "лв",   2, "BG", "bg-BG"),
    CurrencyInfo("HRK", "Croatian Kuna",           "kn",   2, "HR", "hr-HR"),
    CurrencyInfo("TRY", "Turkish Lira",            "₺",    2, "TR", "tr-TR"),
    CurrencyInfo("RUB", "Russian Ruble",           "₽",    2, "RU", "ru-RU"),
    CurrencyInfo("UAH", "Ukrainian Hryvnia",       "₴",    2, "UA", "uk-UA"),
    CurrencyInfo("ISK", "Icelandic Króna",         "kr",   0, "IS", "is-IS"),

    # ----- North America -----
    CurrencyInfo("USD", "United States Dollar",    "$",    2, "US", "en-US"),
    CurrencyInfo("CAD", "Canadian Dollar",         "C$",   2, "CA", "en-CA"),
    CurrencyInfo("MXN", "Mexican Peso",            "$",    2, "MX", "es-MX"),

    # ----- South America -----
    CurrencyInfo("BRL", "Brazilian Real",          "R$",   2, "BR", "pt-BR"),
    CurrencyInfo("ARS", "Argentine Peso",          "$",    2, "AR", "es-AR"),
    CurrencyInfo("COP", "Colombian Peso",          "$",    0, "CO", "es-CO"),
    CurrencyInfo("CLP", "Chilean Peso",            "$",    0, "CL", "es-CL"),
    CurrencyInfo("PEN", "Peruvian Sol",            "S/",   2, "PE", "es-PE"),
    CurrencyInfo("UYU", "Uruguayan Peso",          "$U",   2, "UY", "es-UY"),
    CurrencyInfo("VES", "Venezuelan Bolívar",      "Bs",   2, "VE", "es-VE"),

    # ----- Oceania -----
    CurrencyInfo("AUD", "Australian Dollar",       "A$",   2, "AU", "en-AU"),
    CurrencyInfo("NZD", "New Zealand Dollar",      "NZ$",  2, "NZ", "en-NZ"),
    CurrencyInfo("FJD", "Fijian Dollar",           "FJ$",  2, "FJ", "en-FJ"),
)


# Pre-built lookup dictionaries for fast validation.
_CATALOG_BY_CODE: dict[str, CurrencyInfo] = {c.code: c for c in _CATALOG}


def list_currencies() -> list[CurrencyInfo]:
    """Return the full static catalog."""
    return list(_CATALOG)


def get_currency(code: str) -> CurrencyInfo | None:
    """Look up a currency by its ISO 4217 code (case-insensitive)."""
    if not code:
        return None
    return _CATALOG_BY_CODE.get(code.upper())


def is_valid_currency_code(code: str) -> bool:
    return code is not None and code.upper() in _CATALOG_BY_CODE


def default_currency() -> CurrencyInfo:
    """USD — the system default. NOT the only currency."""
    return _CATALOG_BY_CODE["USD"]


def default_decimal_places(code: str) -> int:
    """Return the standard ISO 4217 number of decimal places for a currency."""
    info = get_currency(code)
    return info.decimal_places if info else 2
