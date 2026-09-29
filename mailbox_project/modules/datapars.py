from names_dataset import NameDataset
from faker import Faker
import openpyxl
from openpyxl.styles import Font

# names-dataset не содержит AU и NZ вовсе - для них используем Faker (локальные списки имён)
FAKER_FALLBACK = {"AU": "en_AU", "NZ": "en_NZ"}

# --- настройки ---


nd = NameDataset()
COUNTRIES = {code: code for code in nd.get_country_codes(alpha_2=True)}
COUNTRIES.update({"AU": "AU", "NZ": "NZ"})
print("Loading dataset (occupies ~1-2 GB RAM, take a few seconds)...")


wb = openpyxl.Workbook()
wb.remove(wb.active)
header_font = Font(bold=True)

stats = []

for code, label in COUNTRIES.items():
    if code in FAKER_FALLBACK:
        # names-dataset не покрывает эту страну - берём из Faker (нет в реестре, меньше объём)
        f = Faker(FAKER_FALLBACK[code])
        male_list = female_list = last_list = []
        for p in f.get_providers():
            if "person" in p.__class__.__module__:
                male_list = sorted(set(getattr(p, "first_names_male", {}) or {}))
                female_list = sorted(set(getattr(p, "first_names_female", {}) or {}))
                last_list = sorted(set(getattr(p, "last_names", {}) or {}))
    else:
        male = nd.get_top_names(n=100000, use_first_names=True,
                                 country_alpha2=code, gender="Male")
        female = nd.get_top_names(n=100000, use_first_names=True,
                                   country_alpha2=code, gender="Female")
        last = nd.get_top_names(n=100000, use_first_names=False,
                                 country_alpha2=code)

        male_list = male.get(code, {}).get("M", [])
        female_list = female.get(code, {}).get("F", [])
        last_list = last.get(code, [])

    ws = wb.create_sheet(title=code)
    ws["A1"], ws["B1"], ws["C1"] = "Ім'я (чоловіче)", "Ім'я (жіноче)", "Прізвище"
    for c in ("A1", "B1", "C1"):
        ws[c].font = header_font

    maxlen = max(len(male_list), len(female_list), len(last_list))
    for i in range(maxlen):
        if i < len(male_list):
            ws.cell(row=i + 2, column=1, value=male_list[i])
        if i < len(female_list):
            ws.cell(row=i + 2, column=2, value=female_list[i])
        if i < len(last_list):
            ws.cell(row=i + 2, column=3, value=last_list[i])

    for col, w in zip("ABC", [22, 22, 22]):
        ws.column_dimensions[col].width = w
    ws.freeze_panes = "A2"

    stats.append((label, code, len(male_list), len(female_list), len(last_list)))
    print(f"{label} ({code}): male={len(male_list)} female={len(female_list)} last={len(last_list)}")

# сводный лист
ws_sum = wb.create_sheet(title="Зведення", index=0)
ws_sum.append(["Країна", "Код", "Чол. імена", "Жін. імена", "Прізвища"])
for cell in ws_sum[1]:
    cell.font = header_font
for row in stats:
    ws_sum.append(row)
for col, w in zip("ABCDE", [22, 8, 14, 14, 12]):
    ws_sum.column_dimensions[col].width = w

wb.save("names_by_country.xlsx")
print("Saved -> names_by_country.xlsx")