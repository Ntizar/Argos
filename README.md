# Mesa 🗂️

**Tablero de tareas humano+agente.** Tarjetas con 6 estados, dependencias y bloqueo
automático, en un JSON plano que vive en tu repo. El agente NUNCA toca el JSON:
todo pasa por el CLI, que valida y rechaza lo prohibido **por código**.

> Inspirado en Kanvas (MIT, XMihura). Adaptación propia en castellano, JSON plano
> y CLI instalable. Hecho con ❤️ por David Antizar.

## Instalación

```bash
uv tool install git+https://github.com/Ntizar/Mesa
# o: pipx install git+https://github.com/Ntizar/Mesa
```

Cero dependencias: solo stdlib de Python 3.11+.

## Uso

```bash
cd tu-proyecto        # cualquier repo
tablero init          # crea tablero.json (+ AGENTS.md con las reglas del agente)
```

### El ciclo de una tarjeta

```
propuesta --(humano: aprobar)--> por_hacer --(agente: empezar)--> en_curso
en_curso --(agente: terminar)--> revision --(humano: hecha)--> hecha
en_curso --(agente: pausar)--> por_hacer
bloqueada --(automático: normalizar)--> por_hacer   cuando todas las dependencias estén hecha
```

### Comandos

| Comando | Quién | Qué hace |
|---|---|---|
| `tablero init [nombre]` | humano | Crea `tablero.json` + `AGENTS.md` |
| `tablero estado` | ambos | Resumen, conteos y anomalías |
| `tablero preparadas` | agente | Tarjetas `por_hacer` listas |
| `tablero bloqueadas` | ambos | Bloqueadas y qué las bloquea |
| `tablero empezar <ID>` | agente | `por_hacer → en_curso` |
| `tablero terminar <ID>` | agente | `en_curso → revision` |
| `tablero pausar <ID>` | agente | `en_curso → por_hacer` |
| `tablero editar <ID> "texto"` | agente | Notas (solo en_curso) |
| `tablero proponer <GRUPO> "T" "D" [--depende-de ID]` | agente | Nueva propuesta |
| `tablero aprobar <ID>` | humano | `propuesta → por_hacer` |
| `tablero hecha <ID>` | humano | `revision → hecha` |
| `tablero rechazar <ID>` | humano | Borra una propuesta |
| `tablero dep <A> <B>` | humano | A bloquea a B (rechaza ciclos) |
| `tablero normalizar` | ambos | Asigna IDs, recalcula bloqueos |
| `tablero sync` | ambos | `git pull --rebase` + push |
| `tablero unlock` | humano | Elimina un lock colgado |

Todos los comandos aceptan `--json` (salida estructurada para agentes) y
`--tablero <ruta>`. Códigos de salida: `0` ok · `1` rechazo · `2` ocupado.

## Por qué funciona con agentes

- **El CLI impide, el prompt sugiere.** "Nunca marques hecha" es una regla que un
  modelo pequeño olvida; un `if` en Python no la olvida nunca.
- **Un rechazo es una respuesta.** Cada error explica POR QUÉ y cuál es el camino legal.
- **Lock de escritor único.** Dos agentes (o agente + humano editando) no corrompen
  el JSON: `tablero.lock` con detección de PID muerto y locks colgados.
- **Escritura atómica.** El JSON nunca queda a medias.
- **IDs asignados por el CLI.** El agente no inventa identificadores.

## Desarrollo

```bash
git clone https://github.com/Ntizar/Mesa && cd Mesa
uv venv .venv && uv pip install -e . pytest --python .venv
.venv/Scripts/python -m pytest -q      # en Windows
```

## Licencia

MIT — ver [LICENSE](LICENSE).
