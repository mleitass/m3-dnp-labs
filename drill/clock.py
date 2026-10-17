"""Simulētais laiks un datumu, ilgumu un skaitļu formāts latviešu valodā.

Simulācijas pulkstenis ir apturēts katastrofas brīdī. Īstais laiks netiek
mērīts un netiek rādīts (atjaunošanas laiku grupa simulē ar kartītēm).
"""

from datetime import datetime, timedelta, timezone

TZ = timezone(timedelta(hours=3))  # Rīga, vasaras laiks (līdz 25.10.2026)
NOW = datetime(2026, 10, 19, 8, 40, tzinfo=TZ)  # pirmdiena 08:40, katastrofas brīdis

WEEKDAYS = (
    "pirmdiena",
    "otrdiena",
    "trešdiena",
    "ceturtdiena",
    "piektdiena",
    "sestdiena",
    "svētdiena",
)


def parse(value: str) -> datetime:
    return datetime.fromisoformat(value)


def fmt_dt(value: datetime | str) -> str:
    """Piemērs: 'svētdiena 18.10.2026 02:00'."""
    if isinstance(value, str):
        value = parse(value)
    value = value.astimezone(TZ)
    return f"{WEEKDAYS[value.weekday()]} {value:%d.%m.%Y %H:%M}"


def fmt_duration(delta: timedelta) -> str:
    """Piemēri: '0 min', '10 min', '30 h 40 min', '174 h 40 min (7 d 6 h 40 min)'."""
    minutes = max(0, int(delta.total_seconds() // 60))
    hours, mins = divmod(minutes, 60)
    if hours == 0:
        return f"{mins} min"
    text = f"{hours} h {mins} min"
    if hours >= 48:
        days, rest = divmod(hours, 24)
        text += f" ({days} d {rest} h {mins} min)"
    return text


def fmt_int(number: int) -> str:
    """Tūkstošus atdala ar atstarpi: 2 425."""
    return f"{number:,}".replace(",", " ")


def day_offset(value: datetime) -> str:
    """Kopijas vecums dienās attiecībā pret katastrofas dienu: 'D-1', 'D-7'."""
    days = (NOW.date() - value.astimezone(TZ).date()).days
    return f"D-{days}"
