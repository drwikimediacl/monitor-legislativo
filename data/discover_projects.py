#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import xml.etree.ElementTree as ET
import json
import os
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from bs4 import BeautifulSoup

# ================= CONFIGURACIÓN =================
KEYWORDS = [
    "inteligencia artificial",
    "datos personales",
    "propiedad intelectual",
    "derechos de autor",
    "libertad de expresión",
    "privacidad",
    "innovación",
    "ciencia"
]

DIAS_HACIA_ATRAS = 60
MAX_REINTENTOS = 3

# Rutas relativas al script (está dentro de data/)
OUTPUT_FILE = "discovered_projects.json"
WATCHLIST_FILE = "watchlist_enriched.xlsx"


def contiene_keywords(texto: str) -> bool:
    if not texto:
        return False
    texto_lower = texto.lower()
    return any(kw in texto_lower for kw in KEYWORDS)


def obtener_con_reintentos(url: str, timeout: int = 30) -> Optional[requests.Response]:
    for intento in range(1, MAX_REINTENTOS + 1):
        try:
            resp = requests.get(url, timeout=timeout)
            resp.raise_for_status()
            return resp
        except Exception as e:
            print(f"Intento {intento}/{MAX_REINTENTOS} fallido para {url}: {e}")
            if intento == MAX_REINTENTOS:
                return None
            time.sleep(2 ** intento)
    return None


def obtener_proyectos_senado() -> List[Dict]:
    proyectos = []
    fecha_inicio = (datetime.now() - timedelta(days=DIAS_HACIA_ATRAS)).strftime("%d/%m/%Y")
    fecha_fin = datetime.now().strftime("%d/%m/%Y")
    url = f"https://tramitacion.senado.cl/wspublico/tramitacion_lista.php?fecha_inicio={fecha_inicio}&fecha_fin={fecha_fin}"
    print(f"Consultando Senado: {url}")
    
    resp = obtener_con_reintentos(url)
    if not resp:
        return []
    
    try:
        resp.encoding = 'utf-8'
        root = ET.fromstring(resp.content)
        for item in root.findall(".//proyecto"):
            boletin = item.findtext("boletin", "").strip()
            titulo = item.findtext("titulo", "").strip()
            materia = item.findtext("materia", "").strip()
            estado = item.findtext("estado", "").strip()
            fecha_ingreso = item.findtext("fecha_ingreso", "").strip()
            try:
                fecha_iso = datetime.strptime(fecha_ingreso, "%d/%m/%Y").strftime("%Y-%m-%d")
            except:
                fecha_iso = fecha_ingreso
            
            texto_busqueda = f"{titulo} {materia}".lower()
            if contiene_keywords(texto_busqueda):
                proyectos.append({
                    "origen": "Senado",
                    "boletin": boletin,
                    "titulo": titulo,
                    "materia": materia,
                    "estado": estado,
                    "fecha_ingreso": fecha_iso,
                    "url": f"https://www.senado.cl/appsenado/templates/tramitacion/index.php?boletin_ini={boletin}"
                })
    except Exception as e:
        print(f"Error procesando XML del Senado: {e}")
    
    print(f"Senado: {len(proyectos)} proyectos relevantes encontrados.")
    return proyectos


def obtener_proyectos_camara() -> List[Dict]:
    proyectos = []
    url = "https://www.camara.cl/legislacion/proyectosdeley/proyectos_ley.aspx"
    print(f"Consultando Cámara: {url}")
    
    resp = obtener_con_reintentos(url)
    if not resp:
        return []
    
    try:
        soup = BeautifulSoup(resp.content, "html.parser")
        tabla = soup.find("table", {"class": "grilla"}) or soup.find("table", {"id": "grilla"})
        if not tabla:
            print("No se encontró la tabla de proyectos en la Cámara.")
            return []
        
        filas = tabla.find_all("tr")[1:]
        for fila in filas:
            celdas = fila.find_all("td")
            if len(celdas) < 5:
                continue
            boletin = celdas[0].get_text(strip=True)
            titulo = celdas[1].get_text(strip=True)
            fecha = celdas[2].get_text(strip=True)
            estado = celdas[3].get_text(strip=True)
            
            link_tag = celdas[0].find("a")
            url_tramitacion = ""
            if link_tag and link_tag.get("href"):
                href = link_tag["href"]
                if href.startswith("/"):
                    url_tramitacion = f"https://www.camara.cl{href}"
                else:
                    url_tramitacion = href
            
            try:
                fecha_iso = datetime.strptime(fecha, "%d/%m/%Y").strftime("%Y-%m-%d")
            except:
                fecha_iso = fecha
            
            if contiene_keywords(titulo):
                proyectos.append({
                    "origen": "Cámara de Diputados",
                    "boletin": boletin,
                    "titulo": titulo,
                    "fecha_ingreso": fecha_iso,
                    "estado": estado,
                    "url": url_tramitacion or f"https://www.camara.cl/legislacion/ProyectosDeLey/tramitacion.aspx?prmID={boletin}"
                })
    except Exception as e:
        print(f"Error scraping Cámara: {e}")
    
    print(f"Cámara: {len(proyectos)} proyectos relevantes encontrados.")
    return proyectos


def cargar_watchlist_manual() -> List[Dict]:
    if not os.path.exists(WATCHLIST_FILE):
        return []
    try:
        import pandas as pd
        df = pd.read_excel(WATCHLIST_FILE)
        proyectos = []
        for _, row in df.iterrows():
            proyectos.append({
                "origen": "Watchlist manual",
                "boletin": str(row["boletin"]).strip(),
                "titulo": row.get("nombre", str(row["boletin"])),
                "url": str(row["url"]).strip(),
                "estado": "Monitoreado manualmente",
                "fecha_ingreso": "",
                "materia": ""
            })
        return proyectos
    except Exception as e:
        print(f"Error cargando watchlist manual: {e}")
        return []


def main():
    print("=== DESCUBRIENDO PROYECTOS LEGISLATIVOS ===")
    proyectos_auto = []
    proyectos_auto.extend(obtener_proyectos_senado())
    proyectos_auto.extend(obtener_proyectos_camara())
    
    unicos = {}
    for p in proyectos_auto:
        if p["boletin"] not in unicos:
            unicos[p["boletin"]] = p
    proyectos_auto = list(unicos.values())
    proyectos_auto.sort(key=lambda x: x.get("fecha_ingreso", ""), reverse=True)
    
    proyectos_manual = cargar_watchlist_manual()
    boletines_auto = {p["boletin"] for p in proyectos_auto}
    for pm in proyectos_manual:
        if pm["boletin"] not in boletines_auto:
            proyectos_auto.append(pm)
    
    output = {
        "fecha_actualizacion": datetime.now().isoformat(),
        "total_proyectos": len(proyectos_auto),
        "proyectos": proyectos_auto
    }
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Total proyectos combinados: {len(proyectos_auto)}")
    print(f"   - Descubiertos automáticamente: {len(proyectos_auto) - len(proyectos_manual)}")
    print(f"   - Watchlist manual: {len(proyectos_manual)}")


if __name__ == "__main__":
    main()
