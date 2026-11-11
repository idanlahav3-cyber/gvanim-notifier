import json, os, re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import requests
from bs4 import BeautifulSoup

URL = "https://gvanim.shahaf.site/?cls=17&tab=changes"  # ט6
PHONE = os.environ.get("WA_PHONE") or None       # אופציונלי: וואטסאפ דרך CallMeBot
APIKEY = os.environ.get("CALLMEBOT_KEY") or None
TOPIC = os.environ.get("NTFY_TOPIC") or None     # אופציונלי: התראה לאייפון דרך ntfy
MODE = os.environ.get("MODE", "change")  # change | daily | test | simulate | now
STATE = "state/seen.json"
TZ = ZoneInfo("Asia/Jerusalem")
DATE_RE = re.compile(r"^\d{2}\.\d{2}\.\d{4},")


def fetch_changes():
    html = requests.get(URL, timeout=30).text
    text = BeautifulSoup(html, "html.parser").get_text("\n")
    return [re.sub(r"\s+", " ", l).strip() for l in text.splitlines()
            if DATE_RE.match(l.strip())]


def pretty(item):
    parts = item.split(", ", 2)
    if len(parts) < 3:
        return f"📌 {item}"
    date, lesson, rest = parts
    return f"📅 {date}  |  🕐 {lesson}\n📝 {rest}"


def send_whatsapp(text):
    """שולח בכל הערוצים שהוגדרו (ntfy ו/או CallMeBot)."""
    sent = False
    if TOPIC:
        r = requests.post("https://ntfy.sh/", json={
            "topic": TOPIC, "message": text.replace("*", ""), "priority": 4}, timeout=30)
        r.raise_for_status()
        sent = True
    if PHONE and APIKEY:
        try:
            r = requests.get("https://api.callmebot.com/whatsapp.php", params={
                "phone": PHONE, "text": text, "apikey": APIKEY}, timeout=60)
            r.raise_for_status()
            sent = True
        except Exception as e:
            print("CallMeBot failed:", e)
    if not sent:
        raise SystemExit("לא הוגדר ערוץ שליחה תקין (NTFY_TOPIC או WA_PHONE+CALLMEBOT_KEY)")


def main():
    now = datetime.now(TZ)
    changes = fetch_changes()

    if MODE == "test":
        send_whatsapp("✅ בדיקה: ההתראות של חילופי ט6 עובדות!")
        return

    if MODE == "simulate":
        fake = f"{now.strftime('%d.%m.%Y')}, שיעור 1, מורה לדוגמה, מילוי מקום בבדיקה, חדר: חדר בדיקה"
        send_whatsapp(f"🚨 *שינוי חדש בט6!* (הדמיה)\n\n{pretty(fake)}")
        return

    if MODE == "now":  # סיכום "מחר" מיידי, בלי תלות ביום/שעה
        tomorrow = (now + timedelta(days=1)).strftime("%d.%m.%Y")
        items = [c for c in changes if c.startswith(tomorrow)]
        if items:
            send_whatsapp("🔔 *חילופים למחר – ט6*\n\n" + "\n\n".join(pretty(i) for i in items))
        else:
            send_whatsapp(f"✅ *אין חילופים למחר* ({tomorrow}) – ט6")
        return

    if MODE == "daily":
        # שבת–רביעי בערב (Mon=0 ... Sat=5, Sun=6), בשעה 20 בישראל
        if now.weekday() not in (5, 6, 0, 1, 2) or now.hour != 20:
            return
        tomorrow = (now + timedelta(days=1)).strftime("%d.%m.%Y")
        items = [c for c in changes if c.startswith(tomorrow)]
        if items:
            body = "\n\n".join(pretty(i) for i in items)
            send_whatsapp(f"🔔 *חילופים למחר – ט6*\n\n{body}")
        else:
            send_whatsapp(f"✅ *אין חילופים למחר* ({tomorrow}) – ט6")
        return

    os.makedirs("state", exist_ok=True)
    first_run = not os.path.exists(STATE)
    seen = set() if first_run else set(json.load(open(STATE, encoding="utf-8")))
    new = [c for c in changes if c not in seen]
    if new and not first_run:
        body = "\n\n".join(pretty(i) for i in new)
        send_whatsapp(f"🚨 *שינוי חדש בט6!*\n\n{body}")
    json.dump(changes, open(STATE, "w", encoding="utf-8"), ensure_ascii=False)


if __name__ == "__main__":
    main()
