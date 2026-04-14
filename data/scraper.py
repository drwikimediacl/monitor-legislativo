import pandas as pd
import requests
from bs4 import BeautifulSoup
import json
import os

DB_PATH = "data/db.json"

def load_db():
    if not os.path.exists(DB_PATH):
        return {}
    with open(DB_PATH, "r") as f:
        return json.load(f)

def save_db(db):
    with open(DB_PATH, "w") as f:
        json.dump(db, f, indent=2)

def get_data(url):
    try:
        r = requests.get(url, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")

        text = soup.get_text()

        return {
            "hash": hash(text[:5000])  # detecta cambios generales
        }

    except Exception as e:
        print("Error:", e)
        return None

def send_slack(msg):
    webhook = os.getenv("SLACK_WEBHOOK")
    if not webhook:
        return

    requests.post(webhook, json={"text": msg})

def main():
    df = pd.read_excel("data/watchlist_enriched.xlsx")
    db = load_db()

    changes = []

    for _, row in df.iterrows():
        boletin = row["boletin"]
        url = row["url"]

        new = get_data(url)
        if not new:
            continue

        old = db.get(boletin)

        if old != new:
            changes.append((row, new))
            db[boletin] = new

    save_db(db)

    if changes:
        msg = "🚨 Cambios detectados:\n\n"

        for row, new in changes:
            msg += f"- {row['nombre']} ({row['boletin']})\n"

        send_slack(msg)
        print(msg)
    else:
        print("Sin cambios")

if __name__ == "__main__":
    main()
