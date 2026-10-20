"""Lock de escritor único: tablero.lock junto al tablero.json.

- Existe y el PID vive y es reciente → TableroOcupado (código 2 en el CLI).
- PID muerto o lock con más de LOCK_STALE_SEGUNDOS → colgado: se limpia con aviso.
- Cero dependencias: detección de PID por OpenProcess (Windows) u os.kill (POSIX).
"""
from __future__ import annotations

import json
import os
import time

from .modelo import LOCK_STALE_SEGUNDOS, TableroOcupado


def _ruta_lock(ruta_tablero: str) -> str:
    carpeta = os.path.dirname(os.path.abspath(ruta_tablero)) or "."
    return os.path.join(carpeta, "tablero.lock")


def _pid_vivo(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        if os.name == "nt":
            import ctypes
            PROCESO = 0x1000  # PROCESS_QUERY_LIMITED_INFORMATION
            h = ctypes.windll.kernel32.OpenProcess(PROCESO, False, pid)
            if h:
                ctypes.windll.kernel32.CloseHandle(h)
                return True
            return False
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError, PermissionError):
        return False


def _proceso_actual() -> int:
    return os.getpid()


def adquirir(ruta_tablero: str, comando: str = "") -> None:
    ruta = _ruta_lock(ruta_tablero)
    ahora = time.time()
    if os.path.exists(ruta):
        info = {}
        try:
            with open(ruta, encoding="utf-8") as f:
                info = json.load(f)
        except (OSError, json.JSONDecodeError):
            info = {}
        pid = info.get("pid", 0)
        ts = info.get("ts", 0)
        viejo = (ahora - ts) > LOCK_STALE_SEGUNDOS
        if viejo or not _pid_vivo(pid):
            os.unlink(ruta)  # lock colgado: se limpia sin ceremonia
        else:
            raise TableroOcupado(
                f"Tablero ocupado: lock activo del PID {pid} "
                f"(comando: {info.get('comando', '?')}). "
                "No trabajes hasta que termine; si es un colgado "
                "reciente del humano, `tablero unlock`.")
    info = {"pid": _proceso_actual(), "ts": ahora, "comando": comando}
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(info, f)


def liberar(ruta_tablero: str) -> None:
    ruta = _ruta_lock(ruta_tablero)
    try:
        if os.path.exists(ruta):
            with open(ruta, encoding="utf-8") as f:
                info = json.load(f)
            # solo liberamos NUESTRO lock (un lock ajeno no se toca)
            if info.get("pid") == _proceso_actual():
                os.unlink(ruta)
    except (OSError, json.JSONDecodeError):
        pass


def forzar_liberacion(ruta_tablero: str) -> bool:
    ruta = _ruta_lock(ruta_tablero)
    if os.path.exists(ruta):
        os.unlink(ruta)
        return True
    return False


def info_lock(ruta_tablero: str) -> dict | None:
    ruta = _ruta_lock(ruta_tablero)
    if not os.path.exists(ruta):
        return None
    try:
        with open(ruta, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {"pid": 0, "ts": 0, "comando": "ilegible"}


class lock_de_escritura:
    """Context manager: adquirir → yield → liberar siempre (aunque falle)."""

    def __init__(self, ruta_tablero: str, comando: str = ""):
        self.ruta_tablero = ruta_tablero
        self.comando = comando

    def __enter__(self):
        adquirir(self.ruta_tablero, self.comando)
        return self

    def __exit__(self, exc_type, exc, tb):
        liberar(self.ruta_tablero)
        return False
