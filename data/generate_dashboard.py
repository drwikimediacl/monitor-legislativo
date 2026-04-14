#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
from datetime import datetime

# Rutas relativas al script (está en data/)
PROJECTS_FILE = "discovered_projects.json"
DB_FILE = "db.json"
OUTPUT_HTML = "../index.html"   # el HTML en la raíz para GitHub Pages


def load_json(path):
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def generate_dashboard():
    proyectos_data = load_json(PROJECTS_FILE)
    db_data = load_json(DB_FILE)
    
    proyectos = proyectos_data.get("proyectos", [])
    fecha_actualizacion = proyectos_data.get("fecha_actualizacion", datetime.now().isoformat())
    
    # Añadir último chequeo
    for p in proyectos:
        boletin = p["boletin"]
        if boletin in db_data:
            p["last_check"] = db_data[boletin].get("last_check", "Nunca")
        else:
            p["last_check"] = "Nunca"
    
    # Generar HTML (igual que antes)
    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Monitor Legislativo Chile</title>
    <link rel="stylesheet" href="https://cdn.datatables.net/1.13.4/css/jquery.dataTables.min.css">
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        h1 {{ color: #1a5276; }}
        .update-info {{ color: #666; margin-bottom: 20px; }}
        table {{ font-size: 14px; }}
    </style>
</head>
<body>
    <h1>📊 Monitor Legislativo - Proyectos de Ley</h1>
    <div class="update-info">
        Última actualización: {fecha_actualizacion}<br>
        Palabras clave: inteligencia artificial, datos personales, propiedad intelectual, derechos de autor, libertad de expresión, privacidad, innovación, ciencia.
    </div>
    
    <table id="tabla-proyectos" class="display" style="width:100%">
        <thead>
            <tr>
                <th>Boletín</th>
                <th>Título</th>
                <th>Origen</th>
                <th>Estado</th>
                <th>Fecha ingreso</th>
                <th>Último chequeo</th>
                <th>Enlace</th>
            </tr>
        </thead>
        <tbody>
"""
    
    for p in proyectos:
        boletin = p.get("boletin", "")
        titulo = p.get("titulo", "")
        origen = p.get("origen", "")
        estado = p.get("estado", "")
        fecha = p.get("fecha_ingreso", "")
        last_check = p.get("last_check", "")
        url = p.get("url", "")
        
        html += f"""
            <tr>
                <td>{boletin}</td>
                <td>{titulo}</td>
                <td>{origen}</td>
                <td>{estado}</td>
                <td>{fecha}</td>
                <td>{last_check}</td>
                <td><a href="{url}" target="_blank">Ver</a></td>
            </tr>
"""
    
    html += """
        </tbody>
    </table>
    
    <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
    <script src="https://cdn.datatables.net/1.13.4/js/jquery.dataTables.min.js"></script>
    <script>
        $(document).ready(function () {
            $('#tabla-proyectos').DataTable({
                language: {
                    url: '//cdn.datatables.net/plug-ins/1.13.4/i18n/es-ES.json'
                },
                order: [[4, 'desc']],
                pageLength: 25
            });
        });
    </script>
</body>
</html>
"""
    
    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)
    
    print(f"✅ Dashboard generado: {OUTPUT_HTML}")


if __name__ == "__main__":
    generate_dashboard()
