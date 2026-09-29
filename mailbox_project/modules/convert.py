import pandas as pd

EXCEL = "names.xlsx"
SKIP_SHEETS = {"Зведення"}   # сводку пропускаем

firstnames = []   # name, country, gender, is_used
lastnames  = []   # name, country, is_used

xl = pd.ExcelFile(EXCEL)
print("Листы:", xl.sheet_names)

for sheet in xl.sheet_names:
    if sheet in SKIP_SHEETS:
        continue
    country = sheet.strip()          # код страны = имя листа: AU, CA, CH, DK...
    df = pd.read_excel(EXCEL, sheet_name=sheet, dtype=str)

    cols = list(df.columns)
    if len(cols) < 3:
        print(f"!! Пропускаю {sheet}: меньше 3 колонок -> {cols}")
        continue

    male_col, female_col, surname_col = cols[0], cols[1], cols[2]

    for v in df[male_col].dropna():
        v = str(v).strip()
        if v:
            firstnames.append((v, country, "M", "f"))

    for v in df[female_col].dropna():
        v = str(v).strip()
        if v:
            firstnames.append((v, country, "F", "f"))

    for v in df[surname_col].dropna():
        v = str(v).strip()
        if v:
            lastnames.append((v, country, "f"))

    print(f"{sheet}: +{len(df)} строк")

pd.DataFrame(firstnames, columns=["name", "country", "gender", "is_used"]).to_csv(
    "firstname.csv", index=False, encoding="utf-8"
)
pd.DataFrame(lastnames, columns=["name", "country", "is_used"]).to_csv(
    "lastname.csv", index=False, encoding="utf-8"
)

print(f"\nИтог: firstname={len(firstnames)}, lastname={len(lastnames)}")