"""IDs: prefijos por grupo, auto-incremento, colisiones y normalizar."""
import json

from conftest import json_out, run


def _ids(ruta):
    with open(ruta, encoding="utf-8") as f:
        return [t["id"] for t in json.load(f)["tareas"]]


def test_prefijo_por_grupo(tablero_creado):
    ids = _ids(tablero_creado)
    assert "DES01" in ids and "DES02" in ids and "INV01" in ids


def test_auto_incremento(mesa):
    for n in range(12):
        run(["--tablero", mesa, "proponer", "Dev", f"T{n}", ""])
    ids = _ids(mesa)
    assert ids == [f"DEV{i:02d}" for i in range(1, 13)]


def test_colision_de_prefijos_resuelta(mesa):
    run(["--tablero", mesa, "proponer", "Frontend", "A", ""])
    run(["--tablero", mesa, "proponer", "Frontera", "B", ""])
    ids = _ids(mesa)
    assert len(set(ids)) == 2  # sin colisión
    assert any(i.startswith("FRO") for i in ids)
    assert any(i.startswith("FR1") for i in ids)


def test_tres_digitos_cuando_pasa_de_99(mesa):
    for n in range(101):
        run(["--tablero", mesa, "proponer", "Dev", f"T{n}", ""])
    ids = _ids(mesa)
    assert ids[0] == "DEV01" and ids[99] == "DEV100"


def test_normalizar_asigna_ids_faltantes(mesa):
    # el humano escribió tarjetas a mano sin ID (permitido para él)
    with open(mesa, encoding="utf-8") as f:
        datos = json.load(f)
    datos["tareas"] = [
        {"titulo": "A", "grupo": "Desarrollo", "estado": "propuesta"},
        {"titulo": "B", "grupo": "Desarrollo", "estado": "propuesta"},
    ]
    with open(mesa, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False)
    code, out, _ = run(["--tablero", mesa, "normalizar"])
    assert code == 0 and "DES01, DES02" in out
    assert _ids(mesa) == ["DES01", "DES02"]


def test_normalizar_idempotente(tablero_creado):
    _, out1, _ = run(["--tablero", tablero_creado, "normalizar"])
    _, out2, _ = run(["--tablero", tablero_creado, "normalizar"])
    assert "nada que cambiar" in out2


def test_normalizar_no_toca_en_curso_ni_revision(tablero_creado):
    run(["--tablero", tablero_creado, "empezar", "DES01"])
    run(["--tablero", tablero_creado, "terminar", "DES01"])
    run(["--tablero", tablero_creado, "normalizar"])
    from conftest import json_out as jo
    datos = jo(["--tablero", tablero_creado, "lista"])
    estados = {t["id"]: t["estado"] for t in datos}
    assert estados["DES01"] == "revision"
    assert estados["DES02"] == "bloqueada"
    assert estados["INV01"] == "por_hacer"


def test_grupo_sin_letras_da_prefijo_por_defecto(mesa):
    run(["--tablero", mesa, "proponer", "123", "A", ""])
    assert "TAR01" in _ids(mesa)


def test_anomalia_tarjetas_sin_id(mesa):
    with open(mesa, encoding="utf-8") as f:
        datos = json.load(f)
    datos["tareas"].append({"titulo": "X", "grupo": "Dev", "estado": "propuesta"})
    with open(mesa, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False)
    _, out, _ = run(["--tablero", mesa, "estado"])
    assert "sin ID" in out and "normalizar" in out


def test_lista_filtra_por_grupo(tablero_creado):
    _, out, _ = run(["--tablero", tablero_creado, "lista", "investigación"])
    assert "INV01" in out and "DES01" not in out


def test_lista_filtra_por_estado(tablero_creado):
    _, out, _ = run(["--tablero", tablero_creado, "lista", "por_hacer"])
    assert "DES01" in out and "DES02" not in out


def test_json_salida_estructurada(tablero_creado):
    datos = json_out(["--tablero", tablero_creado, "lista"])
    assert isinstance(datos, list) and len(datos) == 3
    assert set(datos[0]) >= {"id", "titulo", "estado", "depende_de"}
