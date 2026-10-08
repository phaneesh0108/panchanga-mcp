"""MCP server exposing the Panchanga API to AI assistants (Claude, Gemini, etc.)."""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from mcp.server.fastmcp import FastMCP

API_BASE = os.environ.get(
    "PANCHANGA_API_BASE", "https://panchanga-backend-production.up.railway.app"
).rstrip("/")
TIMEOUT = float(os.environ.get("PANCHANGA_TIMEOUT", "20"))

# Defaults: Bengaluru, Kannada
DEFAULT_LAT = float(os.environ.get("PANCHANGA_DEFAULT_LAT", "12.9716"))
DEFAULT_LON = float(os.environ.get("PANCHANGA_DEFAULT_LON", "77.5946"))
DEFAULT_TZ = os.environ.get("PANCHANGA_DEFAULT_TZ", "Asia/Kolkata")
DEFAULT_LANG = os.environ.get("PANCHANGA_DEFAULT_LANG", "kannada")

mcp = FastMCP(
    "panchanga",
    instructions=(
        "Provides the daily Hindu Panchanga (tithi, nakshatra, yoga, karana, vara, "
        "masa, samvatsara, sunrise/sunset, muhurtas such as Rahu Kala) for a "
        "location. Use get_panchanga for today's or any day's details, and "
        "get_muhurtas when the user only asks about auspicious/inauspicious times. "
        "If the user gives a city name, convert it to latitude/longitude yourself."
    ),
)


async def _fetch(lat: float, lon: float, tz: str, lang: str, date: str | None) -> dict[str, Any]:
    try:
        ZoneInfo(tz)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"Unknown IANA timezone: {tz!r} (e.g. 'Asia/Kolkata')") from exc
    if not -90 <= lat <= 90 or not -180 <= lon <= 180:
        raise ValueError("lat must be within -90..90 and lon within -180..180")

    params: dict[str, Any] = {"lat": lat, "lon": lon, "tz": tz, "lang": lang}
    if date:
        datetime.strptime(date, "%Y-%m-%d")  # validate format
        params["date"] = date

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.get(f"{API_BASE}/panchanga", params=params)
        resp.raise_for_status()
        return resp.json()


def _hhmm(iso: str | None) -> str | None:
    if not iso:
        return None
    return datetime.fromisoformat(iso).strftime("%H:%M")


def _segments(item: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {"name": s.get("name", ""), "from": s.get("start", ""), "until": s.get("end", "")}
        for s in item.get("segments", [])
    ]


def _summarise(data: dict[str, Any]) -> dict[str, Any]:
    p = data.get("panchanga", {})
    req = data.get("requested", {})

    def val(key: str) -> str | None:
        return p.get(key, {}).get("value")

    return {
        "date": req.get("date"),
        "location": {"lat": req.get("lat"), "lon": req.get("lon"), "tz": req.get("tz")},
        "language": req.get("lang"),
        "sunrise": _hhmm(data.get("sunrise_iso")),
        "sunset": _hhmm(data.get("sunset_iso")),
        "vara": val("vara"),
        "tithi": {"current": val("tithi"), "timeline": _segments(p.get("tithi", {}))},
        "nakshatra": {"current": val("nakshatra"), "timeline": _segments(p.get("nakshatra", {}))},
        "yoga": {"current": val("yoga"), "timeline": _segments(p.get("yoga", {}))},
        "karana": {"current": val("karana"), "timeline": _segments(p.get("karana", {}))},
        "paksha": val("paksha"),
        "masa": val("masa"),
        "solar_masa": val("solar_masa"),
        "ritu": val("ritu"),
        "ayana": val("ayana"),
        "samvatsara": val("samvatsara"),
        "dina_status": val("dina_status"),
        "dinavishesha": val("dinavishesha"),
        "special_event": p.get("special_event"),
        "moon": p.get("moon_data"),
        "lagna_bhava": val("bhava"),
        "muhurtas": _muhurtas(data),
        "note": "Times are local to the requested timezone; 'Next Sunrise' means the entry runs until the next day's sunrise.",
    }


_AUSPICIOUS = {"abhijit", "amrita", "brahma_muhurta", "vijaya", "godhuli"}
_INAUSPICIOUS = {"rahu", "yamaganda", "gulika", "durmuhurta", "varjyam"}


