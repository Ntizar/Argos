"""Mesa — CLI del tablero. `tablero <comando> ...`

Códigos de salida: 0 ok · 1 rechazo (ErrorTablero) · 2 tablero ocupado.
Todo comando acepta --json (salida estructurada para agentes) y
--tablero <ruta> (por defecto ./tablero.json).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys

from . import __version__
from .lock import (forzar_liberacion, info_lock, lock_de_escritura)
from .modelo import (ESTADOS, ErrorTablero, Tablero, TableroOcupado)

RUTA_PLANTILLA_AGENTS = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "..", "plantilla", "REGLAS-MESA.md")

# comandos que solo escriben (necesitan lock); lecturas van sin lock
COMANDOS_LECTURA = {"estado", "ver", "preparadas", "bloqueadas", "lista", "version"}


# ------------------------------------------------------------------ salida

def _json(datos) -> str:
    return json.dumps(datos, ensure_ascii=False, indent=2)


def _fmt_tarea(t, extra="") -> str:
    base = f"[{t['id'] or '???'}] ({t['estado']}) {t['grupo']} :: {t['titulo']}"
    return base + (f" — {extra}" if extra else "")


# ------------------------------------------------------------------ comandos

def cmd_init(args) -> int:
    ruta = args.tablero
    if os.path.exists(ruta):
        raise ErrorTablero(f"{ruta} ya existe. No se sobreescribe nunca.")
    tab = Tablero(ruta)
    tab.datos = {"proyecto": args.nombre or "", "version": 1, "tareas": []}
    os.makedirs(os.path.dirname(os.path.abspath(ruta)) or ".", exist_ok=True)
    tab.guardar()
    creados = [ruta]
    if not args.sin_agents:
        destino = os.path.join(os.path.dirname(os.path.abspath(ruta)), "AGENTS.md")
        if not os.path.exists(destino):
            plantilla = _ruta_plantilla()
            if plantilla:
                shutil.copyfile(plantilla, destino)
                creados.append(destino)
            else:
                print("(aviso) plantilla AGENTS.md no encontrada; copia "
                      "plantilla/AGENTS.md del repo Mesa a mano.")
    if args.json:
        print(_json({"creados": creados}))
    else:
        for c in creados:
            print(f"Creado: {c}")
        print("Mesa lista. El agente empieza leyendo: tablero estado")
    return 0


def _ruta_plantilla():
    # dentro de un checkout del repo: plantilla/AGENTS.md a nivel de repo
    candidatos = [
        # instalado como paquete: site-packages/tablero/plantilla/
        os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "plantilla", "REGLAS-MESA.md"),
        # checkout del repo: plantilla/ a nivel de repo
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__)))), "plantilla", "REGLAS-MESA.md"),
    ]
    for c in candidatos:
        if os.path.exists(c):
            return c
    return None


def cmd_estado(args) -> int:
    tab = Tablero(args.tablero)
    tab.cargar()
    conteo = {e: 0 for e in ESTADOS}
    for t in tab.tareas:
        conteo[t["estado"]] += 1
    lock = info_lock(args.tablero)
    datos = {
        "proyecto": tab.datos.get("proyecto", ""),
        "total": len(tab.tareas),
        "conteo": conteo,
        "anomalias": tab.anomalias(),
        "lock": lock,
    }
    if args.json:
        print(_json(datos))
        return 0
    print(f"Mesa: {datos['proyecto'] or '(sin nombre)'} — {tab.ruta}")
    print(f"Total: {datos['total']} tareas")
    print("  " + " | ".join(f"{e}: {conteo[e]}" for e in ESTADOS))
    if conteo["en_curso"]:
        en_curso = [t for t in tab.tareas if t["estado"] == "en_curso"]
        for t in en_curso:
            print(f"  ▶ EN CURSO: {_fmt_tarea(t)}")
    prep = tab.preparadas()
    if prep:
        print("Preparadas para trabajar:")
        for t in prep:
            print(f"  {_fmt_tarea(t)}")
    if datos["anomalias"]:
        print("ANOMALÍAS:")
        for a in datos["anomalias"]:
            print(f"  - {a}")
    if lock:
        print(f"(lock presente: PID {lock.get('pid')} — {lock.get('comando', '?')})")
    return 0


def cmd_ver(args) -> int:
    tab = Tablero(args.tablero)
    tab.cargar()
    t = tab._exigir_id(args.id)
    faltan = tab.faltan_dependencias(t)
    deps = ", ".join(t["depende_de"]) or "(ninguna)"
    datos = {**t, "dependencias_sin_hacer": faltan}
    if args.json:
        print(_json(datos))
        return 0
    print(f"[{t['id']}] {t['titulo']}")
    print(f"  Estado: {t['estado']} | Grupo: {t['grupo']}")
    if t["descripcion"]:
        print(f"  Descripción: {t['descripcion']}")
    print(f"  Depende de: {deps}")
    if faltan:
        print(f"  BLOQUEADA por: {', '.join(faltan)}")
    if t["notas"]:
        print("  Notas:")
        for linea in t["notas"].splitlines():
            print(f"    {linea}")
    return 0


def cmd_preparadas(args) -> int:
    tab = Tablero(args.tablero)
    tab.cargar()
    prep = tab.preparadas()
    if args.json:
        print(_json(prep))
        return 0
    if not prep:
        print("Ninguna tarjeta preparada. Revisa `tablero bloqueadas` "
              "y `tablero estado`.")
        return 0
    print(f"{len(prep)} tarjeta(s) preparada(s):")
    for t in prep:
        print(f"  {_fmt_tarea(t)}")
    return 0


def cmd_bloqueadas(args) -> int:
    tab = Tablero(args.tablero)
    tab.cargar()
    bloq = tab.bloqueadas()
    if args.json:
        print(_json([{"id": t["id"], "titulo": t["titulo"], "bloquea": f}
                     for t, f in bloq]))
        return 0
    if not bloq:
        print("Ninguna tarjeta bloqueada.")
        return 0
    print(f"{len(bloq)} tarjeta(s) bloqueada(s):")
    for t, faltan in bloq:
        print(f"  {_fmt_tarea(t, 'espera a: ' + ', '.join(faltan))}")
    return 0


def cmd_lista(args) -> int:
    tab = Tablero(args.tablero)
    tab.cargar()
    tareas = tab.tareas
    if args.filtro:
        tareas = [t for t in tareas
                  if t["estado"] == args.filtro or
                  t["grupo"].lower() == args.filtro.lower()]
    if args.json:
        print(_json(tareas))
        return 0
    if not tareas:
        print("Sin resultados.")
        return 0
    for t in tareas:
        print(f"  {_fmt_tarea(t)}")
    return 0


def cmd_empezar(args) -> int:
    with lock_de_escritura(args.tablero, "empezar"):
        tab = Tablero(args.tablero)
        tab.cargar()
        tab.normalizar()  # desbloqueo automático antes de trabajar
        r = tab.transicion(args.id, "en_curso", "empezar", "agente")
        tab.guardar()
    _salir_transicion(args, r)
    return 0


def cmd_terminar(args) -> int:
    with lock_de_escritura(args.tablero, "terminar"):
        tab = Tablero(args.tablero)
        tab.cargar()
        r = tab.transicion(args.id, "revision", "terminar", "agente")
        tab.guardar()
    _salir_transicion(args, r)
    print("Entregado a revisión. Tu trabajo acaba aquí: informa al humano "
          "(qué hiciste, archivos tocados, cómo verificarlo) y ESPERA.")
    return 0


def cmd_pausar(args) -> int:
    with lock_de_escritura(args.tablero, "pausar"):
        tab = Tablero(args.tablero)
        tab.cargar()
        r = tab.transicion(args.id, "por_hacer", "pausar", "agente")
        tab.guardar()
    _salir_transicion(args, r)
    return 0


def _salir_transicion(args, r):
    if args.json:
        print(_json(r))
    else:
        print(f"{r['id']}: {r['desde']} → {r['hacia']}")


def cmd_editar(args) -> int:
    with lock_de_escritura(args.tablero, "editar"):
        tab = Tablero(args.tablero)
        tab.cargar()
        r = tab.editar_notas(args.id, " ".join(args.texto))
        tab.guardar()
    if args.json:
        print(_json(r))
    else:
        print(f"Notas de {r['id']} actualizadas.")
    return 0


def cmd_proponer(args) -> int:
    with lock_de_escritura(args.tablero, "proponer"):
        tab = Tablero(args.tablero)
        tab.cargar()
        r = tab.proponer(args.grupo, args.titulo, args.descripcion,
                         args.depende_de)
        tab.guardar()
    if args.json:
        print(_json(r))
    else:
        print(f"Propuesta creada: [{r['id']}] {args.titulo} "
              f"(estado: propuesta, esperando aprobación humana).")
    return 0


def cmd_aprobar(args) -> int:
    with lock_de_escritura(args.tablero, "aprobar"):
        tab = Tablero(args.tablero)
        tab.cargar()
        r = tab.aprobar(args.id)
        tab.normalizar()
        tab.guardar()
    _salir_transicion(args, r)
    return 0


def cmd_hecha(args) -> int:
    with lock_de_escritura(args.tablero, "hecha"):
        tab = Tablero(args.tablero)
        tab.cargar()
        r = tab.marcar_hecha(args.id)
        tab.normalizar()
        tab.guardar()
    _salir_transicion(args, r)
    print("Recuerda: `hecha` es SOLO humano. Un agente nunca debe ejecutarlo.")
    return 0


def cmd_rechazar(args) -> int:
    with lock_de_escritura(args.tablero, "rechazar"):
        tab = Tablero(args.tablero)
        tab.cargar()
        r = tab.rechazar(args.id)
        tab.guardar()
    if args.json:
        print(_json(r))
    else:
        print(f"Propuesta {r['id']} rechazada (borrada).")
    return 0


def cmd_dep(args) -> int:
    with lock_de_escritura(args.tablero, "dep"):
        tab = Tablero(args.tablero)
        tab.cargar()
        r = tab.anadir_dependencia(args.bloquea, args.bloqueada)
        tab.normalizar()
        tab.guardar()
    if args.json:
        print(_json(r))
    else:
        print(f"{r['bloquea']} bloquea a {r['bloqueada']}.")
    return 0


def cmd_normalizar(args) -> int:
    with lock_de_escritura(args.tablero, "normalizar"):
        tab = Tablero(args.tablero)
        tab.cargar()
        r = tab.normalizar()
        tab.guardar()
    if args.json:
        print(_json(r))
    else:
        if r["ids_asignados"]:
            print("IDs asignados: " + ", ".join(r["ids_asignados"]))
        if r["cambios"]:
            for c in r["cambios"]:
                print(f"  {c}")
        if not r["ids_asignados"] and not r["cambios"]:
            print("Tablero normalizado: nada que cambiar.")
    return 0


def cmd_sync(args) -> int:
    carpeta = os.path.dirname(os.path.abspath(args.tablero)) or "."
    if not os.path.isdir(os.path.join(carpeta, ".git")):
        raise ErrorTablero(
            f"{carpeta} no es un repo git: sync no aplica.")
    pasos = [["git", "pull", "--rebase", "--autostash"],
             ["git", "push"]]
    resultado = []
    for paso in pasos:
        p = subprocess.run(paso, cwd=carpeta, capture_output=True, text=True)
        resultado.append({"cmd": " ".join(paso),
                          "code": p.returncode,
                          "out": (p.stdout + p.stderr).strip()})
        if p.returncode != 0:
            if args.json:
                print(_json({"ok": False, "pasos": resultado}))
            else:
                print(f"FALLO en: {' '.join(paso)}", file=sys.stderr)
                print((p.stdout + p.stderr).strip(), file=sys.stderr)
                print("No fuerces el push: resuelve el conflicto a mano o pídeselo al humano.",
                      file=sys.stderr)
            return 1
    if args.json:
        print(_json({"ok": True, "pasos": resultado}))
    else:
        print("Sync OK: pull --rebase + push sin conflictos.")
    return 0


def cmd_unlock(args) -> int:
    r = forzar_liberacion(args.tablero)
    if args.json:
        print(_json({"liberado": r}))
    else:
        print("Lock eliminado." if r else "No había lock.")
    return 0


# ------------------------------------------------------------------ parser

def construir_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="tablero",
        description="Mesa: tablero de tareas humano+agente. Hecho con ❤️ por David Antizar.")
    p.add_argument("--version", action="version", version=f"mesa {__version__}")
    p.add_argument("--tablero", default="tablero.json",
                   help="ruta del tablero.json (por defecto ./tablero.json)")
    p.add_argument("--json", action="store_true",
                   help="salida en JSON para agentes")
    sub = p.add_subparsers(dest="comando", required=True)

    def sp(nombre, fn, ayuda):
        q = sub.add_parser(nombre, help=ayuda)
        # SUPPRESS: los flags comunes funcionan ANTES o DESPUÉS del subcomando
        # sin que el default del subparser pise lo que el parser global ya leyó.
        q.add_argument("--tablero", default=argparse.SUPPRESS)
        q.add_argument("--json", action="store_true", default=argparse.SUPPRESS)
        q.set_defaults(fn=fn)
        return q

    q = sp("init", cmd_init, "crea tablero.json (+ AGENTS.md)")
    q.add_argument("nombre", nargs="?", default="")
    q.add_argument("--sin-agents", action="store_true")

    sp("estado", cmd_estado, "resumen del tablero y anomalías")

    q = sp("ver", cmd_ver, "detalle de una tarjeta")
    q.add_argument("id")

    sp("preparadas", cmd_preparadas, "tarjetas por_hacer listas para trabajar")
    sp("bloqueadas", cmd_bloqueadas, "tarjetas bloqueadas y por qué")

    q = sp("lista", cmd_lista, "lista filtrada por estado o grupo")
    q.add_argument("filtro", nargs="?", default=None)

    q = sp("empezar", cmd_empezar, "por_hacer → en_curso (agente)")
    q.add_argument("id")
    q = sp("terminar", cmd_terminar, "en_curso → revision (agente)")
    q.add_argument("id")
    q = sp("pausar", cmd_pausar, "en_curso → por_hacer (agente)")
    q.add_argument("id")

    q = sp("editar", cmd_editar, "añade notas (solo en_curso)")
    q.add_argument("id")
    q.add_argument("texto", nargs="+")

    q = sp("proponer", cmd_proponer, "crea una tarjeta en propuesta")
    q.add_argument("grupo")
    q.add_argument("titulo")
    q.add_argument("descripcion")
    q.add_argument("--depende-de", action="append", default=[])

    q = sp("aprobar", cmd_aprobar, "propuesta → por_hacer (HUMANO)")
    q.add_argument("id")
    q = sp("hecha", cmd_hecha, "revision → hecha (SOLO HUMANO)")
    q.add_argument("id")
    q = sp("rechazar", cmd_rechazar, "borra una propuesta (HUMANO)")
    q.add_argument("id")

    q = sp("dep", cmd_dep, "A bloquea a B (rechaza ciclos)")
    q.add_argument("bloquea")
    q.add_argument("bloqueada")

    sp("normalizar", cmd_normalizar, "asigna IDs y recalcula bloqueadas")
    sp("sync", cmd_sync, "git pull --rebase + push del proyecto")
    sp("unlock", cmd_unlock, "elimina un lock colgado")
    return p


def main(argv=None) -> int:
    parser = construir_parser()
    args = parser.parse_args(argv)
    try:
        return args.fn(args)
    except TableroOcupado as e:
        print(f"OCUPADO: {e}", file=sys.stderr)
        return 2
    except ErrorTablero as e:
        print(f"RECHAZADO: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
