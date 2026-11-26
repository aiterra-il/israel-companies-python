import sys

from israel_companies import check_company_number, get_company, get_data_date, search_companies

sys.stdout.reconfigure(encoding="utf-8")

print(check_company_number("52-002563-6"))
print(check_company_number("520025637")["message"])
print(check_company_number("580000008")["message"])
company = get_company("520025636")
print({name: company[name] for name in ("name", "english_name", "type_label", "status", "tone", "founded")})
print([(item["number"], item["name"], item["tone"]) for item in search_companies("טבע", limit=3)])
print(get_data_date())