def _muhurtas(data: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {"auspicious": [], "inauspicious": []}
    for key, m in data.get("muhurtas", {}).items():
        bucket = (
            "auspicious" if key in _AUSPICIOUS else "inauspicious" if key in _INAUSPICIOUS else None
        )
        if bucket is None:
            continue
        out[bucket].append(
            {
                "key": key,
                "name": m.get("label", key),
                "start": _hhmm(m.get("start_iso")),
                "end": _hhmm(m.get("end_iso")),
            }
        )
    return out


@mcp.tool()
async def get_panchanga(
    date: str | None = None,
    lat: float = DEFAULT_LAT,
    lon: float = DEFAULT_LON,
    tz: str = DEFAULT_TZ,
    lang: str = DEFAULT_LANG,
    raw: bool = False,
) -> dict[str, Any]:
    """Get the daily Panchanga for a date and location.

    Args:
        date: Date as YYYY-MM-DD. Omit for today.
        lat: Latitude in decimal degrees (default Bengaluru, 12.9716).
        lon: Longitude in decimal degrees (default Bengaluru, 77.5946).
        tz: IANA timezone name, e.g. 'Asia/Kolkata'.
        lang: Output language, e.g. 'kannada' or 'english'.
        raw: Return the API's full JSON instead of the condensed summary.
    """
    data = await _fetch(lat, lon, tz, lang, date)
    return data if raw else _summarise(data)


@mcp.tool()
async def get_muhurtas(
    date: str | None = None,
    lat: float = DEFAULT_LAT,
    lon: float = DEFAULT_LON,
    tz: str = DEFAULT_TZ,
    lang: str = DEFAULT_LANG,
) -> dict[str, Any]:
    """Get only the auspicious and inauspicious time windows (Abhijit, Brahma
    Muhurta, Rahu Kala, Yamaganda, Gulika, Durmuhurta, Varjyam, etc.) for a day.

    Args:
        date: Date as YYYY-MM-DD. Omit for today.
        lat: Latitude in decimal degrees.
        lon: Longitude in decimal degrees.
        tz: IANA timezone name.
        lang: Output language, e.g. 'kannada' or 'english'.
    """
    data = await _fetch(lat, lon, tz, lang, date)
    return {
        "date": data.get("requested", {}).get("date"),
        "sunrise": _hhmm(data.get("sunrise_iso")),
        "sunset": _hhmm(data.get("sunset_iso")),
        **_muhurtas(data),
    }


@mcp.tool()
async def get_panchanga_text(
    date: str | None = None,
    lat: float = DEFAULT_LAT,
    lon: float = DEFAULT_LON,
    tz: str = DEFAULT_TZ,
    lang: str = DEFAULT_LANG,
) -> str:
    """Get a short, human-readable daily Panchanga message (good for chat replies
    or morning greetings). Same arguments as get_panchanga."""
    s = _summarise(await _fetch(lat, lon, tz, lang, date))

    def line(label: str, item: dict[str, Any]) -> str:
        segs = ", ".join(f"{x['name']} (till {x['until']})" for x in item["timeline"])
        return f"{label}: {segs or item['current'] or 'n/a'}"

    rahu = next((m for m in s["muhurtas"]["inauspicious"] if m["key"] == "rahu"), None)
    abhijit = next((m for m in s["muhurtas"]["auspicious"] if m["key"] == "abhijit"), None)
    parts = [
        f"Panchanga for {s['date']} ({s['vara']})",
        f"Samvatsara {s['samvatsara']}, {s['ayana']}, {s['ritu']} ritu, {s['masa']} masa, {s['paksha']} paksha",
        line("Tithi", s["tithi"]),
        line("Nakshatra", s["nakshatra"]),
        line("Yoga", s["yoga"]),
        line("Karana", s["karana"]),
        f"Sunrise {s['sunrise']} / Sunset {s['sunset']}",
    ]
    if abhijit:
        parts.append(f"{abhijit['name']}: {abhijit['start']}-{abhijit['end']}")
    if rahu:
        parts.append(f"{rahu['name']}: {rahu['start']}-{rahu['end']}")
    if s.get("special_event"):
        parts.append(f"Special: {s['special_event']}")
    return "\n".join(parts)


def main() -> None:
    """Entry point. PANCHANGA_MCP_TRANSPORT = stdio (default) | streamable-http."""
    transport = os.environ.get("PANCHANGA_MCP_TRANSPORT", "stdio")
    if transport == "stdio":
        mcp.run(transport="stdio")
    else:
        mcp.settings.host = os.environ.get("HOST", "0.0.0.0")
        mcp.settings.port = int(os.environ.get("PORT", "8000"))
        mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
