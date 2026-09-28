# Source data profile

⚠️ = more than one format in the same column, worth a question to the customer.

## clients.csv

- Rows: **485**
- Encoding detected: `cp1252`  ⚠️ not UTF-8, accents will break if read naively
- Delimiter: `;`

| Column | Filled | Distinct | Most common shapes | Example |
|---|---:|---:|---|---|
| N° client | 100% | 485 | `a99999` ×485 | CL00002 |
| Raison sociale | 99% | 428 | `a a` ×424, `a a a` ×20, `a-a a` ×20, `a a a a` ×15 | Garage David |
| SIRET | 41% | 188 | `99999999999999` ×200 | 01338908386371 |
| Adresse | 99% | 457 | `999 a a a` ×168, `99 a a a` ×168, `999 a a a a` ×73, `99 a a a a` ×52, `9 a a a` ×14 | 2 avenue des Écoles |
| CP | 100% | 16 | `99999` ×340, `9999` ×145 ⚠️ | 1000 |
| Ville | 100% | 11 | `a` ×342, `a-a-a` ×143 | Bourg-en-Bresse |
| Tél | 93% | 446 | `99 99 99 99 99` ×206, `9999999999` ×97, `99.99.99.99.99` ×74, `+99 9 99 99 99 99` ×31, `99999999999` ×28, `99 99 99 99` ×15 ⚠️ | 04 72 18 19 60 |
| Email | 98% | 440 | `a.a@a.a` ×280, `a@a-a.a` ×138, `a@a-a-a.a` ×36, `a@a-a-a-a.a` ×14 | contact@garage-david.fr |
| Date création | 100% | 468 | `99/99/9999` ×370, `99/99/99` ×59, `9999-99-99` ×56 ⚠️ | 03/03/18 |
| Commercial | 100% | 5 | `a a` ×485 | Sophie Laurent |

## contacts.csv

- Rows: **670**
- Encoding detected: `cp1252`  ⚠️ not UTF-8, accents will break if read naively
- Delimiter: `;`

| Column | Filled | Distinct | Most common shapes | Example |
|---|---:|---:|---|---|
| N° contact | 100% | 670 | `a99999` ×670 | CT00001 |
| N° client | 100% | 497 | `a99999` ×670 | CL00002 |
| Nom | 100% | 54 | `a` ×670 | MATHIEU |
| Prénom | 100% | 28 | `a` ×670 | Noémie |
| Fonction | 56% | 7 | `a` ×207, `a a a` ×115, `a a` ×55 | Gérant |
| Tél portable | 93% | 622 | `99 99 99 99 99` ×298, `9999999999` ×115, `99.99.99.99.99` ×103, `+99 9 99 99 99 99` ×59, `99999999999` ×29, `99 99 99 99` ×18 ⚠️ | 06.52.98.67.07 |
| E-mail | 91% | 592 | `a.a@a.a` ×587, `a.a@a` ×12, `a.a@@a.a` ×8 | noemie.mathieu@laposte.net |

## contrats.csv

- Rows: **436**
- Encoding detected: `cp1252`  ⚠️ not UTF-8, accents will break if read naively
- Delimiter: `;`

| Column | Filled | Distinct | Most common shapes | Example |
|---|---:|---:|---|---|
| Réf contrat | 100% | 436 | `a-9999-9999` ×436 | CTR-2025-0279 |
| N° client | 100% | 435 | `a99999` ×436 | CL00334 |
| Formule | 100% | 5 | `a a` ×233, `a a a` ×90, `a a-a` ×61, `a a+` ×52 | Maintenance multi-sites |
| Montant annuel HT | 100% | 415 | `999,99` ×170, `9 999,99` ×140, `999` ×52, `999,99 €` ×30, `9.999` ×25, `9 999,99 €` ×19 ⚠️ | 2 178,47 |
| Date début | 100% | 416 | `99/99/9999` ×322, `99/99/99` ×114 ⚠️ | 24/07/2025 |
| Date fin | 100% | 414 | `99/99/9999` ×311, `99/99/99` ×125 ⚠️ | 23/07/2026 |
| Statut | 100% | 3 | `a` ×436 | Actif |
