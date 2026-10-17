# Runbook: <nosaukums, piemēram, "Datubāze zudusi vai bojāta">

> Ielīmējiet šeit savas grupas runbook no plāna (Word). Aizpildiet katru sadaļu. Claude Code šo failu izlasa un tam seko. Ja kāda sadaļa paliek tukša, Claude Code apstāsies un jautās.

| | |
|---|---|
| Grupa | |
| Versija un datums | |
| Runbook īpašnieks | |

## 1. Mērķis un tvērums

- Kuru servisu atjauno:
- Ārpus tvēruma:
- Mērķi: RTO … h, RPO … h

## 2. Aktivizēšanas kritērijs

Kādas pazīmes nozīmē, ka šo runbook sāk lietot?

-

## 3. Katastrofas izsludināšana

- Kas izsludina (amats):
- Aizvietotājs, ja viņš nav sasniedzams:
- Kā paziņo komandai:

## 4. Lomas

| Loma | Kas (amats) | Aizvietotājs | Kā sazināties |
|---|---|---|---|
| Incidenta vadītājs | | | |
| Operators (izpilda soļus) | | | |
| Navigators (seko runbook) | | | |
| Pulksteņa turētājs (kartītes) | | | |
| Žurnāls un komunikācija | | | |
| SIA "Ezerdati" kontaktpersona | | | |

## 5. Priekšnosacījumi

- Kādas piekļuves vajag un kur tās ir:
- Kur ir rezerves kopijas un kā pārbauda to kontrolsummas:
- Kur ir šī runbook kopija, ja failu serveris nav pieejams:

## 6. Lēmumu punkti

| Nr. | Lēmums | Kas lemj | Kritērijs |
|---|---|---|---|
| L1 | Izsludināt katastrofu | | |
| L2 | Pārslēgties uz rezerves serveri vai atjaunot no kopijas | | |
| L3 | Kuru rezerves kopiju izmantot | | |
| L4 | Iesaistīt SIA "Ezerdati" | | |
| L5 | Informēt iedzīvotājus | | |

## 7. Soļi

| Nr. | Solis | Komanda vai darbība | Kas | Paredzamais ilgums | Pārbaude pēc soļa |
|---|---|---|---|---|---|
| 1 | Pārbaudīt stāvokli | `make status` | Operators | | |
| 2 | | | | | |
| 3 | | | | | |

## 8. Pārbaude: vai serviss ir atjaunots?

- Kritēriji (piemēram, `make verify`: datu zuduma logs ≤ RPO, pielikumi vietā, triāža ≥ 18/20):
- Kas apstiprina, ka serviss ir atjaunots:

## 9. Komunikācijas kontrolpunkti

| Kad | Kam | Ko paziņo | Kanāls | Kas paziņo |
|---|---|---|---|---|
| Pēc izsludināšanas | Pašvaldības vadībai | | | |
| | Iedzīvotājiem | | | |
| | Darbiniekiem (Kanceleja, Sociālais dienests) | | | |
| Ja incidents ir nozīmīgs | NKC, CERT.LV | | | |

## 10. Atgriešanās (failback)

Kā atgriežas uz galveno serveri, kā atjauno rezerves serveri un kopiju grafiku:

-

## 11. Žurnāls

| Simulētais laiks | Notikums vai lēmums | Kas izlēma | Kartīte (+ ilgums) | Piezīmes |
|---|---|---|---|---|
| pirmdiena 08:40 | Katastrofa sākas | | | |
| | | | | |
