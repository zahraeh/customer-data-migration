"""Generate the fictional legacy exports used throughout this project.

Maison Verte Services is a fictional heating & plumbing maintenance company
(Bourg-en-Bresse / Lyon area). Every name, number and company here is
generated; SIRETs are random numbers that merely pass the checksum.

The mess is deliberate and modelled on what real legacy exports look like:
Windows-1252 + semicolons, postcodes whose leading zero Excel removed,
five ways of writing a phone number, day-first dates, French amounts with
dot thousands separators, duplicate companies, and contacts/contracts that
point at accounts deleted years ago.

Run: python data/generate_sample.py   (deterministic, seed 42)
"""
from __future__ import annotations

import csv
import random
from datetime import date, timedelta
from pathlib import Path

import phonenumbers

OUT = Path(__file__).parent / "source"
rng = random.Random(42)

CITIES = [
    ("01000", "Bourg-en-Bresse", 14), ("01100", "Oyonnax", 6), ("01300", "Belley", 4),
    ("01500", "Ambérieu-en-Bugey", 6), ("01600", "Trévoux", 4), ("69001", "Lyon", 8),
    ("69003", "Lyon", 10), ("69100", "Villeurbanne", 10), ("69400", "Villefranche-sur-Saône", 10),
    ("71000", "Mâcon", 10), ("38200", "Vienne", 8), ("69500", "Bron", 10),
]
SURNAMES = ["Martin", "Bernard", "Dubois", "Thomas", "Robert", "Richard", "Petit", "Durand", "Leroy",
            "Moreau", "Simon", "Laurent", "Lefèvre", "Michel", "Garcia", "David", "Bertrand", "Roux",
            "Vincent", "Fournier", "Morel", "Girard", "André", "Mercier", "Dupont", "Lambert", "Bonnet",
            "François", "Martinez", "Legrand", "Garnier", "Faure", "Rousseau", "Blanc", "Guérin", "Muller",
            "Henry", "Roussel", "Nicolas", "Perrin", "Morin", "Mathieu", "Clément", "Gauthier", "Dumont",
            "Lopez", "Fontaine", "Chevalier", "Robin", "Masson", "Sanchez", "Boyer", "Denis", "Lemaire"]
FIRST = ["Jean", "Marie", "Pierre", "Sophie", "Nicolas", "Isabelle", "Thomas", "Nathalie", "Julien",
         "Céline", "Antoine", "Camille", "Hélène", "François", "Émilie", "Karim", "Inès", "Léa", "Hugo",
         "Chloé", "Mathieu", "Aurélie", "Yannick", "Sandrine", "Rémi", "Manon", "Olivier", "Noémie"]
TRADES = ["Boulangerie", "Pharmacie", "Cabinet dentaire", "Garage", "Restaurant", "Hôtel", "Crèche",
          "Salon de coiffure", "Fromagerie", "Cabinet comptable", "Boucherie", "Librairie", "Auto-école"]
ROLES = ["Gérant", "Gérante", "Responsable technique", "Directrice", "Assistante de direction",
         "Comptable", "Responsable des achats"]
OWNERS = ["Claire Moreau", "Julien Petit", "Sophie Laurent", "Karim Benali", "Élodie Garnier"]
DOMAINS = ["gmail.com", "orange.fr", "free.fr", "laposte.net", "sfr.fr", "wanadoo.fr"]


def slug(text: str) -> str:
    import unicodedata
    t = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return "".join(c if c.isalnum() else "-" for c in t).strip("-").replace("--", "-")


def siret() -> str:
    while True:
        digits = [rng.randint(0, 9) for _ in range(13)]
        for check in range(10):
            candidate = digits + [check]
            total = 0
            for i, n in enumerate(reversed(candidate)):
                if i % 2 == 1:
                    n *= 2
                    n = n - 9 if n > 9 else n
                total += n
            if total % 10 == 0:
                return "".join(map(str, candidate))


def phone_number(prefixes) -> str:
    while True:
        num = rng.choice(prefixes) + "".join(str(rng.randint(0, 9)) for _ in range(10 - len(prefixes[0])))
        if phonenumbers.is_valid_number(phonenumbers.parse(num, "FR")):
            return num


def fmt_phone(num: str) -> str:
    """The same number, written the way different people typed it over ten years."""
    pairs = " ".join(num[i:i + 2] for i in range(0, 10, 2))
    r = rng.random()
    if r < 0.45:
        return pairs
    if r < 0.63:
        return num
    if r < 0.78:
        return pairs.replace(" ", ".")
    if r < 0.86:
        return "+33 " + num[1] + " " + " ".join(num[i:i + 2] for i in range(2, 10, 2))
    if r < 0.91:
        return "33" + num[1:]
    if r < 0.97:
        return ""
    return pairs[:11]  # truncated, genuinely invalid


