from __future__ import annotations

import json
import math
import re
import socket
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any, Literal, Optional, TypedDict, Union, cast

from ._data import CORPORATE_PREFIXES, STATUS_CATALOG, VIOLATION_CATALOG

__version__ = "1.0.0"

__all__ = [
    "COMPANIES_RESOURCE_ID",
    "COMPANY_PREFIXES",
    "CORPORATE_PREFIXES",
    "DATASET_URL",
    "DATA_API",
    "STATUS_CATALOG",
    "VIOLATION_CATALOG",
    "Company",
    "CompanyLookupError",
    "build_name_query",
    "check_company_number",
    "clean_text",
    "entity_of",
    "get_company",
    "get_data_date",
    "is_valid_israeli_id",
    "search_companies",
    "status_info",
    "to_company",
    "type_info",
]

COMPANIES_RESOURCE_ID = "f004176c-b85f-4542-8901-7b3176f9a054"
DATA_API = "https://data.gov.il/api/3/action"
DATASET_URL = "https://data.gov.il/he/datasets/ministry_of_justice/ica_companies"
COMPANY_PREFIXES = ("51", "52", "56")

DEFAULT_TIMEOUT = 15.0
USER_AGENT = "datagov-external-client"
_MAX_NAME_TOKENS = 8
_NAME_MIN_LETTERS = 2

_FIELD = {
    "number": "מספר חברה",
    "name": "שם חברה",
    "english_name": "שם באנגלית",
    "type": "סוג תאגיד",
    "status": "סטטוס חברה",
    "sub_status": "תת סטטוס",
    "violation": "מפרה",
    "description": "תאור חברה",
    "purpose": "מטרת החברה",
    "founded": "תאריך התאגדות",
    "government": "חברה ממשלתית",
    "liability": "מגבלות",
    "last_report": "שנה אחרונה של דוח שנתי (שהוגש)",
    "city": "שם עיר",
    "street": "שם רחוב",
    "house": "מספר בית",
    "zip": "מיקוד",
    "po_box": "ת.ד.",
    "country": "מדינה",
    "care_of": "אצל",
}

_TYPE_CATALOG = {
    "ישראלית חברה פרטית": {"label": "חברה פרטית", "english": "Private company"},
    "ישראלית חברה ציבורית": {"label": "חברה ציבורית", "english": "Public company"},
    "ישראלית חברה אגח": {"label": "חברת אג״ח", "english": "Bond-issuing company"},
    "חוץ חברה פרטית": {"label": "חברת חוץ", "english": "Foreign company"},
    "חוץ חברה ציבורית": {"label": "חברת חוץ ציבורית", "english": "Foreign public company"},
}

_JS_SPACE = (
    "\t\n\v\f\r \u00a0\u1680"
    + "".join(chr(code) for code in range(0x2000, 0x200B))
    + "\u2028\u2029\u202f\u205f\u3000\ufeff"
)
_SEPARATORS = re.compile("[" + _JS_SPACE + "\\-\u2010-\u2015\u05be./\u200e\u200f\u202a-\u202e]")
_SPACES = re.compile("[" + _JS_SPACE + "]+")
_HEBREW_LETTER = re.compile("[א-ת]")
_LATIN_LETTER = re.compile("[a-z]")
_DIGITS = re.compile("[0-9]+")
_ID_DIGITS = re.compile("[0-9]{1,9}")
_ZEROS = re.compile("0+")
_DATE = re.compile(r"([0-9]{1,2})/([0-9]{1,2})/([0-9]{4})")
_GERSHAYIM = re.compile("([א-ת])~(?=[א-ת])")
_DECIMAL = re.compile(r"[+-]?(?:[0-9]+\.?[0-9]*|\.[0-9]+)(?:[eE][+-]?[0-9]+)?")
_OFFSET = re.compile(r"Z$|[+-][0-9]{2}:?[0-9]{2}$")
_SUFFIX_TOKENS = {"בעמ", "ltd", "limited"}
_WEIGHTS = (1, 2, 1, 2, 1, 2, 1, 2, 1)
_TONE_ORDER = {"active": 0, "caution": 1, "unknown": 2, "ended": 3}

