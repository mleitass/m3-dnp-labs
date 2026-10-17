# Ezermalas e-pakalpojums "Iesniegumi" · atjaunošanas mācības (m3-dnp-lab)

Mācību vide M3 modulim "Sistēmu nepārtrauktības pārvaldība". Ezermalas novada pašvaldības e-pakalpojums "Iesniegumi" pieņem iedzīvotāju iesniegumus, un MI triāža tos sadala pa nodaļām. Jūsu grupa saņem savu katastrofu un atjauno servisu pēc sava runbook.

> **Visi dati ir sintētiski un izdomāti.** Ezermalas novada pašvaldība, SIA "Ezerdati", iedzīvotāji un iesniegumi ir izdomāti. Šeit neievadiet reālus datus. MI pakalpojums ir imitācija: tīkla izsaukumu un īstu API atslēgu nav.

## Kā sākt

1. Šī ir veidne (template). Spiediet **Use this template → Create a new repository**, nosaukums **`m3-dnp-lab`**.
2. Savā kopijā: **Code → Codespaces → Create codespace on main**. Pirmā atvēršana ilgst 2–3 minūtes.
3. Cilnē **Claude Code** pieslēdzieties ar kursa kontu.
4. Ielīmējiet savas grupas runbook failā `RUNBOOK.md`.

## Trīs galvenās komandas

| Komanda | Kad |
|---|---|
| `make status` | Jebkurā brīdī: ko rāda uzraudzība |
| `make katastrofa GROUP=N` | Vienreiz, kad pasniedzējs to saka. N ir jūsu grupas numurs (1–4) |
| `make verify` | Pēc atjaunošanas: cik datu zaudēts (izmērītais RPO), pielikumi, triāža |

Pārējās komandas izmantojiet tā, kā rakstīts jūsu runbook:

| Komanda | Ko dara |
|---|---|
| `make backup-list` | Rezerves kopijas: laiks, vecums, izmērs, kontrolsumma, žurnāls |
| `make restore BACKUP=<ID>` | Atjauno galveno serveri no kopijas (ID vai `D-1`, `D-7`, `D-30`, `D-365`) |
| `make failover` | Pārslēdz servisu uz rezerves serveri |
| `make replicate` | Sinhronizē rezerves serveri ar galveno |
| `make triage MODE=manual` | Triāža manuāli: visi jaunie iesniegumi nonāk Kancelejā (`MODE=auto`: atpakaļ uz MI) |
| `make reset` | Sākt no jauna: stāvoklis pirms katastrofas |
| `make help` | Visas komandas |

`make verify` mēra datu zudumu, nevis laiku. Atjaunošanas laiku (RTO) jūs simulējat ar ilguma un lēmumu kartītēm.

## Lomas

- **Operatoru pāris** (pie tastatūras un navigators) strādā Codespace ar Claude Code.
- **Pulksteņa turētājs** izvēlas kartītes un skaita simulēto laiku.
- **Žurnāla rakstītājs** pieraksta lēmumus un sagatavo paziņojumu iedzīvotājiem.

## Kur kas atrodas

| Mape vai fails | Saturs |
|---|---|
| `RUNBOOK.md` | Jūsu grupas runbook |
| `CLAUDE.md` | Noteikumi Claude Code |
| `sistema/` | Mācību sistēmas stāvoklis: serveri, rezerves kopijas (izveido `make reset`) |
| `app/`, `ui/` | E-pakalpojuma kods un lapas |
| `drill/`, `mock_llm/` | Simulācija. Tas nav atjaunošanas avots |

## Portāls (pēc izvēles)

`make run` palaiž portālu. Cilnē **Ports** pie porta 8000 spiediet globusa ikonu un adreses beigās pievienojiet `/ui` (iedzīvotāja forma) vai `/ui/darbinieks.html` (darbinieku saraksts). Katastrofas laikā portāls rāda kļūdu, pēc atjaunošanas tas darbojas. Portālu aptur ar `Ctrl+C`.
