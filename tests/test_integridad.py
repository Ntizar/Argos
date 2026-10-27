"""Integridad del argos.json y ciclo de vida end-to-end."""
import json
import os

from conftest import json_out, run


# ---------- fichero corrupto / esquema roto

def test_json_corrupto_rechazado_con_mensaje(tablero):
    with open(tablero, "w", encoding="utf-8") as f:
        f.write("{esto no es json")
    code, _, err = run(["--argos", tablero, "estado"])
    assert code == 1 and "corrupto" in err and "humano" in err


def test_esquema_sin_tareas_rechazado(tablero):
    with open(tablero, "w", encoding="utf-8") as f:
        json.dump({"proyecto": "x"}, f)
    code, _, err = run(["--argos", tablero, "estado"])
    assert code == 1 and "esquema" in err


def test_estado_desconocido_rechazado(tablero):
    with open(tablero, encoding="utf-8") as f:
        datos = json.load(f)
    datos["tareas"].append({"titulo": "X", "estado": "archivada"})
    with open(tablero, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False)
    code, _, err = run(["--argos", tablero, "estado"])
    assert code == 1 and "estado desconocido" in err


def test_tarea_no_objeto_rechazada(tablero):
    with open(tablero, encoding="utf-8") as f:
        datos = json.load(f)
    datos["tareas"].append("texto suelto")
    with open(tablero, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False)
    code, _, err = run(["--argos", tablero, "estado"])
    assert code == 1 and "no es un objeto" in err


def test_argos_inexistente_sugiere_init(tablero):
    code, _, err = run(["--argos", tablero + ".no-existe", "estado"])
    assert code == 1 and "argos init" in err


def test_campos_por_defecto_reparados_al_cargar(tablero):
    # el humano guardó una tarea mínima a mano: el CLI repara, no rompe
    with open(tablero, encoding="utf-8") as f:
        datos = json.load(f)
    datos["tareas"].append({"titulo": "mínima"})
    with open(tablero, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False)
    code, _, _ = run(["--argos", tablero, "normalizar"])
    assert code == 0
    with open(tablero, encoding="utf-8") as f:
        t = json.load(f)["tareas"][0]
    assert t["id"] == "GEN01" and t["estado"] == "propuesta"
    assert t["depende_de"] == [] and t["notas"] == ""


def test_escritura_atomica_no_deja_tmp(tablero):
    run(["--argos", tablero, "normalizar"])
    sueltos = [f for f in os.listdir(os.path.dirname(tablero))
               if f.startswith(".tablero-")]
    assert sueltos == []


def test_init_no_sobreescribe(tablero):
    code, _, err = run(["--argos", tablero, "init", "otro"])
    assert code == 1 and "No se sobreescribe" in err


def test_init_salida_json(tmp_path):
    ruta = str(tmp_path / "t.json")
    datos = json_out(["--argos", ruta, "init", "proy", "--sin-agents"])
    assert ruta in datos["creados"]


def test_init_no_pisa_agents_existente(tmp_path):
    ruta = str(tmp_path / "t.json")
    reglas = tmp_path / "AGENTS.md"
    reglas.write_text("mis reglas", encoding="utf-8")
    run(["--argos", ruta, "init", "proy"])
    assert reglas.read_text(encoding="utf-8") == "mis reglas"


# ---------- ciclo de vida end-to-end completo (simulación de sesión)

def test_sesion_completa_de_agente(tablero):
    # 1. el agente propone dos tareas, una con dependencia
    assert run(["--argos", tablero, "proponer", "API", "Endpoint",
                "GET /datos"])[0] == 0
    assert run(["--argos", tablero, "proponer", "API", "Tests", "pytest",
                "--depende-de", "API01"])[0] == 0
    # 2. propone trabajo nuevo descubierto en curso
    # 3. el humano aprueba la primera; la segunda queda bloqueada
    assert run(["--argos", tablero, "aprobar", "API01"])[0] == 0
    assert run(["--argos", tablero, "aprobar", "API02"])[0] == 0
    # 4. el agente lee preparadas y empieza
    prep = json_out(["--argos", tablero, "preparadas"])
    assert [t["id"] for t in prep] == ["API01"]
    assert run(["--argos", tablero, "empezar", "API01"])[0] == 0
    # 5. anota avances
    assert run(["--argos", tablero, "editar", "API01",
                "endpoint listo, falta validar"])[0] == 0
    # 6. propone trabajo nuevo descubierto
    assert run(["--argos", tablero, "proponer", "API", "Caché",
                "redis", "--depende-de", "API01"])[0] == 0
    # 7. termina y entrega a revisión
    assert run(["--argos", tablero, "terminar", "API01"])[0] == 0
    estado = json_out(["--argos", tablero, "estado"])
    assert estado["conteo"]["revision"] == 1
    assert estado["conteo"]["propuesta"] == 1  # solo la caché (API03)
    # 8. el humano verifica y marca hecha → se desbloquean los tests
    assert run(["--argos", tablero, "hecha", "API01"])[0] == 0
    assert run(["--argos", tablero, "normalizar"])[0] == 0
    prep = json_out(["--argos", tablero, "preparadas"])
    assert [t["id"] for t in prep] == ["API02"]
    # 9. el humano rechaza la propuesta de caché → no queda ninguna propuesta
    assert run(["--argos", tablero, "rechazar", "API03"])[0] == 0
    estado = json_out(["--argos", tablero, "estado"])
    assert estado["conteo"]["propuesta"] == 0


def test_sync_en_carpeta_sin_git_rechazado(tablero):
    code, _, err = run(["--argos", tablero, "sync"])
    assert code == 1 and "no es un repo git" in err


def test_sync_en_repo_git_sin_remote_falla_limpio(tmp_path):
    import subprocess
    ruta = str(tmp_path / "argos.json")
    run(["--argos", ruta, "init", "p", "--sin-agents"])
    subprocess.run(["git", "init", "-q"], cwd=str(tmp_path), check=True)
    code, _, err = run(["--argos", ruta, "sync"])
    assert code == 1  # sin remote: falla sin colgarse y con mensaje
    assert "No fuerces el push" in err or "FALLO" in err
