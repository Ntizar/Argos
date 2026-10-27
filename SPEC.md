# Argos — SPEC

> Argos de tareas humano+agente, inspirado en Kanvas (MIT, XMihura). Adaptación propia en castellano, JSON plano y CLI instalable.
> Hecho con ❤️ por David Antizar.

## Visión

Un CLI (`argos`) que da a un humano y a uno o varios agentes IA un tablero de trabajo
compartida: tarjetas con 6 estados, dependencias y bloqueo automático. El agente NUNCA
toca el JSON: todo pasa por el CLI, que valida y rechaza lo prohibido por código.

## Alcance

### Sí hace
- CLI `argos` con 15 comandos (estado, ver, preparadas, bloqueadas, lista, empezar,
  terminar, pausar, editar, proponer, aprobar, hecha, rechazar, dep, normalizar).
- Extras: `init` (crea argos.json + copia plantilla AGENTS.md), `sync` (pull --rebase + push),
  `unlock` (fuerza un lock colgado), `--json` en todos los comandos.
- 6 estados en castellano con transiciones cerradas y validadas.
- Dependencias: tarjeta bloqueada hasta que todas sus dependencias estén `hecha`;
  desbloqueo automático en `normalizar`; rechazo de ciclos.
- IDs asignados por el CLI (prefijo del grupo + número, auto-incremento).
- Lock de escritor único (`argos.lock`) con detección de PID muerto y lock viejo.
- Escritura atómica (tmp + replace) — un JSON nunca queda corrupto.
- Empaquetado instalable: `uv tool install git+https://github.com/Ntizar/Argos`.
- Plantilla AGENTS.md con las reglas del agente (Parte A de las reglas de Argos).

### NO hace (non-goals)
- Sin backend, sin login, sin base de datos (JSON plano y punto).
- Sin visor web en fase 1 (vendrá luego con Aurora).
- Sin borrado general ni edición directa del JSON para el agente.
- Sin multiusuario real: el lock protege la concurrencia, no la identidad.
- La autoridad humano/agente se define en AGENTS.md (prompt); el CLI garantiza la
  estructura, no la identidad de quien teclea. Decisión consciente.

## Comandos

| Comando | Quién | Efecto |
|---|---|---|
| `init [nombre]` | humano | Crea argos.json (+ AGENTS.md si no existe) |
| `estado` | ambos | Resumen: conteos por estado, anomalías |
| `ver <ID>` | ambos | Detalle de tarjeta |
| `preparadas` | agente | por_hacer con dependencias cumplidas |
| `bloqueadas` | ambos | bloqueadas + qué las bloquea |
| `lista [estado\|grupo]` | ambos | Lista filtrada |
| `empezar <ID>` | agente | por_hacer → en_curso |
| `terminar <ID>` | agente | en_curso → revision |
| `pausar <ID>` | agente | en_curso → por_hacer |
| `editar <ID> "texto"` | agente | Añade nota (solo en_curso) |
| `proponer <GRUPO> "T" "D" [--depende-de ID]` | agente | Crea tarjeta en propuesta |
| `aprobar <ID>` | humano | propuesta → por_hacer |
| `hecha <ID>` | humano | revision → hecha |
| `rechazar <ID>` | humano | Borra una propuesta |
| `dep <A> <B>` | humano | A bloquea a B (rechaza ciclos) |
| `normalizar` | ambos | Asigna IDs, recalcula bloqueadas |
| `sync` | ambos | git pull --rebase --autostash + push |
| `unlock` | humano | Elimina lock colgado |

Transiciones prohibidas por código: cualquier cosa → hecha salvo revision→hecha;
trabajar sobre propuesta/bloqueada/revision/hecha; borrar tarjetas no-propuesta;
editar una tarjeta que no esté en_curso.

## Gobierno del dato

- **Almacén único:** `argos.json` en la raíz del proyecto (escritor: el CLI; nadie más).
- **Contrato publicado:** el esquema (proyecto/version/tareas) es estable; campos nuevos
  se AÑADEN, nunca se renombran.
- **Verificador:** suite pytest (transiciones prohibidas, dependencias, ciclos, IDs, lock,
  JSON corrupto, ciclo de vida completo). Nace verde o no se pushea.
- **Deuda consciente:** la autoridad humano/agente vive en el prompt (ver non-goals).

## Stack

- Python 3.11+, **cero dependencias** (stdlib only) — se instala igual en Windows y en el
  VM NaN sin fricción.
- Empaquetado: pyproject + entry point `argos`. Instalación: `uv tool install`.

## Arquitectura

| Archivo | Responsabilidad |
|---|---|
| `src/argos/modelo.py` | Tarea, Argos, estados, transiciones, IDs, normalizar, guardado atómico |
| `src/argos/lock.py` | Lock de escritor único + detección de PID muerto |
| `src/argos/cli.py` | argparse, comandos, salidas texto/JSON, códigos de salida (0 ok, 1 rechazo, 2 ocupado) |
| `plantilla/AGENTS.md` | Reglas del agente, copiable con `init` |
| `tests/` | pytest: cada transición prohibida falla por código |

## Criterios de éxito

- Suite pytest verde (objetivo: 60+ casos).
- `uv tool install -e .` → `argos estado` funciona fuera del repo.
- Ciclo de vida completo end-to-end: init → proponer → aprobar → empezar → terminar → hecha.
- Lock: segundo proceso simultáneo recibe "argos ocupado" (código 2).
- Repo en GitHub (Ntizar/Argos) con CI opcional de pytest.

## Anti-patrones (lo que evitamos)

- Que el modelo pequeño reimporte comandos hasta colar: un rechazo es una respuesta,
  con mensaje que explica POR QUÉ.
- Editar el JSON a mano desde el agente: el CLI valida, el JSON solo lo toca el CLI
  (y el humano si quiere, asumiendo el riesgo).
- Estados extra o sinónimos: 6, ni uno más.
