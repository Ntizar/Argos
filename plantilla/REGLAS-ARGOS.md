# REGLAS DE ARGOS (para el agente)

> Plantilla de Argos. `argos init` copia este fichero como AGENTS.md en el
> proyecto. Hecho con ❤️ por David Antizar.

Trabajas con un tablero de tareas compartida con un humano. El tablero es UN archivo
JSON (`argos.json`). NUNCA lo editas a mano: TODO pasa por el CLI.

    tablero <comando> [argumentos]

Si el CLI rechaza un comando, NO reintentes lo mismo ni edites el JSON:
lee el mensaje (explica POR QUÉ) y sigue el protocolo. Un rechazo es una
respuesta, no un obstáculo. Códigos de salida: 0 ok · 1 rechazo · 2 tablero ocupado.
Tip: añade `--json` si quieres la salida estructurada.

## ESTADOS (6, ni uno más)

| Estado    | Significado                                   | Quién lo pone        |
|-----------|-----------------------------------------------|----------------------|
| propuesta | Propuesta tuya, pendiente de aprobación       | Tú (proponer)        |
| bloqueada | Aprobada, pero falta alguna dependencia       | Automático (CLI)     |
| por_hacer | Aprobada y lista para trabajar                | El humano (aprobar)  |
| en_curso  | La estás trabajando ahora                     | Tú (empezar)         |
| revision  | Terminada, pendiente de verificación humana   | Tú (terminar)        |
| hecha     | Verificada y cerrada                          | SOLO el humano       |

Transiciones PROHIBIDAS para ti (el CLI las rechaza por código):
- Cualquier cosa → hecha. NUNCA marques nada como hecho ni ejecutes `argos hecha`.
- Trabajar sobre propuesta, bloqueada o revision. Solo trabajas tarjetas por_hacer.
- Borrar tarjetas. No existe comando de borrado para ti (solo el humano puede rechazar propuestas).

## PROTOCOLO DE SESIÓN (en orden, siempre)

1. **LEE ARGOS:** `argos estado`. Si avisa de tarjetas sin ID o cambios de
   bloqueo: `argos normalizar`. Resume al humano: preparadas, bloqueadas, anomalías.
2. **ELIGE:** `argos preparadas` y `argos ver <ID>`. Si hay varias y el humano
   no dijo cuál, PREGUNTA. No elijas por tu cuenta fuera del modo YOLO.
3. **EMPIEZA:** `argos empezar <ID>`. Si falla, NO trabajes esa tarjeta.
4. **TRABAJA. UNA tarjeta a la vez.** Nunca dos en_curso.
   - Trabajo nuevo descubierto → `argos proponer <GRUPO> "Título" "Descripción" --depende-de <ID>`.
   - Avances/decisiones → `argos editar <ID> "texto"` (solo en en_curso).
5. **ENTREGA:** `argos terminar <ID>` y en 3-5 líneas: qué hiciste, qué archivos
   tocaste, cómo verificarlo. Tu trabajo acaba en revision, NO en hecha.
6. **ESPERA** mientras haya tarjetas en revision (salvo modo YOLO).
7. **CIERRE:** `argos estado` + resumen: hecho, en revisión, bloqueado.

## SI ESTÁS ATASCADO

- Falta información/credencial/decisión → NO inventes: `argos pausar <ID>`,
  `argos editar <ID> "falta exactamente X"` y UNA pregunta concreta al humano.
- Dos fallos seguidos del CLI con la misma tarjeta → para y muestra el error tal cual.
- Tarjeta ambigua → pregunta ANTES de empezar.

## MODO YOLO

Solo se activa si el humano escribe literalmente: "MODO YOLO: hasta <ID>" o
"MODO YOLO: N tareas". Sin esa frase, modo normal. En YOLO encadenas preparadas
(máx 3 o hasta el ID) con ciclo completo empezar→trabajar→terminar, y PARAS
inmediatamente si: falla un comando, fallan dos pruebas seguidas, la tarea pide
credenciales/dinero/borrado, la tarjeta es ambigua, o llegas al límite.

## ESCRITOR ÚNICO

- Si el CLI dice "OCUPADO" (código 2), hay otro escritor con el lock: NO fuerces
  nada, avisa al humano. `argos unlock` es SOLO del humano.
- El humano puede editar el JSON a mano; tú nunca. Si algo no cuadra,
  `argos estado` + `argos normalizar` antes de seguir.

## ERRORES TÍPICOS QUE DEBES EVITAR

- Inventarte un ID: los asigna el CLI (`argos lista` para verlos).
- Marcar trabajo como hecho: tu máximo es revision.
- Encadenar tareas sin frase YOLO literal.
- Resumir el tablero de memoria: léela siempre con `argos estado`.
- Reintentar un rechazo cambiando argumentos hasta colar.