def fmt_postcode(pc: str) -> str:
    # Excel opened the export as numbers at some point: 01000 → 1000.
    if pc.startswith("0") and rng.random() < 0.9:
        return pc[1:]
    return pc


def fmt_date(d: date, allow_iso=True) -> str:
    r = rng.random()
    if allow_iso and r < 0.12:
        return d.isoformat()  # rows that came in through a 2019 bulk import
    if r < 0.25:
        return d.strftime("%d/%m/%y")
    return d.strftime("%d/%m/%Y")


def fmt_amount(value: float) -> str:
    """How the legacy tool prints money: French format, dot for thousands on whole amounts."""
    if value == int(value):
        v = int(value)
        return f"{v:,}".replace(",", ".") if v >= 1000 else str(v)
    whole, cents = f"{value:.2f}".split(".")
    whole = f"{int(whole):,}".replace(",", " ")
    text = f"{whole},{cents}"
    return text + " €" if rng.random() < 0.15 else text


def random_date(start_year: int, end_year: int) -> date:
    start = date(start_year, 1, 1)
    return start + timedelta(days=rng.randint(0, (date(end_year, 12, 31) - start).days))


def pick_city():
    return rng.choices(CITIES, weights=[c[2] for c in CITIES])[0]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    accounts, contacts, contracts = [], [], []
    account_ids = []
    next_id = 1

    def new_account_id():
        nonlocal next_id
        # Gaps in the numbering are accounts deleted from the legacy tool over the years.
        next_id += 1 if rng.random() > 0.04 else rng.randint(2, 4)
        return f"CL{next_id:05d}"

    deleted_ids = []
    household_names = []
    for i in range(470):
        prev = next_id
        acc_id = new_account_id()
        deleted_ids += [f"CL{n:05d}" for n in range(prev + 1, next_id)]
        pc, city, _ = pick_city()
        is_business = i % 5 < 2
        created = random_date(2012, 2025)
        if is_business:
            surname = rng.choice(SURNAMES)
            name = f"{rng.choice(TRADES)} {surname}"
            email = f"contact@{slug(name)}.fr"
            phone = phone_number(["0474", "0472", "0478", "0385", "0437"])
            company_id = siret()
        else:
            if household_names and rng.random() < 0.02:
                name, pc, city = rng.choice(household_names)  # same household entered twice
            else:
                name = f"{rng.choice(SURNAMES)} {rng.choice(FIRST)}"
                household_names.append((name, pc, city))
            first = name.split()[-1]
            email = f"{slug(first)}.{slug(name.split()[0])}@{rng.choice(DOMAINS)}"
            phone = phone_number(["06", "07"])
            company_id = ""
        if rng.random() < 0.03:
            email = rng.choice([email.replace("@", "@@"), email.rsplit(".", 1)[0], "n/a"])
        accounts.append({
            "N° client": acc_id, "Raison sociale": name, "SIRET": company_id,
            "Adresse": f"{rng.randint(1, 180)} {rng.choice(['rue', 'avenue', 'chemin', 'place'])} "
                       f"{rng.choice(['de la République', 'Victor Hugo', 'des Tilleuls', 'du Stade', 'Jean Jaurès', 'des Écoles', 'de la Gare'])}",
            "CP": fmt_postcode(pc), "Ville": city, "Tél": fmt_phone(phone), "Email": email,
            "Date création": fmt_date(created), "Commercial": rng.choice(OWNERS),
            "_business": is_business, "_created": created,
        })
        account_ids.append(acc_id)

    # Duplicate companies: same SIRET, re-created by a different rep years later.
    businesses = [a for a in accounts if a["_business"]]
    for original in rng.sample(businesses, 12):
        dup = dict(original)
        dup["N° client"] = new_account_id()
        dup["Raison sociale"] = rng.choice([original["Raison sociale"].upper(), original["Raison sociale"] + " SARL"])
        dup["Tél"] = rng.choice(["", original["Tél"]])
        dup["Email"] = rng.choice(["", original["Email"]])
        dup["Commercial"] = rng.choice(OWNERS)
        dup["Date création"] = fmt_date(random_date(2020, 2025))
        accounts.append(dup)
        account_ids.append(dup["N° client"])
    dup_ids = [a["N° client"] for a in accounts[-12:]]

    # Accounts with no name: created from a phone call, never completed.
    blank_ids = []
    for _ in range(3):
        acc_id = new_account_id()
        pc, city, _ = pick_city()
        accounts.append({
            "N° client": acc_id, "Raison sociale": "", "SIRET": "", "Adresse": "", "CP": fmt_postcode(pc),
            "Ville": city, "Tél": fmt_phone(phone_number(["06", "07"])), "Email": "",
            "Date création": fmt_date(random_date(2022, 2025)), "Commercial": rng.choice(OWNERS),
            "_business": False, "_created": date(2023, 1, 1),
        })
        account_ids.append(acc_id)
        blank_ids.append(acc_id)

    # ── Contacts ─────────────────────────────────────────────────────────────
    ct = 0

    def add_contact(acc_id, business, surname=None, first=None):
        nonlocal ct
        ct += 1
        surname = surname or rng.choice(SURNAMES)
        first = first or rng.choice(FIRST)
        email = f"{slug(first)}.{slug(surname)}@{rng.choice(DOMAINS)}"
        if rng.random() < 0.03:
            email = rng.choice([email.replace("@", "@@"), email.rsplit(".", 1)[0]])
        contacts.append({
            "N° contact": f"CT{ct:05d}", "N° client": acc_id, "Nom": surname.upper(), "Prénom": first,
            "Fonction": rng.choice(ROLES) if business else "", "Tél portable": fmt_phone(phone_number(["06", "07"])),
            "E-mail": email if rng.random() > 0.08 else "",
        })

    for a in accounts:
        if a["_business"]:
            for _ in range(rng.choice([1, 1, 2, 2, 3])):
                add_contact(a["N° client"], True)
        else:
            parts = a["Raison sociale"].split()
            add_contact(a["N° client"], False, *(parts if len(parts) == 2 else (None, None)))
    for _ in range(15):
        add_contact(rng.choice(deleted_ids), rng.random() < 0.5)

    # ── Contracts ────────────────────────────────────────────────────────────
    true_active_total = 0.0
    n = 0
    invalid_dates = iter(["31/02/2023", "29/02/2023", "00/01/2022"])
    invalid_rows = set(rng.sample(range(300), 3))

    def add_contract(acc_id, business):
        nonlocal n, true_active_total
        n += 1
        start = random_date(2018, 2026)
        if business:
            kind = rng.choice(["Contrat Sérénité+", "Maintenance PAC", "Maintenance multi-sites"])
            value = float(rng.choice(range(850, 6800, 50))) if rng.random() < 0.12 else round(rng.uniform(850, 6800), 2)
        else:
            kind = rng.choice(["Entretien annuel chaudière", "Contrat Sérénité", "Contrat Sérénité"])
            value = round(rng.uniform(139, 590), 2) if rng.random() < 0.8 else float(rng.choice(range(150, 600, 10)))
        status = rng.choices(["Actif", "Suspendu", "Résilié"], weights=[85, 5, 10])[0]
        start_txt = next(invalid_dates) if n in invalid_rows else fmt_date(start, allow_iso=False)
        contracts.append({
            "Réf contrat": f"CTR-{start.year}-{n:04d}", "N° client": acc_id, "Formule": kind,
            "Montant annuel HT": fmt_amount(value), "Date début": start_txt,
            "Date fin": fmt_date(start + timedelta(days=364), allow_iso=False), "Statut": status,
        })
        if status != "Résilié":
            true_active_total += value

    for a in accounts:
        if rng.random() < 0.88 or a["N° client"] in dup_ids or a["N° client"] in blank_ids:
            add_contract(a["N° client"], a["_business"])
    for _ in range(4):
        add_contract(rng.choice(deleted_ids), True)
    rng.shuffle(contracts)

    # ── Write, the way the legacy tool exports ───────────────────────────────
    def write(name, rows):
        rows = [{k: v for k, v in r.items() if not k.startswith("_")} for r in rows]
        with (OUT / name).open("w", encoding="cp1252", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()), delimiter=";")
            w.writeheader()
            w.writerows(rows)

    write("clients.csv", accounts)
    write("contacts.csv", contacts)
    write("contrats.csv", contracts)
    (OUT / "CONTROL_TOTALS.txt").write_text(
        "Provided by Maison Verte Services (ops lead), exported from the legacy tool's\n"
        "'CA contrats actifs' report on 18/09/2026, the same day as the CSV exports.\n\n"
        f"Active + suspended contracts, total annual value excl. VAT: {true_active_total:.2f} EUR\n",
        encoding="utf-8",
    )
    print(f"accounts={len(accounts)} contacts={len(contacts)} contracts={len(contracts)} "
          f"control_total={true_active_total:.2f}")


if __name__ == "__main__":
    main()
