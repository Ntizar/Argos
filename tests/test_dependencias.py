"""Dependencias: bloqueo, desbloqueo automático, ciclos y referencias."""
from conftest import json_out, run


def test_aprobar_tarjeta_con_dependencia_la_bloquea(mesa):
    run(["--tablero", mesa, "proponer", "Dev", "A", "primera"])
    run(["--tablero", mesa, "proponer", "Dev", "B", "segunda",
         "--depende-de", "DEV01"])
    run(["--tablero", mesa, "aprobar", "DEV01"])
    code, out, _ = run(["--tablero", mesa, "aprobar", "DEV02"])
    assert code == 0
    _, out, _ = run(["--tablero", mesa, "estado"])
    assert "bloqueada: 1" in out


def test_hecha_desbloquea_con_normalizar(mesa):
    run(["--tablero", mesa, "proponer", "Dev", "A", "primera"])
    run(["--tablero", mesa, "proponer", "Dev", "B", "segunda",
         "--depende-de", "DEV01"])
    run(["--tablero", mesa, "aprobar", "DEV01"])
    run(["--tablero", mesa, "aprobar", "DEV02"])
    # A se completa
    run(["--tablero", mesa, "empezar", "DEV01"])
    run(["--tablero", mesa, "terminar", "DEV01"])
    run(["--tablero", mesa, "hecha", "DEV01"])
    # normalizar es idempotente: `hecha` ya desbloqueó a B automáticamente
    code, out, _ = run(["--tablero", mesa, "normalizar"])
    assert code == 0
    _, out, _ = run(["--tablero", mesa, "preparadas"])
    assert "DEV02" in out


def test_empezar_normaliza_antes(mesa):
    # el desbloqueo también ocurre al ejecutar empezar (no hace falta
    # que el agente recuerde normalizar)
    run(["--tablero", mesa, "proponer", "Dev", "A", "primera"])
    run(["--tablero", mesa, "proponer", "Dev", "B", "segunda",
         "--depende-de", "DEV01"])
    run(["--tablero", mesa, "aprobar", "DEV01"])
    run(["--tablero", mesa, "aprobar", "DEV02"])
    run(["--tablero", mesa, "empezar", "DEV01"])
    run(["--tablero", mesa, "terminar", "DEV01"])
    run(["--tablero", mesa, "hecha", "DEV01"])
    code, out, _ = run(["--tablero", mesa, "empezar", "DEV02"])
    assert code == 0


def test_ciclo_rechazado(mesa):
    run(["--tablero", mesa, "proponer", "Dev", "A", ""])
    run(["--tablero", mesa, "proponer", "Dev", "B", ""])
    run(["--tablero", mesa, "aprobar", "DEV01"])
    run(["--tablero", mesa, "aprobar", "DEV02"])
    assert run(["--tablero", mesa, "dep", "DEV01", "DEV02"])[0] == 0
    code, _, err = run(["--tablero", mesa, "dep", "DEV02", "DEV01"])
    assert code == 1 and "ciclo" in err.lower()


def test_auto_dependencia_rechazada(mesa):
    run(["--tablero", mesa, "proponer", "Dev", "A", ""])
    code, _, err = run(["--tablero", mesa, "dep", "DEV01", "DEV01"])
    assert code == 1


def test_dep_sobre_inexistente_rechazado(mesa):
    run(["--tablero", mesa, "proponer", "Dev", "A", ""])
    code, _, err = run(["--tablero", mesa, "dep", "ZZ99", "DEV01"])
    assert code == 1 and "no existe" in err


def test_dep_duplicada_rechazada(mesa):
    run(["--tablero", mesa, "proponer", "Dev", "A", ""])
    run(["--tablero", mesa, "proponer", "Dev", "B", ""])
    run(["--tablero", mesa, "dep", "DEV01", "DEV02"])
    code, _, err = run(["--tablero", mesa, "dep", "DEV01", "DEV02"])
    assert code == 1 and "Nada que hacer" in err


def test_proponer_con_dependencia_inexistente_rechazado(mesa):
    # proponer valida las dependencias en el momento: no se puede depender
    # de un ID que no existe (evita anomalías de entrada)
    code, _, err = run(["--tablero", mesa, "proponer", "Dev", "A", "",
                        "--depende-de", "ZZ99"])
    assert code == 1 and "no existe" in err


def test_normalizar_limpia_referencias_colgantes(mesa):
    run(["--tablero", mesa, "proponer", "Dev", "A", ""])
    run(["--tablero", mesa, "proponer", "Dev", "B", "", "--depende-de", "DEV01"])
    run(["--tablero", mesa, "rechazar", "DEV01"])
    run(["--tablero", mesa, "normalizar"])
    datos = json_out(["--tablero", mesa, "lista"])
    assert datos[0]["depende_de"] == []


def test_bloqueadas_muestra_quien_bloquea(mesa):
    run(["--tablero", mesa, "proponer", "Dev", "A", ""])
    run(["--tablero", mesa, "proponer", "Dev", "B", "", "--depende-de", "DEV01"])
    run(["--tablero", mesa, "aprobar", "DEV02"])
    code, out, _ = run(["--tablero", mesa, "bloqueadas"])
    assert code == 0 and "DEV01" in out and "espera a" in out


def test_preparadas_excluye_bloqueadas(tablero_creado):
    _, out, _ = run(["--tablero", tablero_creado, "preparadas"])
    assert "DES02" not in out and "DES01" in out and "INV01" in out


def test_cadena_larga_de_dependencias(mesa):
    # A → B → C: C no se libera hasta que B esté hecha, y B hasta que A
    run(["--tablero", mesa, "proponer", "Dev", "A", ""])
    run(["--tablero", mesa, "proponer", "Dev", "B", "", "--depende-de", "DEV01"])
    run(["--tablero", mesa, "proponer", "Dev", "C", "", "--depende-de", "DEV02"])
    for tid in ("DEV01", "DEV02", "DEV03"):
        run(["--tablero", mesa, "aprobar", tid])
    _, out, _ = run(["--tablero", mesa, "estado"])
    assert "bloqueada: 2" in out
    for paso in ("DEV01", "DEV02"):
        run(["--tablero", mesa, "empezar", paso])
        run(["--tablero", mesa, "terminar", paso])
        run(["--tablero", mesa, "hecha", paso])
    _, out, _ = run(["--tablero", mesa, "preparadas"])
    assert "DEV03" in out
