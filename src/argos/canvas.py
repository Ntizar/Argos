"""Argos — proyección visual del tablero: Obsidian Canvas (.canvas).

argos.json es la ÚNICA fuente de verdad; el .canvas es una vista regenerable que
se abre con Obsidian: colores = estados, flechas = dependencias, niveles = profundidad.
Paleta Kanvas: morada propuesta · roja por_hacer · naranja en_curso · cian revision ·
verde hecha · gris bloqueada.
"""
from __future__ import annotations

import json
import os
import tempfile

COLOR_ESTADO = {
    "propuesta": "6",       # morado
    "por_hacer": "1",       # rojo
    "en_curso": "2",        # naranja
    "revision": "5",        # cian
    "hecha": "4",           # verde
    "bloqueada": "#8f8f8f", # gris (hex, fuera de la paleta oficial)
}

EMOJI_ESTADO = {
    "propuesta": "🟣", "por_hacer": "🔴", "en_curso": "🟠",
    "revision": "🔵", "hecha": "🟢", "bloqueada": "⬜",
}

ANCHO = 380
ALTO = 210
H_GAP = 110
V_GAP = 60


def _profundidades(tareas):
    """Profundidad (cadena más larga hacia una raíz) por tarjeta; 0 = sin deps."""
    deps = {t["id"]: t.get("depende_de", []) for t in tareas}
    memo = {}

    def p(tid, en_visita):
        if tid in memo:
            return memo[tid]
        if tid in en_visita:
            return 0  # ciclo: se corta (el CLI no los permite; defensivo)
        en_visita = en_visita | {tid}
        valor = max((1 + p(d, en_visita) for d in deps[tid] if d in deps),
                    default=0)
        memo[tid] = valor
        return valor

    return {tid: p(tid, frozenset()) for tid in deps}


def _tarjeta_texto(t):
    desc = (t.get("descripcion") or "").strip()
    if len(desc) > 220:
        desc = desc[:217] + "…"
    nota = (t.get("notas") or "").strip()
    lineas = [f"{EMOJI_ESTADO.get(t['estado'], '⚪')} **{t['id']} · {t['estado']}**",
              f"*{t.get('grupo') or 'General'}* — {t.get('titulo', '')}",
              "", desc]
    if nota:
        lineas += ["", f"> {nota}"]
    return "\n".join(lineas)


def generar_canvas(datos):
    """Construye el JSON de Canvas (nodos+aristas) desde los datos de argos.json.

    Determinista: mismos datos → mismo fichero (diffs de git limpios).
    """
    tareas = [t for t in datos.get("tareas", []) if t.get("id")]
    prof = _profundidades(tareas)
    niveles = {}
    for t in tareas:
        niveles.setdefault(prof.get(t["id"], 0), []).append(t)
    nodes = []
    for nivel in sorted(niveles):
        for i, t in enumerate(sorted(niveles[nivel], key=lambda x: x["id"])):
            nodes.append({
                "id": t["id"],
                "type": "text",
                "text": _tarjeta_texto(t),
                "x": nivel * (ANCHO + H_GAP),
                "y": i * (ALTO + V_GAP),
                "width": ANCHO,
                "height": ALTO,
                "color": COLOR_ESTADO.get(t["estado"], "#8f8f8f"),
            })
    ids = {t["id"] for t in tareas}
    edges = []
    e = 0
    for t in sorted(tareas, key=lambda x: x["id"]):
        for d in sorted(t.get("depende_de", [])):
            if d in ids:
                e += 1
                edges.append({"id": f"dep-{e:03d}", "fromNode": d,
                              "fromSide": "right", "toNode": t["id"],
                              "toSide": "left"})
    return {"nodes": nodes, "edges": edges}


def escribir_canvas(ruta, canvas):
    """Escritura atómica (igual que argos.json): tmp en la carpeta + replace."""
    carpeta = os.path.dirname(os.path.abspath(ruta)) or "."
    fd, tmp = tempfile.mkstemp(prefix=".canvas-", suffix=".tmp", dir=carpeta)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(canvas, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp, ruta)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
