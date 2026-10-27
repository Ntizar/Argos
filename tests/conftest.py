"""Fixtures y helper para lanzar el CLI en proceso (rápido y con códigos de salida)."""
import contextlib
import io
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from argos import cli  # noqa: E402


def run(argv, cwd=None):
    """Ejecuta el CLI y devuelve (code, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    viejo = os.getcwd()
    if cwd:
        os.chdir(cwd)
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(argv)
    finally:
        if cwd:
            os.chdir(viejo)
    return code, out.getvalue(), err.getvalue()


def json_out(argv, cwd=None):
    code, out, err = run(argv + ["--json"], cwd=cwd)
    assert code == 0, f"esperaba 0, fue {code}: {out}{err}"
    return json.loads(out)


@pytest.fixture
def tablero(tmp_path):
    """Un proyecto limpio con argos.json creado vía `argos init`."""
    ruta = str(tmp_path / "argos.json")
    code, out, err = run(["--argos", ruta, "init", "proyecto-test"])
    assert code == 0, err
    return ruta


@pytest.fixture
def tablero_creado(tablero):
    """Argos con tres tarjetas aprobadas: DES01, DES02 (depende de DES01), INV01."""
    run(["--argos", tablero, "proponer", "Desarrollo", "Login", "POST /login"])
    run(["--argos", tablero, "proponer", "Desarrollo", "Logout", "POST /logout",
         "--depende-de", "DES01"])
    run(["--argos", tablero, "proponer", "Investigación", "JWT", "elegir librería"])
    run(["--argos", tablero, "aprobar", "DES01"])
    run(["--argos", tablero, "aprobar", "DES02"])
    run(["--argos", tablero, "aprobar", "INV01"])
    return tablero
