"""Argos — modelo del tablero: estados, transiciones, dependencias, IDs.

Filosofía Kanvas: el agente nunca toca el JSON; el CLI valida todo por código.
Cero dependencias externas (stdlib only) para instalar igual en Windows y Linux.
"""
from __future__ import annotations

import json
import os
import re
import tempfile

# ------------------------------------------------------------------ constantes

ESTADOS = ["propuesta", "bloqueada", "por_hacer", "en_curso", "revision", "hecha"]

# Transiciones legales: (desde, hacia) → (comando_responsable, autoridad)
# autoridad: "agente" | "humano" | "auto" (normalizar)
TRANSICIONES = {
    ("propuesta", "por_hacer"): ("aprobar", "humano"),
    ("bloqueada", "por_hacer"): ("normalizar", "auto"),
    ("por_hacer", "en_curso"): ("empezar", "agente"),
    ("en_curso", "revision"): ("terminar", "agente"),
    ("en_curso", "por_hacer"): ("pausar", "agente"),
    ("revision", "hecha"): ("hecha", "humano"),
}

ESTADOS_TRABAJABLES = ("por_hacer",)          # donde puede estar el agente
ESTADOS_HUMANOS = ("propuesta", "revision")   # solo el humano mueve desde aquí

LOCK_STALE_SEGUNDOS = 300  # un lock con más de 5 min es un colgado


class ErrorArgos(Exception):
    """Rechazo del CLI: el mensaje explica POR QUÉ (un rechazo es una respuesta)."""


class ArgosOcupado(ErrorArgos):
    """Lock activo de otro escritor."""


# ------------------------------------------------------------------ tarea

def _tarea_nueva(grupo, titulo, descripcion="", estado="propuesta", depende_de=None):
    return {
        "id": "",
        "grupo": grupo,
        "titulo": titulo,
        "descripcion": descripcion,
        "estado": estado,
        "depende_de": list(depende_de or []),
        "notas": "",
    }


# ------------------------------------------------------------------ argos

