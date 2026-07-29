"""
Clasificador semántico opcional de proyectos de ley usando Claude Haiku.

Motivación: el filtro por keyword literal (`contiene_keywords`) descarta
proyectos cuyo tema es relevante pero que no contienen la palabra exacta
en el título ("neurodatos", "biometría", "tarificación vial", etc.). Un LLM
puede capturar sinónimos y contexto.

Uso:
    - Si la variable de entorno ANTHROPIC_API_KEY está seteada y el paquete
      `anthropic` está instalado, `classify()` devuelve una clasificación
      estructurada.
    - Si no, devuelve None y el código que llama debe caer al filtro por
      keywords como fallback.

Costo aproximado con Haiku 4.5 y prompt caching: ~1-2 USD/mes para cientos
de proyectos por corrida (cada 6h).
"""

import hashlib
import json
import os
from typing import Dict, Optional

try:
    from anthropic import Anthropic, APIError

    _ANTHROPIC_AVAILABLE = True
except ImportError:
    _ANTHROPIC_AVAILABLE = False

MODEL = "claude-haiku-4-5"
MAX_TOKENS = 256

SYSTEM_PROMPT = """Eres un clasificador de proyectos de ley chilenos para Wikimedia Chile.

Tu tarea es decidir si un proyecto de ley es relevante para alguno de estos temas de derechos digitales:

1. Inteligencia artificial: regulación de IA, sistemas algorítmicos, neurodatos, neurotecnologías, decisiones automatizadas.
2. Datos personales y privacidad: protección de datos, vigilancia, biometría, anonimización, tratamiento de datos.
3. Propiedad intelectual: derechos de autor, patentes, licencias, derecho de remuneración.
4. Libertad de expresión: libertad de prensa, regulación de contenido digital, censura, plataformas digitales.
5. Ciencia, innovación y tecnología: fomento a la I+D, financiamiento científico, ciencia abierta, transferencia tecnológica.

Clasifica con criterio estricto: un proyecto que sólo menciona "datos" al pasar no es relevante; uno que regula el tratamiento de datos biométricos sí lo es.

Devuelve ÚNICAMENTE un objeto JSON (sin texto adicional ni code fences) con estos campos:
- "relevante" (bool): true si cae en alguna de las 5 categorías.
- "categoria" (string): nombre exacto de la categoría o "No relevante".
- "confianza" (float 0.0-1.0): tu confianza en la clasificación.
- "razon" (string, máx 120 chars): explicación breve."""


def is_available() -> bool:
    """True si el SDK está instalado y hay API key."""
    return _ANTHROPIC_AVAILABLE and bool(os.getenv("ANTHROPIC_API_KEY"))


def classify(titulo: str, materia: str = "", resumen: str = "") -> Optional[Dict]:
    """
    Clasifica un proyecto. Devuelve dict con claves relevante/categoria/confianza/razon,
    o None si no se pudo clasificar (sin API key, SDK no instalado, o error de red/parseo).
    """
    if not is_available():
        return None

    client = Anthropic()

    user_content = f"Título: {titulo}"
    if materia:
        user_content += f"\nMateria: {materia}"
    if resumen:
        user_content += f"\nResumen: {resumen}"

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=[
                {
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": user_content}],
        )
    except APIError as e:
        print(f"Error de API clasificando '{titulo[:60]}': {e}")
        return None

    text = next(
        (b.text for b in response.content if getattr(b, "type", None) == "text"),
        "",
    ).strip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        print(f"Respuesta no-JSON clasificando '{titulo[:60]}': {text[:120]}")
        return None

    return parsed
