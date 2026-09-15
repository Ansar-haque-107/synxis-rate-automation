import json
import sys
import time
import datetime
import requests

from . import config


def calendar_id_for_date(d: datetime.date) -> int:
    return config.CALENDAR_ANCHOR_ID + (d - config.CALENDAR_ANCHOR_DATE).days


def date_for_calendar_id(cid: int) -> datetime.date:
    return config.CALENDAR_ANCHOR_DATE + datetime.timedelta(cid - config.CALENDAR_ANCHOR_ID)


def build_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "content-type": "application/json;charset=UTF-8",
        "accept": "*/*",
        "origin": config.BASE_URL,
        "referer": config.REFERER,
        "x-requested-with": "XMLHttpRequest",
        "x-requestverificationtoken": config.CSRF_TOKEN,
        "cookie": config.COOKIE,
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36",
    })
    return s


def _valid_templates() -> list[str]:
    return [t.strip() for t in config.GETRATES_PAYLOAD_TEMPLATES if t.strip().startswith("{")]


def get_rates_window(session: requests.Session, start_calendar_id: int, template: str = "") -> dict:
    if template:
        payload = json.loads(template)
        payload.update(StartCalendarId=start_calendar_id, PageIndex=1,
                        GetAllRemainingPages=False, ReloadHotel=False)
    else:
        payload = {
            "StartCalendarId": start_calendar_id, "ReloadHotel": False,
            "SelectedChannels": ["0"], "ViewRateBy": "Type", "SelectedRooms": [],
            "SelectedRateCategories": [], "SelectedRates": [], "SelectedRestrictions": [],
            "SelectedCategoryRestrictions": [], "SelectedRateTypes": ["0", "1", "3"],
            "DisplayRatesByRestriction": False, "AdultCount": "1", "ChildCount": "0",
            "ChildAges": "", "PageIndex": 1, "GetAllRemainingPages": False,
        }
    resp = session.post(config.GETRATES_URL, data=json.dumps(payload))
    if resp.status_code != 200:
        print(f"GetRates failed with HTTP {resp.status_code}:\n{resp.text[:1000]}")
        sys.exit(1)
    return resp.json()


def extract_values(data: dict):
    rows, room_name_to_id, rate_code_to_id = [], {}, {}
    for rate in data.get("Rates", {}).get("Rates") or []:
        code = (rate.get("Code") or "").strip()
        rate_uid = rate.get("UniqueID")
        if code and rate_uid:
            rate_code_to_id[code.upper()] = rate_uid
        for dpp in rate.get("DailyProductPrices", []):
            room = dpp.get("Room") or {}
            room_name, room_uid = (room.get("Name") or "").strip(), room.get("UniqueID")
            if room_name and room_uid:
                room_name_to_id[room_name] = room_uid
            for v in dpp.get("Values", []):
                value = v.get("Value")
                if value is None or str(value).strip() == "":
                    value = v.get("CalculatedPrice")  # Synxis sometimes omits "Value"
                rows.append({
                    "rate_code": code, "rate_uid": rate_uid,
                    "room_name": room_name, "room_uid": room_uid,
                    "calendar_id": v.get("CalendarId"), "value": value,
                })
    return rows, room_name_to_id, rate_code_to_id


def fetch_range(session: requests.Session, start_date: datetime.date, end_date: datetime.date):
    """Pages through GetRates windows until [start_date, end_date] is fully covered."""
    want_min, want_max = calendar_id_for_date(start_date), calendar_id_for_date(end_date)
    all_rows, room_map, rate_map = {}, {}, {}
    templates = _valid_templates() or [""]

    cursor = want_min + config.WINDOW_BACK
    while True:
        max_cid_seen = None
        for i, template in enumerate(templates, start=1):
            label = f" (rate plan {i}/{len(templates)})" if len(templates) > 1 else ""
            print(f"  Fetching window around {date_for_calendar_id(cursor)}{label} ...")
            data = get_rates_window(session, cursor, template)
            rows, rm, cm = extract_values(data)
            room_map.update(rm)
            rate_map.update(cm)
            for r in rows:
                cid = r["calendar_id"]
                if cid is None:
                    continue
                max_cid_seen = cid if max_cid_seen is None else max(max_cid_seen, cid)
                if want_min <= cid <= want_max:
                    all_rows[(r["rate_uid"], r["room_uid"], cid)] = r
            if len(templates) > 1:
                time.sleep(config.REQUEST_DELAY_SECONDS)

        if max_cid_seen is None:
            print(f"  No data returned at cursor {cursor} — stopping.")
            break
        if max_cid_seen >= want_max:
            break
        cursor = max_cid_seen + 1 + config.WINDOW_BACK
        time.sleep(config.REQUEST_DELAY_SECONDS)

    return list(all_rows.values()), room_map, rate_map