class Argos:
    def __init__(self, ruta: str):
        self.ruta = os.path.abspath(ruta)
        self.datos = {"proyecto": "", "version": 1, "tareas": []}

    # ---------- carga / guardado

    def cargar(self) -> None:
        if not os.path.exists(self.ruta):
            raise ErrorArgos(
                f"No existe {self.ruta}. Ejecuta: argos init")
        try:
            with open(self.ruta, encoding="utf-8") as f:
                datos = json.load(f)
        except json.JSONDecodeError as e:
            raise ErrorArgos(
                f"argos.json corrupto (JSON inválido): {e}. "
                "Repararlo a mano es tarea del humano.")
        if not isinstance(datos, dict) or not isinstance(datos.get("tareas"), list):
            raise ErrorArgos(
                "argos.json no tiene el esquema esperado "
                "(falta 'tareas' como lista). El humano debe revisarlo.")
        self.datos = datos
        for i, t in enumerate(self.datos["tareas"]):
            if not isinstance(t, dict):
                raise ErrorArgos(
                    f"Tarea #{i} no es un objeto JSON. El humano debe revisarla.")
            t.setdefault("id", "")
            t.setdefault("grupo", "General")
            t.setdefault("titulo", "")
            t.setdefault("descripcion", "")
            t.setdefault("estado", "propuesta")
            t.setdefault("depende_de", [])
            t.setdefault("notas", "")
            if t["estado"] not in ESTADOS:
                raise ErrorArgos(
                    f"Tarea {t['id'] or t['titulo']}: estado desconocido "
                    f"'{t['estado']}'. Estados válidos: {', '.join(ESTADOS)}.")

    def guardar(self) -> None:
        """Escritura atómica: tmp en el mismo directorio + os.replace."""
        carpeta = os.path.dirname(self.ruta) or "."
        fd, tmp = tempfile.mkstemp(prefix=".argos-", suffix=".tmp", dir=carpeta)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self.datos, f, ensure_ascii=False, indent=2)
                f.write("\n")
            os.replace(tmp, self.ruta)
        except BaseException:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise

    # ---------- acceso

    @property
    def tareas(self):
        return self.datos["tareas"]

    def por_id(self, tid: str):
        for t in self.tareas:
            if t["id"] == tid:
                return t
        return None

    def _exigir_id(self, tid: str):
        t = self.por_id(tid)
        if t is None:
            raise ErrorArgos(
                f"La tarjeta '{tid}' no existe. IDs reales los lista "
                "`argos lista` o `argos preparadas`; nunca te los inventes.")
        return t

    # ---------- IDs

    @staticmethod
    def _prefijo_grupo(grupo: str) -> str:
        letras = re.sub(r"[^A-Za-zÁÉÍÓÚÑáéíóúñ]", "", grupo).upper()
        return (letras[:3] or "TAR")

    def asignar_ids(self) -> list:
        """Asigna ID a toda tarjeta sin id. Determinista y auto-incremental."""
        asignadas = []
        prefijos_usados: dict[str, str] = {}  # grupo -> prefijo
        for t in self.tareas:
            if t["id"]:
                g = prefijos_usados.get(t["grupo"])
                if g is None:
                    prefijos_usados[t["grupo"]] = t["id"].rstrip("0123456789")
        for t in self.tareas:
            if t["id"]:
                continue
            grupo = t["grupo"] or "General"
            prefijo = prefijos_usados.get(grupo)
            if prefijo is None:
                prefijo = self._prefijo_grupo(grupo)
                # evitar colisión con otro grupo
                ocupados = {p for g, p in prefijos_usados.items() if g != grupo}
                ocupados |= {tt["id"].rstrip("0123456789")
                             for tt in self.tareas if tt["id"]}
                base, n = prefijo, 0
                while prefijo in ocupados:
                    n += 1
                    prefijo = base[:2] + str(n)
                prefijos_usados[grupo] = prefijo
            numero = 1 + max(
                (int(tt["id"][len(prefijo):]) for tt in self.tareas
                 if tt["id"] and tt["id"].startswith(prefijo)
                 and tt["id"][len(prefijo):].isdigit()),
                default=0)
            t["id"] = f"{prefijo}{numero:02d}"
            asignadas.append(t["id"])
        return asignadas

    # ---------- dependencias

    def faltan_dependencias(self, t) -> list:
        """IDs de dependencias que aún no están hecha."""
        return [d for d in t["depende_de"]
                if not (dep := self.por_id(d)) or dep["estado"] != "hecha"]

    def validar_dependencias(self) -> list:
        """Anomalías: dependencias inexistentes o auto-referencia."""
        anomalias = []
        for t in self.tareas:
            if not t["id"]:
                continue
            for d in t["depende_de"]:
                if d == t["id"]:
                    anomalias.append(f"{t['id']} depende de sí misma")
                elif self.por_id(d) is None:
                    anomalias.append(
                        f"{t['id']} depende de {d}, que no existe")
        return anomalias

    def _crearia_ciclo(self, bloquea: str, bloqueada: str) -> bool:
        """True si añadir «bloqueada depende de bloquea» cierra un ciclo.

        Recorre desde el nuevo bloqueador siguiendo depende_de: si llega a la
        bloqueada, la flecha nueva cierra el círculo.
        """
        alcance, pila = set(), [bloquea]
        while pila:
            actual = pila.pop()
            if actual == bloqueada:
                return True
            if actual in alcance:
                continue
            alcance.add(actual)
            t = self.por_id(actual)
            if t:
                pila.extend(t["depende_de"])
        return False

    # ---------- normalizar

    def normalizar(self) -> dict:
        """Asigna IDs y recalcula bloqueada<->por_hacer según dependencias.

        Nunca toca propuesta, en_curso, revision ni hecha.
        """
        ids_asignados = self.asignar_ids()
        # validar referencias tras asignar
        for t in self.tareas:
            t["depende_de"] = [d for d in t["depende_de"] if self.por_id(d)]
        cambios = []
        for t in self.tareas:
            if t["estado"] not in ("bloqueada", "por_hacer"):
                continue
            faltan = self.faltan_dependencias(t)
            nuevo = "bloqueada" if faltan else "por_hacer"
            if nuevo != t["estado"]:
                cambios.append(f"{t['id']}: {t['estado']} → {nuevo}")
                t["estado"] = nuevo
        return {"ids_asignados": ids_asignados, "cambios": cambios}

    # ---------- transiciones

    def transicion(self, tid: str, hacia: str, comando: str, quien: str) -> dict:
        t = self._exigir_id(tid)
        desde = t["estado"]
        legal = TRANSICIONES.get((desde, hacia))
        if legal is None:
            raise ErrorArgos(
                f"Transición {desde} → {hacia} PROHIBIDA. "
                f"Ciclo legal de '{tid}': {self._ciclo_de(desde)}")
        comando_legal, quien_legal = legal
        if comando != comando_legal:
            raise ErrorArgos(
                f"'{tid}' está en '{desde}': la transición a '{hacia}' "
                f"corresponde a `{comando_legal}`, no a `{comando}`.")
        if quien == "agente" and quien_legal != "agente":
            raise ErrorArgos(
                f"`{comando}` no es un comando de agente para '{tid}' "
                f"(en '{desde}'). Esa autoridad es del HUMANO. No reintentes.")
        if desde == "por_hacer" and hacia == "en_curso":
            faltan = self.faltan_dependencias(t)
            if faltan:
                raise ErrorArgos(
                    f"'{tid}' está BLOQUEADA por dependencias sin hacer: "
                    f"{', '.join(faltan)}. Ejecuta `argos bloqueadas` para verlo.")
        t["estado"] = hacia
        return {"id": tid, "desde": desde, "hacia": hacia}

    @staticmethod
    def _ciclo_de(estado: str) -> str:
        caminos = {
            "propuesta": "propuesta --(aprobar, humano)--> por_hacer",
            "por_hacer": "por_hacer --(empezar)--> en_curso --(terminar)--> revision --(hecha, humano)--> hecha",
            "en_curso": "en_curso --(terminar)--> revision  |  --(pausar)--> por_hacer",
            "revision": "revision --(hecha, SOLO humano)--> hecha",
            "hecha": "hecha es terminal: no se mueve",
            "bloqueada": "bloqueada --(normalizar, cuando todas las dependencias estén hecha)--> por_hacer",
        }
        return caminos.get(estado, estado)

    # ---------- Helpers de dominio

    def preparadas(self) -> list:
        return [t for t in self.tareas
                if t["estado"] == "por_hacer" and not self.faltan_dependencias(t)]

    def bloqueadas(self) -> list:
        return [(t, self.faltan_dependencias(t))
                for t in self.tareas if t["estado"] == "bloqueada"]

    def anomalias(self) -> list:
        anomalias = self.validar_dependencias()
        sin_id = [t for t in self.tareas if not t["id"]]
        if sin_id:
            anomalias.append(
                f"{len(sin_id)} tarjeta(s) sin ID. Ejecuta: argos normalizar")
        en_curso = [t for t in self.tareas if t["estado"] == "en_curso"]
        if len(en_curso) > 1:
            anomalias.append(
                "Más de una tarjeta en_curso "
                f"({', '.join(t['id'] for t in en_curso)}): regla 'una a la vez'.")
        return anomalias

    # ---------- altas / bajas

    def proponer(self, grupo, titulo, descripcion, depende_de) -> dict:
        for d in depende_de:
            self._exigir_id(d)
        t = _tarea_nueva(grupo, titulo, descripcion, "propuesta", depende_de)
        self.tareas.append(t)
        ids = self.asignar_ids()
        return {"id": t["id"], "asignadas": ids}

    def aprobar(self, tid) -> dict:
        return self.transicion(tid, "por_hacer", "aprobar", "humano")

    def marcar_hecha(self, tid) -> dict:
        return self.transicion(tid, "hecha", "hecha", "humano")

    def rechazar(self, tid) -> dict:
        t = self._exigir_id(tid)
        if t["estado"] != "propuesta":
            raise ErrorArgos(
                f"Solo se rechazan tarjetas en 'propuesta' (rechazar = borrar). "
                f"'{tid}' está en '{t['estado']}'.")
        self.tareas.remove(t)
        # limpiar referencias colgantes
        for otra in self.tareas:
            otra["depende_de"] = [d for d in otra["depende_de"] if d != tid]
        return {"id": tid, "borrada": True}

    def anadir_dependencia(self, bloquea, bloqueada) -> dict:
        if bloquea == bloqueada:
            raise ErrorArgos("Una tarjeta no puede bloquearse a sí misma.")
        self._exigir_id(bloquea)
        self._exigir_id(bloqueada)
        b = self.por_id(bloqueada)
        if bloquea in b["depende_de"]:
            raise ErrorArgos(
                f"{bloqueada} ya depende de {bloquea}. Nada que hacer.")
        if self._crearia_ciclo(bloquea, bloqueada):
            raise ErrorArgos(
                f"RECHAZADO: {bloquea} → {bloqueada} crearía un ciclo de "
                "dependencias. Los ciclos nunca se permiten.")
        b["depende_de"].append(bloquea)
        return {"bloquea": bloquea, "bloqueada": bloqueada}

    def editar_notas(self, tid, texto) -> dict:
        t = self._exigir_id(tid)
        if t["estado"] != "en_curso":
            raise ErrorArgos(
                f"Solo se edita una tarjeta en_curso; '{tid}' está en "
                f"'{t['estado']}'. Si es trabajo nuevo, propónlo con `proponer`.")
        sello = t["notas"] + ("\n" if t["notas"] else "")
        t["notas"] = f"{sello}{texto}"
        return {"id": tid, "notas": t["notas"]}
