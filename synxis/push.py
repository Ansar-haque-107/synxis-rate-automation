import json
import time
import pandas as pd

from . import config
from .client import build_session, fetch_range, calendar_id_for_date


def values_match(live_val, exported_val) -> bool:
    if live_val is None or exported_val is None:
        return False
    try:
        return float(live_val) == float(exported_val)
    except (TypeError, ValueError):
        return str(live_val).strip() == str(exported_val).strip()


def run():
    print(f"Reading {config.EXCEL_PATH} ...")
    df = pd.read_excel(config.EXCEL_PATH, sheet_name=config.SHEET_NAME)
    df = df.dropna(subset=["Date", "Room Type", "Rate Code", "New Rate"])
    if df.empty:
        print("No rows with a New Rate filled in. Nothing to do.")
        return
    print(f"Found {len(df)} row(s) with a New Rate.")

    session = build_session()
    dates = pd.to_datetime(df["Date"]).dt.date
    start_d, end_d = dates.min(), dates.max()

    print("Fetching live rates from Synxis to cross-check before pushing ...")
    live_rows, room_map, rate_map = fetch_range(session, start_d, end_d)
    if not room_map or not rate_map:
        print("Could not discover rooms/rates — session likely expired, recapture the cookie/token.")
        return
    live = {(r["rate_uid"], r["room_uid"], r["calendar_id"]): r["value"] for r in live_rows}

    ok_rows, skipped = [], []
    for _, row in df.iterrows():
        cid = calendar_id_for_date(pd.to_datetime(row["Date"]).date())
        room_uid = room_map.get(str(row["Room Type"]).strip())
        rate_uid = rate_map.get(str(row["Rate Code"]).strip().upper())

        if not room_uid or not rate_uid:
            skipped.append(f"{row['Date']} | {row['Room Type']} | {row['Rate Code']}: not found in Synxis.")
            continue

        live_val = live.get((rate_uid, room_uid, cid))
        if not values_match(live_val, row.get("Current Rate")) and not config.PUSH_ON_MISMATCH:
            skipped.append(
                f"{row['Date']} | {row['Room Type']} | {row['Rate Code']}: "
                f"exported {row.get('Current Rate')}, live shows {live_val} — grid changed since export."
            )
            continue

        ok_rows.append({
            "rate_uid": rate_uid, "room_uid": room_uid, "cid": cid,
            "new_rate": row["New Rate"],
            "label": f"{row['Date']} | {row['Room Type']} | {row['Rate Code']}",
        })

    for s in skipped:
        print("  !", s)
    if not ok_rows:
        print("Nothing left to push after cross-checks.")
        return
    print(f"Cross-check passed for {len(ok_rows)} row(s)" + (f", {len(skipped)} skipped." if skipped else "."))

    payload = _build_payload(ok_rows)

    if config.DRY_RUN:
        print("\n=== DRY RUN — nothing was sent ===")
        print(json.dumps(payload, indent=2))
        return

    print("\nSending Save request to Synxis ...")
    resp = session.post(config.SAVE_URL, data=json.dumps(payload))
    result = resp.json()
    print(f"Status: {resp.status_code} — {result.get('Text') or result.get('Title')}")
    if result.get("Title") != "Success":
        print(json.dumps(result, indent=2))
        return

    if config.VERIFY_AFTER_SAVE:
        _verify(session, ok_rows, start_d, end_d)


def _build_payload(ok_rows: list[dict]) -> dict:
    by_rate: dict[str, dict[str, list[dict]]] = {}
    for r in ok_rows:
        by_rate.setdefault(r["rate_uid"], {}).setdefault(r["room_uid"], []).append(r)

    rates_payload, selected_rate_uids = [], []
    for rate_uid, rooms in by_rate.items():
        dpps = [
            {"Values": [{"Value": str(int(float(i["new_rate"]))), "CalendarId": i["cid"]} for i in items],
             "Room": {"UniqueID": room_uid}}
            for room_uid, items in rooms.items()
        ]
        rates_payload.append({
            "DailyProductPrices": dpps, "UniqueID": rate_uid,
            "IsRateValidForSplitSeason": True, "IsMirroredRate": False,
        })
        selected_rate_uids.append(rate_uid)

    return {
        "RatesModel": {"Rates": rates_payload},
        "ChannelManagerUserPreferenceModel": {
            "ViewRateBy": "Type", "ViewRoomBy": "Type",
            "ChannelManagerRatesFilterModel": {"SelectedRates": selected_rate_uids},
        },
    }


def _verify(session, ok_rows: list[dict], start_d, end_d):
    time.sleep(config.REQUEST_DELAY_SECONDS)
    print("\nRe-fetching rates to verify the save ...")
    live_rows, _, _ = fetch_range(session, start_d, end_d)
    live = {(r["rate_uid"], r["room_uid"], r["calendar_id"]): r["value"] for r in live_rows}

    confirmed, bad = 0, []
    for r in ok_rows:
        expected = str(int(float(r["new_rate"])))
        actual = live.get((r["rate_uid"], r["room_uid"], r["cid"]))
        if values_match(actual, expected):
            confirmed += 1
        else:
            bad.append(f"{r['label']}: expected {expected}, Synxis now shows {actual}")

    print(f"Verification: {confirmed}/{len(ok_rows)} value(s) confirmed in Synxis.")
    for b in bad[:20]:
        print("  !", b)
    if not bad:
        print("Everything you sent is confirmed live.")
