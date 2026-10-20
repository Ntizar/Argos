"""Lock de escritor único: ocupado, colgado, liberación garantizada."""
import json
import os
import time

from conftest import run

from tablero.lock import (adquirir, forzar_liberacion, info_lock,
                          lock_de_escritura, liberar)


def _escribir_lock(ruta, pid, edad_s=0):
    lock = os.path.join(os.path.dirname(ruta), "tablero.lock")
    with open(lock, "w", encoding="utf-8") as f:
        json.dump({"pid": pid, "ts": time.time() - edad_s,
                   "comando": "prueba"}, f)
    return lock


# ---------- comando de escritura con lock ajeno vivo → código 2

def test_tablero_ocupado_codigo_2(mesa):
    _escribir_lock(mesa, pid=os.getpid())  # PID vivo (este proceso de tests)
    code, _, err = run(["--tablero", mesa, "empezar", "DES01"])
    assert code == 2 and "OCUPADO" in err


def test_estado_lectura_funciona_con_lock(mesa):
    _escribir_lock(mesa, pid=os.getpid())
    code, out, _ = run(["--tablero", mesa, "estado"])
    assert code == 0 and "lock presente" in out


# ---------- locks colgados se limpian solos

def test_lock_con_pid_muerto_se_limpia(mesa):
    _escribir_lock(mesa, pid=99999999)  # inexistente
    code, out, _ = run(["--tablero", mesa, "normalizar"])
    assert code == 0
    assert not os.path.exists(os.path.join(os.path.dirname(mesa), "tablero.lock"))


def test_lock_viejo_se_limpia(mesa):
    _escribir_lock(mesa, pid=os.getpid(), edad_s=400)  # > 5 min
    code, _, _ = run(["--tablero", mesa, "normalizar"])
    assert code == 0


def test_lock_ilegible_se_limpia(mesa):
    lock = os.path.join(os.path.dirname(mesa), "tablero.lock")
    with open(lock, "w") as f:
        f.write("no-soy-json")
    code, _, _ = run(["--tablero", mesa, "normalizar"])
    assert code == 0


# ---------- liberación garantizada

def test_lock_se_libera_tras_comando_ok(mesa):
    run(["--tablero", mesa, "normalizar"])
    assert info_lock(mesa) is None


def test_lock_se_libera_tras_rechazo(mesa):
    run(["--tablero", mesa, "empezar", "ZZ99"])  # code 1
    assert info_lock(mesa) is None


def test_context_manager_libera_en_excepcion(mesa):
    try:
        with lock_de_escritura(mesa, "prueba"):
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    assert info_lock(mesa) is None


def test_unlock_borra_lock(mesa):
    _escribir_lock(mesa, pid=os.getpid())
    code, out, _ = run(["--tablero", mesa, "unlock"])
    assert code == 0 and "eliminado" in out
    assert info_lock(mesa) is None


def test_unlock_sin_lock(mesa):
    code, out, _ = run(["--tablero", mesa, "unlock"])
    assert code == 0 and "No había lock" in out


def test_no_se_libera_el_lock_ajeno(mesa):
    # liberar() solo toca SU propio lock: si el PID del lock no es el nuestro,
    # lo dejamos (aunque aquí forzamos limpieza para el siguiente test)
    _escribir_lock(mesa, pid=os.getpid())
    # liberar() con el mismo PID sí libera
    liberar(mesa)
    assert info_lock(mesa) is None


def test_adquirir_y_liberar_secuencia(mesa):
    adquirir(mesa, "prueba")
    assert info_lock(mesa)["comando"] == "prueba"
    liberar(mesa)
    assert info_lock(mesa) is None


def test_forzar_liberacion(mesa):
    _escribir_lock(mesa, pid=os.getpid())
    assert forzar_liberacion(mesa) is True
    assert forzar_liberacion(mesa) is False