Tone = Literal["active", "caution", "ended", "unknown"]
Violation = Literal["none", "warning", "violator"]
ErrorCode = Literal["invalid-number", "network", "timeout", "blocked", "server", "format"]


class Address(TypedDict):
    street: str
    city: str
    zip: str
    country: str


class Company(TypedDict):
    number: str
    name: str
    english_name: str
    type: str
    type_label: str
    status: str
    tone: Tone
    sub_statuses: list[str]
    violation: Violation
    description: str
    purpose: str
    founded: str
    government: bool
    limited_liability: bool
    last_report_year: Optional[int]
    address: Address
    care_of: str
    po_box: str


class NameQuery(TypedDict):
    field: str
    tsquery: str


class CompanyLookupError(Exception):
    def __init__(self, code: ErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code


def _js_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        if value.is_integer() and abs(value) < 1e21:
            return str(int(value))
        return repr(value)
    return str(value)


def _digits_of(value: Any) -> str:
    return _SEPARATORS.sub("", _js_text(value))


def is_valid_israeli_id(value: Union[str, int]) -> bool:
    digits = _digits_of(value)
    if not _ID_DIGITS.fullmatch(digits) or _ZEROS.fullmatch(digits):
        return False
    total = 0
    for index, char in enumerate(digits.zfill(9)):
        product = int(char) * _WEIGHTS[index]
        total += product - 9 if product > 9 else product
    return total % 10 == 0


def entity_of(number: Union[str, int]) -> Optional[dict[str, str]]:
    digits = _digits_of(number)
    return next((dict(item) for item in CORPORATE_PREFIXES if digits.startswith(item["prefix"])), None)


def check_company_number(value: Union[str, int]) -> dict[str, Any]:
    digits = _digits_of(value)
    if not digits:
        return {"valid": False, "reason": "empty", "message": "לא הוקלד מספר."}
    if not _DIGITS.fullmatch(digits):
        return {"valid": False, "reason": "not-digits", "message": "במספר חברה יש רק ספרות."}
    if len(digits) != 9:
        return {"valid": False, "reason": "length", "message": f"מספר חברה הוא 9 ספרות, והוקלדו {len(digits)}."}
    if not is_valid_israeli_id(digits):
        return {"valid": False, "reason": "checksum", "message": "ספרת הביקורת לא מתאימה למספר, כנראה יש בו טעות הקלדה."}
    if digits[:2] in COMPANY_PREFIXES:
        return {"valid": True, "number": digits}
    entity = entity_of(digits)
    if entity:
        return {
            "valid": False,
            "reason": "not-a-company",
            "entity": entity,
            "message": f"לפי הקידומת {entity['prefix']}, זה מספר של {entity['label']}, ולא של חברה.",
        }
    return {
        "valid": False,
        "reason": "not-a-company",
        "entity": None,
        "message": "מספר שלא מתחיל ב-51, 52 או 56 הוא לא מספר חברה. עוסק שהוא אדם פרטי רשום לפי תעודת הזהות שלו.",
    }


def clean_text(value: Any) -> str:
    text = _GERSHAYIM.sub("\\1״", _js_text(value)).replace("~", '"')
    return _SPACES.sub(" ", text).strip(_JS_SPACE)


def _iso_date(value: Any) -> str:
    match = _DATE.fullmatch(clean_text(value))
    if not match:
        return ""
    day, month, year = match.groups()
    return f"{year}-{month.zfill(2)}-{day.zfill(2)}"


def _year_of(value: Any) -> Optional[int]:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
    else:
        text = str(value).strip(_JS_SPACE)
        number = float(text) if _DECIMAL.fullmatch(text) else (0.0 if not text else math.nan)
    return int(number) if math.isfinite(number) and number.is_integer() and number > 1900 else None


def _violation_of(value: str) -> Violation:
    if value == "מפרה":
        return "violator"
    if value == "התראה":
        return "warning"
    return "none"


def status_info(status: str) -> dict[str, str]:
    return next((dict(entry) for entry in STATUS_CATALOG if entry["status"] == status), {"status": status, "tone": "unknown", "text": ""})


def type_info(type_name: str) -> dict[str, str]:
    return dict(_TYPE_CATALOG.get(type_name, {"label": type_name, "english": ""}))


def to_company(record: Mapping[str, Any]) -> Company:
    def field(name: str) -> str:
        return clean_text(record.get(_FIELD[name]))

    status = field("status")
    type_name = field("type")
    violation = _violation_of(field("violation"))
    base_tone = status_info(status)["tone"]
    sub_statuses = list(dict.fromkeys(part.strip(_JS_SPACE) for part in field("sub_status").split(";") if part.strip(_JS_SPACE)))
    return {
        "number": field("number"),
        "name": field("name"),
        "english_name": field("english_name"),
        "type": type_name,
        "type_label": type_info(type_name)["label"],
        "status": status,
        "tone": cast(Tone, "caution" if base_tone == "active" and violation != "none" else base_tone),
        "sub_statuses": sub_statuses,
        "violation": violation,
        "description": field("description"),
        "purpose": field("purpose"),
        "founded": _iso_date(record.get(_FIELD["founded"])),
        "government": field("government") == "כן",
        "limited_liability": field("liability") == "מוגבלת",
        "last_report_year": _year_of(record.get(_FIELD["last_report"])),
        "address": {
            "street": " ".join(part for part in (field("street"), field("house")) if part),
            "city": field("city"),
            "zip": field("zip"),
            "country": field("country"),
        },
        "care_of": field("care_of"),
        "po_box": field("po_box"),
    }


def _tokens_of(raw: Any) -> list[str]:
    text = unicodedata.normalize("NFC", _js_text(raw))
    text = "".join(char for char in text if unicodedata.category(char)[0] != "M").lower()
    tokens: list[str] = []
    current: list[str] = []
    for char in text:
        if unicodedata.category(char)[0] in "LN":
            current.append(char)
        elif current:
            tokens.append("".join(current))
            current = []
    if current:
        tokens.append("".join(current))
    return tokens


def _without_suffixes(tokens: Sequence[str]) -> list[str]:
    kept = []
    for index, token in enumerate(tokens):
        if token in _SUFFIX_TOKENS:
            continue
        if token == "בע" and index + 1 < len(tokens) and tokens[index + 1] == "מ":
            continue
        if token == "מ" and index > 0 and tokens[index - 1] == "בע":
            continue
        kept.append(token)
    return kept


def build_name_query(raw: str) -> Optional[NameQuery]:
    tokens = _without_suffixes(_tokens_of(raw))
    hebrew = any(_HEBREW_LETTER.search(token) for token in tokens)
    usable = ([token for token in tokens if not _LATIN_LETTER.search(token)] if hebrew else tokens)[:_MAX_NAME_TOKENS]
    if len("".join(usable)) < _NAME_MIN_LETTERS:
        return None
    english = not hebrew and any(_LATIN_LETTER.search(token) for token in usable)
    last = len(usable) - 1
    tsquery = " & ".join(f"{token}:*" if index == last and len(token) > 1 else token for index, token in enumerate(usable))
    return {"field": _FIELD["english_name"] if english else _FIELD["name"], "tsquery": tsquery}


def _search_url(params: Mapping[str, str]) -> str:
    query = {
        "resource_id": COMPANIES_RESOURCE_ID,
        "fields": ",".join(_FIELD.values()),
        "include_total": "false",
        **params,
    }
    encoded = urllib.parse.urlencode(query, quote_via=urllib.parse.quote_plus, safe="*")
    return f"{DATA_API}/datastore_search?{encoded.replace('~', '%7E')}"


def _get_json(url: str, timeout: float) -> Any:
    request = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
    except urllib.error.HTTPError as error:
        if error.code in (403, 429):
            raise CompanyLookupError("blocked", "data.gov.il is rate limiting requests") from error
        raise CompanyLookupError("server", f"data.gov.il answered {error.code}") from error
    except (TimeoutError, socket.timeout) as error:
        raise CompanyLookupError("timeout", "data.gov.il did not answer in time") from error
    except urllib.error.URLError as error:
        if isinstance(error.reason, (TimeoutError, socket.timeout)):
            raise CompanyLookupError("timeout", "data.gov.il did not answer in time") from error
        raise CompanyLookupError("network", "Could not reach data.gov.il") from error
    except OSError as error:
        raise CompanyLookupError("network", "Could not reach data.gov.il") from error
    try:
        return json.loads(body)
    except ValueError as error:
        raise CompanyLookupError("format", "data.gov.il returned something that is not JSON") from error


def _fetch_records(url: str, timeout: float) -> list[dict[str, Any]]:
    data = _get_json(url, timeout)
    result = data.get("result") if isinstance(data, dict) else None
    records = result.get("records") if isinstance(result, dict) else None
    if not isinstance(data, dict) or data.get("success") is not True or not isinstance(records, list):
        raise CompanyLookupError("format", "Unexpected data.gov.il response")
    return records


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def get_company(number: Union[str, int], *, timeout: float = DEFAULT_TIMEOUT) -> Optional[Company]:
    check = check_company_number(number)
    if not check["valid"]:
        raise CompanyLookupError("invalid-number", check["message"])
    url = _search_url({"filters": _json({_FIELD["number"]: int(check["number"])}), "limit": "1"})
    records = _fetch_records(url, timeout)
    return to_company(records[0]) if records else None


def _rank_by_name(companies: Sequence[Company], raw: str) -> list[Company]:
    first = next(iter(_without_suffixes(_tokens_of(raw))), "")
    english = not _HEBREW_LETTER.search(_js_text(raw)) and bool(_LATIN_LETTER.search(_js_text(raw).lower()))

    def leading_match(company: Company) -> int:
        leading = next(iter(_tokens_of(company["english_name"] if english else company["name"])), "")
        if not first or not leading.startswith(first):
            return 2
        return 0 if leading == first else 1

    ranked = sorted(
        enumerate(companies),
        key=lambda entry: (leading_match(entry[1]), _TONE_ORDER[entry[1]["tone"]], entry[0]),
    )
    return [company for _, company in ranked]


def _search_url_for(name: str, limit: int) -> Optional[str]:
    query = build_name_query(name)
    if not query:
        return None
    return _search_url(
        {
            "q": _json({query["field"]: query["tsquery"]}),
            "plain": "false",
            "sort": '"סוג תאגיד" desc, "קוד סטטוס חברה" asc',
            "limit": str(max(limit, 100)),
        }
    )


def search_companies(name: str, *, limit: int = 20, timeout: float = DEFAULT_TIMEOUT) -> list[Company]:
    url = _search_url_for(name, limit)
    if url is None:
        return []
    return _rank_by_name([to_company(record) for record in _fetch_records(url, timeout)], name)[:limit]


def get_data_date(*, timeout: float = DEFAULT_TIMEOUT) -> Optional[datetime]:
    try:
        data = _get_json(f"{DATA_API}/resource_show?id={COMPANIES_RESOURCE_ID}", timeout)
    except CompanyLookupError as error:
        if error.code in ("server", "blocked"):
            return None
        raise
    modified = data.get("result", {}).get("last_modified") if isinstance(data, dict) else None
    if not modified:
        return None
    stamp = modified if _OFFSET.search(modified) else f"{modified}Z"
    parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
