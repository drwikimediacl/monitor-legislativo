import requests
from bs4 import BeautifulSoup
import json
import os
import time
from typing import Optional, Dict, Any, List

DB_PATH = "data/db.json"
PROJECTS_FILE = "data/discovered_projects.json"

MAX_REINTENTOS = 3


def load_db() -> Dict[str, Any]:
    if not os.path.exists(DB_PATH):
        return {}
    try:
        with open(DB_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}


def save_db(db: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)


def load_projects() -> List[Dict]:
    """Carga la lista de proyectos a monitorear desde el archivo JSON unificado."""
    if not os.path.exists(PROJECTS_FILE):
        print(f"ERROR: No se encontró {PROJECTS_FILE}. Ejecuta primero discover_projects.py")
        return []
    try:
        with open(PROJECTS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("proyectos", [])
    except Exception as e:
        print(f"Error cargando proyectos: {e}")
        return []


def get_data(url: str) -> Optional[Dict[str, Any]]:
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
            time.sleep(2 ** intento)
    return None


def send_slack(msg: str) -> None:
    webhook = os.getenv("SLACK_WEBHOOK")
    if not webhook:
        return
    try:
        requests.post(webhook, json={"text": msg}, timeout=10)
    except Exception as e:
        print(f"Error enviando a Slack: {e}")


def main() -> None:
    proyectos = load_projects()
    if not proyectos:
        return
    
    db = load_db()
    changes = []
    
    for p in proyectos:
        boletin = p["boletin"]
        url = p["url"]
        titulo = p["titulo"]
        
        print(f"Verificando: {titulo} ({boletin})")
        new = get_data(url)
        if not new:
            continue
        
        old = db.get(boletin)
        if old is None or old.get("hash") != new.get("hash"):
            changes.append((p, new))
            db[boletin] = new
            print(f"  🔄 Cambio detectado")
        else:
            print(f"  ✅ Sin cambios")
    
    save_db(db)
    
    if changes:
        msg = "🚨 *Cambios detectados en proyectos legislativos*\n\n"
        for p, new in changes:
            msg += f"• *{p['titulo']}* (Boletín: {p['boletin']})\n  <{p['url']}|Ver proyecto>\n\n"
        send_slack(msg)
        print(msg)
    else:
        print("✅ Sin cambios en ningún proyecto.")


if __name__ == "__main__":
    main()
