import pandas as pd
import requests
from bs4 import BeautifulSoup
import json
import os
import time
from typing import Optional, Dict, Any

DB_PATH = "data/db.json"
WATCHLIST_PATH = "data/watchlist_enriched.xlsx"

# Número máximo de reintentos para cada URL
MAX_REINTENTOS = 3


def load_db() -> Dict[str, Any]:
    """Carga la base de datos de hashes desde db.json."""
    if not os.path.exists(DB_PATH):
        return {}
    try:
        with open(DB_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"Error cargando db.json: {e}")
        return {}


def save_db(db: Dict[str, Any]) -> None:
    """Guarda la base de datos de hashes en db.json."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)


def get_data(url: str) -> Optional[Dict[str, Any]]:
    """
    Obtiene el hash del contenido de la URL.
    Usa los primeros 5000 caracteres para detectar cambios generales.
    Incluye reintentos en caso de fallos de red.
    """
    for intento in range(1, MAX_REINTENTOS + 1):
        try:
            r = requests.get(url, timeout=15)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            text = soup.get_text()
            
            return {
                "hash": hash(text[:5000]),
                "last_check": time.strftime("%Y-%m-%d %H:%M:%S")
            }
        except Exception as e:
            print(f"Intento {intento}/{MAX_REINTENTOS} fallido para {url}: {e}")
            if intento == MAX_REINTENTOS:
                return None
            time.sleep(2 ** intento)  # Espera exponencial: 2, 4, 8 segundos
    
    return None


def send_slack(msg: str) -> None:
    """Envía un mensaje a Slack usando el webhook configurado."""
    webhook = os.getenv("SLACK_WEBHOOK")
    if not webhook:
        print("SLACK_WEBHOOK no configurado. No se enviará notificación.")
        return
    
    try:
        response = requests.post(webhook, json={"text": msg}, timeout=10)
        response.raise_for_status()
        print("Notificación enviada a Slack.")
    except Exception as e:
        print(f"Error enviando a Slack: {e}")


def main() -> None:
    # Verificar que existe el archivo de watchlist
    if not os.path.exists(WATCHLIST_PATH):
        print(f"ERROR: No se encontró {WATCHLIST_PATH}. Ejecuta primero fetch_watchlist.py")
        return
    
    # Cargar la watchlist
    df = pd.read_excel(WATCHLIST_PATH)
    db = load_db()
    
    changes = []
    
    for _, row in df.iterrows():
        boletin = str(row["boletin"]).strip()
        url = str(row["url"]).strip()
        nombre = row.get("nombre", boletin)  # Usa 'nombre' si existe, sino el boletín
        
        print(f"Verificando: {nombre} ({boletin})")
        
        new = get_data(url)
        if not new:
            print(f"  ⚠️ No se pudo obtener datos para {boletin}")
            continue
        
        old = db.get(boletin)
        
        if old is None or old.get("hash") != new.get("hash"):
            changes.append((row, new))
            db[boletin] = new
            print(f"  🔄 Cambio detectado en {boletin}")
        else:
            print(f"  ✅ Sin cambios en {boletin}")
    
    save_db(db)
    
    if changes:
        msg = "🚨 *Cambios detectados en proyectos legislativos*\n\n"
        for row, new in changes:
            boletin = str(row["boletin"]).strip()
            nombre = row.get("nombre", boletin)
            url = str(row["url"]).strip()
            msg += f"• *{nombre}* (Boletín: {boletin})\n  <{url}|Ver proyecto>\n\n"
        
        send_slack(msg)
        print(msg)
    else:
        print("✅ Sin cambios en ningún proyecto.")


if __name__ == "__main__":
    main()
