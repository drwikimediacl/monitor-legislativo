#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import json
import os
import sys
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from bs4 import BeautifulSoup

# Clasificador LLM opcional — si ANTHROPIC_API_KEY está seteada, reemplaza
# el filtro por keyword exacto del título con clasificación semántica.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from classifier import classify as llm_classify, is_available as llm_available

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

OUTPUT_FILE = "discovered_projects.json"
# El workflow corre este script desde la raíz, y fetch_watchlist.py escribe
# en "data/watchlist_enriched.xlsx" — mantener coherencia.
WATCHLIST_FILE = "data/watchlist_enriched.xlsx"


def contiene_keywords(texto: str) -> bool:
    if not texto:
        return False
    texto_lower = texto.lower()
    return any(kw in texto_lower for kw in KEYWORDS)


def obtener_con_reintentos(url: str, method: str = "GET", data: Optional[Dict] = None, timeout: int = 30) -> Optional[requests.Response]:
    for intento in range(1, MAX_REINTENTOS + 1):
        try:
            if method == "POST":
                resp = requests.post(url, data=data, timeout=timeout)
            else:
                resp = requests.get(url, timeout=timeout)
            resp.raise_for_status()
            return resp
        except Exception as e:
            print(f"Intento {intento}/{MAX_REINTENTOS} fallido para {url}: {e}")
            if intento == MAX_REINTENTOS:
                return None
            time.sleep(2 ** intento)
    return None


def obtener_proyectos_camara_buscador() -> List[Dict]:
    """
    Utiliza el buscador de la Cámara de Diputados enviando un POST con las palabras clave.
    Filtra por proyectos ingresados en los últimos DIAS_HACIA_ATRAS días.
    """
    proyectos = []
    url = "https://www.camara.cl/legislacion/buscadordeProyectos/buscador.aspx"
    
    # Primero obtenemos la página para extraer VIEWSTATE y otros campos ocultos
    resp_get = obtener_con_reintentos(url)
    if not resp_get:
        return []
    
    soup = BeautifulSoup(resp_get.text, "html.parser")
    
    # Extraer campos ocultos necesarios para el POST
    viewstate = soup.find("input", {"name": "__VIEWSTATE"})
    viewstategen = soup.find("input", {"name": "__VIEWSTATEGENERATOR"})
    eventvalidation = soup.find("input", {"name": "__EVENTVALIDATION"})
    
    if not viewstate or not viewstategen or not eventvalidation:
        print("No se pudieron obtener los campos ocultos del formulario de búsqueda.")
        return []
    
    # Calcular fecha desde (DD/MM/AAAA)
    fecha_desde = (datetime.now() - timedelta(days=DIAS_HACIA_ATRAS)).strftime("%d/%m/%Y")
    fecha_hasta = datetime.now().strftime("%d/%m/%Y")
    
    # Construir la frase de búsqueda uniendo palabras clave con OR
    frase_busqueda = " OR ".join(KEYWORDS)
    
    # Datos del POST (simulando el formulario)
    post_data = {
        "__VIEWSTATE": viewstate["value"],
        "__VIEWSTATEGENERATOR": viewstategen["value"],
        "__EVENTVALIDATION": eventvalidation["value"],
        "ctl00$main$txtFechaDesde": fecha_desde,
        "ctl00$main$txtFechaHasta": fecha_hasta,
        "ctl00$main$txtTexto": frase_busqueda,
        "ctl00$main$btnBuscar": "Buscar"
    }
    
    print(f"Buscando en Cámara con frase: {frase_busqueda[:100]}...")
    resp_post = obtener_con_reintentos(url, method="POST", data=post_data, timeout=45)
    if not resp_post:
        return []
    
    soup_resp = BeautifulSoup(resp_post.text, "html.parser")
    
    # Buscar la tabla de resultados (puede tener id 'grilla' o class 'grilla')
    tabla = soup_resp.find("table", {"id": "grilla"}) or soup_resp.find("table", {"class": "grilla"})
    if not tabla:
        print("No se encontró la tabla de resultados en la respuesta del buscador.")
        return []
    
    filas = tabla.find_all("tr")[1:]  # saltar cabecera
    for fila in filas:
        celdas = fila.find_all("td")
        if len(celdas) < 5:
            continue
        
        boletin = celdas[0].get_text(strip=True)
        titulo = celdas[1].get_text(strip=True)
        fecha = celdas[2].get_text(strip=True)
        estado = celdas[3].get_text(strip=True)
        
        # Enlace a tramitación
        link_tag = celdas[0].find("a")
        url_tramitacion = ""
        if link_tag and link_tag.get("href"):
            href = link_tag["href"]
            if href.startswith("/"):
                url_tramitacion = f"https://www.camara.cl{href}"
            else:
                url_tramitacion = href
        
        # Convertir fecha a ISO
        try:
            fecha_iso = datetime.strptime(fecha, "%d/%m/%Y").strftime("%Y-%m-%d")
        except:
            fecha_iso = fecha
        
        # Filtro por keyword como prefiltro barato. Si hay LLM disponible,
        # damos una segunda oportunidad a los proyectos que no matchean por
        # keyword literal pero podrían ser relevantes semánticamente (e.g.
        # "neurodatos" no calza con "privacidad" pero es del mismo tema).
        match_keyword = contiene_keywords(titulo)
        clasificacion = None

        if llm_available():
            clasificacion = llm_classify(titulo=titulo)
            es_relevante = clasificacion["relevante"] if clasificacion else match_keyword
        else:
            es_relevante = match_keyword

        if not es_relevante:
            continue

        proyecto = {
            "origen": "Cámara de Diputados",
            "boletin": boletin,
            "titulo": titulo,
            "fecha_ingreso": fecha_iso,
            "estado": estado,
            "url": url_tramitacion or f"https://www.camara.cl/legislacion/ProyectosDeLey/tramitacion.aspx?prmID={boletin}"
        }
        if clasificacion:
            proyecto["clasificacion"] = clasificacion
        proyectos.append(proyecto)

    return proyectos


def cargar_watchlist_manual() -> List[Dict]:
    if not os.path.exists(WATCHLIST_FILE):
        print(f"Watchlist manual no encontrada en {WATCHLIST_FILE}")
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
    if llm_available():
        print("✨ Clasificador LLM activado (ANTHROPIC_API_KEY seteada)")
    else:
        print("ℹ️  Clasificador LLM no disponible — usando sólo filtro por keywords")
    proyectos = []
    
    # Intentar con el buscador de la Cámara
    camara_projects = obtener_proyectos_camara_buscador()
    proyectos.extend(camara_projects)
    print(f"Cámara (buscador): {len(camara_projects)} proyectos encontrados.")
    
    # Cargar watchlist manual
    manual_projects = cargar_watchlist_manual()
    proyectos.extend(manual_projects)
    print(f"Watchlist manual: {len(manual_projects)} proyectos.")
    
    # Eliminar duplicados por boletín
    unicos = {}
    for p in proyectos:
        if p["boletin"] not in unicos:
            unicos[p["boletin"]] = p
    proyectos_finales = list(unicos.values())
    proyectos_finales.sort(key=lambda x: x.get("fecha_ingreso", ""), reverse=True)
    
    output = {
        "fecha_actualizacion": datetime.now().isoformat(),
        "total_proyectos": len(proyectos_finales),
        "proyectos": proyectos_finales
    }
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Total proyectos combinados: {len(proyectos_finales)}")


if __name__ == "__main__":
    main()
