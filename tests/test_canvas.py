"""Comando `argos canvas`: proyección Obsidian del tablero."""
import json
import os

from conftest import run


def _cargar(ruta):
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def _nodo(canvas, tid):
    return next(n for n in canvas["nodes"] if n["id"] == tid)


def test_canvas_genera_archivo_valido(tablero):
    run(["--argos", tablero, "proponer", "Dev", "A", "uno"])
    code, out, err = run(["--argos", tablero, "canvas"])
    assert code == 0 and "Argos.canvas" in out, f"{out}{err}"
    canvas = _cargar(os.path.join(os.path.dirname(tablero), "Argos.canvas"))
    assert len(canvas["nodes"]) == 1 and canvas["edges"] == []
    assert _nodo(canvas, "DEV01")["color"] == "6"  # propuesta → morado


def test_tablero_vacio_no_rompe(tablero):
    code, _, err = run(["--argos", tablero, "canvas"])
    assert code == 0, err
    canvas = _cargar(os.path.join(os.path.dirname(tablero), "Argos.canvas"))
    assert canvas["nodes"] == [] and canvas["edges"] == []


def test_colores_siguen_estados(tablero):
    run(["--argos", tablero, "proponer", "Dev", "A", "uno"])
    run(["--argos", tablero, "aprobar", "DEV01"])
    run(["--argos", tablero, "empezar", "DEV01"])
    run(["--argos", tablero, "canvas"])
    canvas = _cargar(os.path.join(os.path.dirname(tablero), "Argos.canvas"))
    assert _nodo(canvas, "DEV01")["color"] == "2"  # en_curso → naranja
    run(["--argos", tablero, "terminar", "DEV01"])
    run(["--argos", tablero, "canvas"])
    canvas = _cargar(os.path.join(os.path.dirname(tablero), "Argos.canvas"))
    assert _nodo(canvas, "DEV01")["color"] == "5"  # revision → cian


def test_bloqueada_gris_y_capas_por_dependencia(tablero):
    run(["--argos", tablero, "proponer", "Dev", "A", "raíz"])
    run(["--argos", tablero, "proponer", "Dev", "B", "hija",
         "--depende-de", "DEV01"])
    run(["--argos", tablero, "aprobar", "DEV01"])
    run(["--argos", tablero, "aprobar", "DEV02"])
    run(["--argos", tablero, "normalizar"])  # B queda bloqueada (A no hecha)
    run(["--argos", tablero, "canvas"])
    canvas = _cargar(os.path.join(os.path.dirname(tablero), "Argos.canvas"))
    assert _nodo(canvas, "DEV02")["color"] == "#8f8f8f"  # gris
    assert _nodo(canvas, "DEV01")["x"] < _nodo(canvas, "DEV02")["x"]  # capas
    edge = canvas["edges"][0]
    assert edge["fromNode"] == "DEV01" and edge["toNode"] == "DEV02"


def test_hecha_verde(tablero):
    run(["--argos", tablero, "proponer", "Dev", "A", "uno"])
    for paso in ("aprobar", "empezar", "terminar"):
        run(["--argos", tablero, paso, "DEV01"])
    run(["--argos", tablero, "hecha", "DEV01"])
    run(["--argos", tablero, "canvas"])
    canvas = _cargar(os.path.join(os.path.dirname(tablero), "Argos.canvas"))
    assert _nodo(canvas, "DEV01")["color"] == "4"  # hecha → verde


def test_determinista_y_ruta_personalizada(tablero):
    run(["--argos", tablero, "proponer", "Dev", "A", "uno"])
    run(["--argos", tablero, "proponer", "Dev", "B", "dos",
         "--depende-de", "DEV01"])
    p1 = os.path.join(os.path.dirname(tablero), "v1.canvas")
    p2 = os.path.join(os.path.dirname(tablero), "v2.canvas")
    run(["--argos", tablero, "canvas", p1])
    run(["--argos", tablero, "canvas", p2])
    with open(p1, encoding="utf-8") as a, open(p2, encoding="utf-8") as b:
        assert a.read() == b.read()  # misma vista → diff de git limpio
