"""Dependencias: bloqueo, desbloqueo automático, ciclos y referencias."""
from conftest import json_out, run


def test_aprobar_tarjeta_con_dependencia_la_bloquea(tablero):
    run(["--argos", tablero, "proponer", "Dev", "A", "primera"])
    run(["--argos", tablero, "proponer", "Dev", "B", "segunda",
         "--depende-de", "DEV01"])
    run(["--argos", tablero, "aprobar", "DEV01"])
    code, out, _ = run(["--argos", tablero, "aprobar", "DEV02"])
    assert code == 0
    _, out, _ = run(["--argos", tablero, "estado"])
    assert "bloqueada: 1" in out


def test_hecha_desbloquea_con_normalizar(tablero):
    run(["--argos", tablero, "proponer", "Dev", "A", "primera"])
    run(["--argos", tablero, "proponer", "Dev", "B", "segunda",
         "--depende-de", "DEV01"])
    run(["--argos", tablero, "aprobar", "DEV01"])
    run(["--argos", tablero, "aprobar", "DEV02"])
    # A se completa
    run(["--argos", tablero, "empezar", "DEV01"])
    run(["--argos", tablero, "terminar", "DEV01"])
    run(["--argos", tablero, "hecha", "DEV01"])
    # normalizar es idempotente: `hecha` ya desbloqueó a B automáticamente
    code, out, _ = run(["--argos", tablero, "normalizar"])
    assert code == 0
    _, out, _ = run(["--argos", tablero, "preparadas"])
    assert "DEV02" in out


def test_empezar_normaliza_antes(tablero):
    # el desbloqueo también ocurre al ejecutar empezar (no hace falta
    # que el agente recuerde normalizar)
    run(["--argos", tablero, "proponer", "Dev", "A", "primera"])
    run(["--argos", tablero, "proponer", "Dev", "B", "segunda",
         "--depende-de", "DEV01"])
    run(["--argos", tablero, "aprobar", "DEV01"])
    run(["--argos", tablero, "aprobar", "DEV02"])
    run(["--argos", tablero, "empezar", "DEV01"])
    run(["--argos", tablero, "terminar", "DEV01"])
    run(["--argos", tablero, "hecha", "DEV01"])
    code, out, _ = run(["--argos", tablero, "empezar", "DEV02"])
    assert code == 0


def test_ciclo_rechazado(tablero):
    run(["--argos", tablero, "proponer", "Dev", "A", ""])
    run(["--argos", tablero, "proponer", "Dev", "B", ""])
    run(["--argos", tablero, "aprobar", "DEV01"])
    run(["--argos", tablero, "aprobar", "DEV02"])
    assert run(["--argos", tablero, "dep", "DEV01", "DEV02"])[0] == 0
    code, _, err = run(["--argos", tablero, "dep", "DEV02", "DEV01"])
    assert code == 1 and "ciclo" in err.lower()


def test_auto_dependencia_rechazada(tablero):
    run(["--argos", tablero, "proponer", "Dev", "A", ""])
    code, _, err = run(["--argos", tablero, "dep", "DEV01", "DEV01"])
    assert code == 1


def test_dep_sobre_inexistente_rechazado(tablero):
    run(["--argos", tablero, "proponer", "Dev", "A", ""])
    code, _, err = run(["--argos", tablero, "dep", "ZZ99", "DEV01"])
    assert code == 1 and "no existe" in err


def test_dep_duplicada_rechazada(tablero):
    run(["--argos", tablero, "proponer", "Dev", "A", ""])
    run(["--argos", tablero, "proponer", "Dev", "B", ""])
    run(["--argos", tablero, "dep", "DEV01", "DEV02"])
    code, _, err = run(["--argos", tablero, "dep", "DEV01", "DEV02"])
    assert code == 1 and "Nada que hacer" in err


def test_proponer_con_dependencia_inexistente_rechazado(tablero):
    # proponer valida las dependencias en el momento: no se puede depender
    # de un ID que no existe (evita anomalías de entrada)
    code, _, err = run(["--argos", tablero, "proponer", "Dev", "A", "",
                        "--depende-de", "ZZ99"])
    assert code == 1 and "no existe" in err


def test_normalizar_limpia_referencias_colgantes(tablero):
    run(["--argos", tablero, "proponer", "Dev", "A", ""])
    run(["--argos", tablero, "proponer", "Dev", "B", "", "--depende-de", "DEV01"])
    run(["--argos", tablero, "rechazar", "DEV01"])
    run(["--argos", tablero, "normalizar"])
    datos = json_out(["--argos", tablero, "lista"])
    assert datos[0]["depende_de"] == []


def test_bloqueadas_muestra_quien_bloquea(tablero):
    run(["--argos", tablero, "proponer", "Dev", "A", ""])
    run(["--argos", tablero, "proponer", "Dev", "B", "", "--depende-de", "DEV01"])
    run(["--argos", tablero, "aprobar", "DEV02"])
    code, out, _ = run(["--argos", tablero, "bloqueadas"])
    assert code == 0 and "DEV01" in out and "espera a" in out


def test_preparadas_excluye_bloqueadas(tablero_creado):
    _, out, _ = run(["--argos", tablero_creado, "preparadas"])
    assert "DES02" not in out and "DES01" in out and "INV01" in out


def test_cadena_larga_de_dependencias(tablero):
    # A → B → C: C no se libera hasta que B esté hecha, y B hasta que A
    run(["--argos", tablero, "proponer", "Dev", "A", ""])
    run(["--argos", tablero, "proponer", "Dev", "B", "", "--depende-de", "DEV01"])
    run(["--argos", tablero, "proponer", "Dev", "C", "", "--depende-de", "DEV02"])
    for tid in ("DEV01", "DEV02", "DEV03"):
        run(["--argos", tablero, "aprobar", tid])
    _, out, _ = run(["--argos", tablero, "estado"])
    assert "bloqueada: 2" in out
    for paso in ("DEV01", "DEV02"):
        run(["--argos", tablero, "empezar", paso])
        run(["--argos", tablero, "terminar", paso])
        run(["--argos", tablero, "hecha", paso])
    _, out, _ = run(["--argos", tablero, "preparadas"])
    assert "DEV03" in out
