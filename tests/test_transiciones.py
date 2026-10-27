"""Transiciones de estado: legales, prohibidas y quién manda."""
from conftest import run


# ---------- ciclo feliz completo

def test_ciclo_feliz_completo(tablero):
    # proponer → aprobar → empezar → terminar → hecha
    assert run(["--argos", tablero, "proponer", "Dev", "Tarea A", "desc"])[0] == 0
    assert run(["--argos", tablero, "aprobar", "DEV01"])[0] == 0
    code, out, _ = run(["--argos", tablero, "empezar", "DEV01"])
    assert code == 0 and "por_hacer → en_curso" in out
    code, out, _ = run(["--argos", tablero, "terminar", "DEV01"])
    assert code == 0 and "en_curso → revision" in out
    assert "acaba aquí" in out  # recordatorio: el trabajo acaba en revision
    code, out, _ = run(["--argos", tablero, "hecha", "DEV01"])
    assert code == 0 and "revision → hecha" in out


def test_pausar_devuelve_a_por_hacer(tablero_creado):
    run(["--argos", tablero_creado, "empezar", "DES01"])
    code, out, _ = run(["--argos", tablero_creado, "pausar", "DES01"])
    assert code == 0 and "en_curso → por_hacer" in out


# ---------- prohibidas: empezar

def test_empezar_sobre_propuesta_rechazado(tablero):
    run(["--argos", tablero, "proponer", "Dev", "Tarea", "desc"])
    code, _, err = run(["--argos", tablero, "empezar", "DEV01"])
    assert code == 1 and "PROHIBIDA" in err
    assert "aprobar" in err  # explica el camino legal


def test_empezar_sobre_bloqueada_rechazado(tablero_creado):
    code, _, err = run(["--argos", tablero_creado, "empezar", "DES02"])
    assert code == 1 and "PROHIBIDA" in err
    assert "bloqueada" in err


def test_empezar_sobre_revision_rechazado(tablero_creado):
    run(["--argos", tablero_creado, "empezar", "DES01"])
    run(["--argos", tablero_creado, "terminar", "DES01"])
    code, _, err = run(["--argos", tablero_creado, "empezar", "DES01"])
    assert code == 1 and "PROHIBIDA" in err


def test_empezar_sobre_hecha_rechazado(tablero_creado):
    run(["--argos", tablero_creado, "empezar", "DES01"])
    run(["--argos", tablero_creado, "terminar", "DES01"])
    run(["--argos", tablero_creado, "hecha", "DES01"])
    code, _, err = run(["--argos", tablero_creado, "empezar", "DES01"])
    assert code == 1 and "hecha es terminal" in err


# ---------- prohibidas: terminar y pausar

def test_terminar_sobre_por_hacer_rechazado(tablero_creado):
    code, _, err = run(["--argos", tablero_creado, "terminar", "DES01"])
    assert code == 1 and "PROHIBIDA" in err


def test_terminar_sobre_propuesta_rechazado(tablero):
    run(["--argos", tablero, "proponer", "Dev", "Tarea", "desc"])
    code, _, err = run(["--argos", tablero, "terminar", "DEV01"])
    assert code == 1


def test_pausar_sobre_por_hacer_rechazado(tablero_creado):
    code, _, err = run(["--argos", tablero_creado, "pausar", "DES01"])
    assert code == 1


def test_hecha_directa_desde_por_hacer_rechazado(tablero_creado):
    # atajo prohibido: por_hacer → hecha sin pasar por revision
    code, _, err = run(["--argos", tablero_creado, "hecha", "DES01"])
    assert code == 1 and "PROHIBIDA" in err


def test_aprobar_sobre_en_curso_rechazado(tablero_creado):
    run(["--argos", tablero_creado, "empezar", "DES01"])
    code, _, err = run(["--argos", tablero_creado, "aprobar", "DES01"])
    assert code == 1


# ---------- el agente no tiene autoridad (el CLI lo recuerda)

def test_mensaje_de_transicion_incluye_autoridad(tablero_creado):
    run(["--argos", tablero_creado, "empezar", "DES01"])
    run(["--argos", tablero_creado, "terminar", "DES01"])
    _, out, _ = run(["--argos", tablero_creado, "hecha", "DES01"])
    assert "SOLO humano" in out or "solo humano" in out.lower()


# ---------- edición solo en en_curso

def test_editar_en_por_hacer_rechazado(tablero_creado):
    code, _, err = run(["--argos", tablero_creado, "editar", "DES01", "nota"])
    assert code == 1 and "en_curso" in err


def test_editar_en_curso_ok(tablero_creado):
    run(["--argos", tablero_creado, "empezar", "DES01"])
    code, out, _ = run(["--argos", tablero_creado, "editar",
                        "DES01", "avanzó el endpoint"])
    assert code == 0 and "actualizadas" in out
    code, out, _ = run(["--argos", tablero_creado, "ver", "DES01"])
    assert "avanzó el endpoint" in out


def test_editar_acumula_notas(tablero_creado):
    run(["--argos", tablero_creado, "empezar", "DES01"])
    run(["--argos", tablero_creado, "editar", "DES01", "primera nota"])
    run(["--argos", tablero_creado, "editar", "DES01", "segunda nota"])
    _, out, _ = run(["--argos", tablero_creado, "ver", "DES01"])
    assert "primera nota" in out and "segunda nota" in out


# ---------- una a la vez: el CLI permite, pero avisa en estado

def test_dos_en_curso_genera_anomalia(tablero_creado):
    run(["--argos", tablero_creado, "empezar", "DES01"])
    run(["--argos", tablero_creado, "empezar", "INV01"])
    code, out, _ = run(["--argos", tablero_creado, "estado"])
    assert code == 0 and "una a la vez" in out


# ---------- IDs inexistentes nunca se inventan

def test_id_inexistente_rechazado_con_consejo(tablero):
    code, _, err = run(["--argos", tablero, "empezar", "ZZ99"])
    assert code == 1 and "no existe" in err and "lista" in err


def test_ver_id_inexistente_rechazado(tablero):
    code, _, err = run(["--argos", tablero, "ver", "XX00"])
    assert code == 1
