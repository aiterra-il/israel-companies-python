# israel-companies · חיפוש חברות ברשם החברות

[![PyPI](https://img.shields.io/pypi/v/israel-companies?color=2447D6)](https://pypi.org/project/israel-companies/)
[![tests](https://github.com/aiterra-il/israel-companies-python/actions/workflows/tests.yml/badge.svg)](https://github.com/aiterra-il/israel-companies-python/actions/workflows/tests.yml)
[![license](https://img.shields.io/badge/license-MIT-3E96F9)](LICENSE)
![dependencies](https://img.shields.io/badge/dependencies-0-060B22)

Look up an Israeli company by number (ח.פ.) or by name, straight from the open database of the **Registrar of Companies** (רשם החברות) on data.gov.il, for Python. No API key, no sign-up. The package checks the check digit before it asks the database, and explains every company status in plain Hebrew.

This is the Python edition of the [israel-companies](https://www.npmjs.com/package/israel-companies) package on npm. The tests compare the number check, the record cleanup, the name query and the ranking of search results with the answers of the JavaScript version.

- **Know your customer and supplier checks.** Is the company active, struck off, in liquidation, marked as a violator of the Companies Law?
- **Forms and invoices.** Catch a mistyped ח.פ. before it reaches the database.
- **CRM and onboarding.** Fill in the company name, type and address from the number.

## Install

```bash
pip install israel-companies
```

No dependencies. Python 3.10 or newer. Type hints included.

## Use

```python
from israel_companies import check_company_number, get_company, search_companies

check_company_number("52-002563-6")
# {'valid': True, 'number': '520025636'}

check_company_number("520025637")["message"]
# 'ספרת הביקורת לא מתאימה למספר, כנראה יש בו טעות הקלדה.'

check_company_number("580000008")["message"]
# 'לפי הקידומת 58, זה מספר של עמותה, ולא של חברה.'

company = get_company("520025636")
company["name"], company["english_name"], company["type_label"], company["status"], company["tone"], company["founded"]
# ('בנק ירושלים בע״מ', 'BANK OF JERUSALEM LTD.', 'חברה ציבורית', 'פעילה', 'active', '1963-12-12')

[(item["number"], item["name"]) for item in search_companies("טבע", limit=2)]
# [('520013954', 'טבע תעשיות פרמצבטיות בע״מ'),
#  ('512850900', 'טבע עוף 2000 חברה לשיווק עופות ומוצרי בשר (1999) בע״מ')]
```

`search_companies()` searches Hebrew names, or English names when the query has only Latin letters, puts names that start with the first word first and active companies before closed ones. `get_data_date()` returns the time data.gov.il last updated the database.

### Errors

`CompanyLookupError` with `code` set to `invalid-number` (the number failed the check, no request was sent), `network`, `timeout`, `blocked`, `server` or `format`.

## API

| Function | What it does |
|---|---|
| `get_company(number)` | The company by ח.פ., or `None` when the registrar has no such number |
| `search_companies(name, *, limit=20)` | Companies by name, best matches first |
| `check_company_number(value)` | Check the length, the check digit and the prefix, with a Hebrew message |
| `is_valid_israeli_id(value)` | The check digit of a ת״ז, ח.פ. or עמותה number |
| `entity_of(number)` | The kind of corporation by prefix: company, partnership, amuta |
| `status_info(status)` | A plain Hebrew explanation of a registrar status |
| `get_data_date()` | When the registrar data was last updated |
| `to_company(record)` | Turn a raw data.gov.il record into a clean dict |

Every function that goes to the network takes `timeout=` in seconds (15 by default).

## Source of the data

[The Registrar of Companies database](https://data.gov.il/he/datasets/ministry_of_justice/ica_companies) of the Israeli Ministry of Justice on data.gov.il, used under the [data.gov.il terms of use](https://data.gov.il/terms-of-use). The database is updated daily. This is a community library with no official connection to the Registrar of Companies; for a legal decision, order an official extract from the registrar.

<div dir="rtl">

## בעברית

חיפוש חברה ישראלית לפי מספר ח.פ. או לפי שם, ישר מהמאגר הפתוח של **רשם החברות** ב-data.gov.il, לפייתון. אין צורך במפתח API, בהרשמה או בתשלום. הספרייה בודקת את ספרת הביקורת לפני הפנייה למאגר ומסבירה כל סטטוס בעברית פשוטה: פעילה, מחוקה, בפירוק, מפרת חוק.

לנסות בלי קוד: **[בדיקת חברה לפי ח.פ. או שם](https://www.aiterra.co.il/tools/company-lookup)** באתר של Aiterra.

</div>

## Licence

MIT for the code. The data belongs to the State of Israel and is used under the data.gov.il terms of use. Built by [Aiterra](https://www.aiterra.co.il), a software studio in Israel that builds AI agents, voice agents and websites.
