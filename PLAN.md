# PLAN — TalentMatch IA (MVP)

> Estado: **APROBADO** (2026-11-18)
> Basado en [SPEC.md](SPEC.md) (aprobado el 2026-11-18).

## Cómo trabajamos

- **Una tarea a la vez**, en orden. Cada tarea dura ≤ ~1 h.
- Cada tarea termina con: código + pruebas en verde (`pytest`) + **un commit** con el mensaje indicado
  (Conventional Commits, en español) + la casilla marcada en este archivo.
- Al terminar cada tarea te explico en 3–5 líneas qué hice y por qué, y espero tu visto bueno antes de seguir.
- **Ramas:** todo el MVP va en la rama `feat/mvp`, con un commit por tarea. Hago push al terminar cada
  bloque (A, B, …) y abro un PR a `main` al final de la FASE 3.
- Nada se agrega si no está en SPEC.md. Si se me ocurre algo, te lo propongo primero.
- Leyenda: HU = historia de usuario del SPEC.

---

## Bloque A — Base del proyecto

### [x] T01 · Esqueleto de Django y configuración
- **Qué:** `venv`, `requirements.txt`, proyecto `config/`, apps `vacantes` y `analisis`, paquete
  `services/`, `settings.py` leyendo `.env` con python-dotenv, `.env.example`, `pytest.ini` con
  pytest-django, español (`LANGUAGE_CODE="es-mx"`, `TIME_ZONE="America/Mexico_City"`).
- **Terminado cuando:** `python manage.py check` pasa sin errores; `pytest` corre; el servidor arranca sin `.env`.
- **Pruebas:** `test_settings.py`: hay `SECRET_KEY` por defecto solo en DEBUG; `LLM_MODELO` por defecto = `claude-haiku-5-5`.
- **Commit:** `chore: esqueleto de Django con configuración por variables de entorno`

### [x] T02 · Tailwind y plantilla base
- **Qué:** `package.json` con `tailwindcss` + `@tailwindcss/cli` y scripts `css:build`/`css:watch`;
  `static/src/input.css`; `templates/base.html` (navbar, contenedor responsivo y pie); página de
  inicio `/`; `static/css/app.css` compilado y versionado.
- **Terminado cuando:** `npm run css:build` genera el CSS minificado; `/` se ve bien en móvil y escritorio.
- **Pruebas:** `GET /` responde 200, usa `base.html` y enlaza `css/app.css`.
- **Commit:** `feat: plantilla base con Tailwind CSS y página de inicio`

### [x] T03 · Bloqueo de red en pruebas y ProveedorFalso (infraestructura de tests)
- **Qué:** `tests/conftest.py` con una *fixture* `autouse` que vacía `ANTHROPIC_API_KEY` y bloquea
  `socket.connect` hacia fuera. Esqueleto de `ProveedorFalso` (respuestas programadas) para usarlo más adelante.
- **Terminado cuando:** cualquier intento de conexión a internet dentro de un test falla con un error explícito.
- **Pruebas:** un test que intenta abrir una conexión y verifica que se bloquea.
- **Commit:** `test: bloqueo de red y proveedor LLM falso para las pruebas`

---

## Bloque B — Vacantes (HU-09)

### [x] T04 · Modelo Vacante y admin
- **Qué:** modelo `Vacante` (campos del SPEC §6, `choices` para modalidad y nivel, `JSONField` para
  habilidades), migración, `VacanteAdmin` con `list_filter` por nivel y modalidad, `search_fields` y `list_display`.
- **Terminado cuando:** puedo crear, editar y borrar vacantes en `/admin/`.
- **Pruebas:** crear vacante; `__str__`; validación de que las habilidades sean una lista de strings; el admin carga (200) para un superusuario.
- **Commit:** `feat: modelo Vacante con administración en el admin de Django`

### [x] T05 · Comando `cargar_vacantes_ejemplo`
- **Qué:** `vacantes/data/vacantes_ejemplo.json` con 20 vacantes de TI de empresas inventadas
  (mezcla de niveles trainee/jr/mid, modalidades y stacks) y el comando que las carga con `update_or_create`.
- **Terminado cuando:** correrlo dos veces deja exactamente 20 vacantes; todas dicen "(ficticia)".
- **Pruebas:** carga 20; es idempotente; los datos del JSON son válidos (niveles y modalidades permitidos).
- **Commit:** `feat: comando para cargar 20 vacantes ficticias de ejemplo`

---

## Bloque C — Lógica determinista (sin LLM)

### [x] T06 · Normalización de habilidades
- **Qué:** `services/habilidades.py`: `normalizar(habilidad)` (minúsculas, sin acentos ni puntuación
  sobrante) + diccionario de sinónimos; `normalizar_lista()` sin duplicados.
- **Terminado cuando:** `"React.js"`, `"react"` y `"ReactJS"` dan lo mismo; `"C#"` y `"C++"` **no** se rompen.
- **Pruebas:** tabla parametrizada de casos (sinónimos, acentos, símbolos, vacíos).
- **Commit:** `feat: normalización de habilidades con diccionario de sinónimos`

### [x] T07 · Puntaje determinista
- **Qué:** `services/matching.py`: `calcular_match_determinista(habilidades_perfil, vacante)` →
  `ResultadoDeterminista(puntaje, coincidentes, faltantes_requeridas, faltantes_deseables)`, con la
  fórmula 80/20 del SPEC §4.5 y `combinar_puntajes(det, llm, peso)`.
- **Terminado cuando:** la fórmula coincide con el SPEC, incluido el caso sin deseables.
- **Pruebas:** 100 % de coincidencia, 0 %, parcial, sin deseables, mismo input → mismo output (HU-03), peso configurable.
- **Commit:** `feat: puntaje determinista de coincidencia de habilidades`

### [x] T08 · Extracción de texto del CV
- **Qué:** `services/extraccion.py`: `extraer_texto(archivo | texto)` para PDF (pypdf), DOCX
  (python-docx) y texto pegado, todo en memoria. Errores propios: `ArchivoInvalidoError`,
  `CVVacioError` (< 200 caracteres) y `CVDemasiadoLargoError` (> 30 000); límite de 5 MB.
- **Terminado cuando:** los tres orígenes devuelven texto limpio y cada caso inválido lanza su error.
- **Pruebas:** PDF y DOCX generados dentro del test; extensión no permitida; archivo corrupto; vacío; demasiado largo; > 5 MB.
- **Commit:** `feat: extracción de texto de CV en PDF, DOCX y texto pegado`

### [x] T09 · Esquemas Pydantic
- **Qué:** `services/esquemas.py` con `PerfilCV` y subesquemas, `VacanteEstructurada`,
  `EvaluacionVacante`, `Brecha`, `PasoAprendizaje` y `Recomendaciones` (límites del SPEC: 3–7 brechas,
  2–4 pasos y 3–6 sugerencias). Incluye una función que genera el JSON Schema para las herramientas.
- **Terminado cuando:** los esquemas aceptan datos válidos y rechazan los inválidos con mensajes legibles.
- **Pruebas:** casos válidos e inválidos (nivel fuera de rango, puntaje > 100, listas fuera de límite).
- **Nota de implementación:** las brechas se validan con mínimo 1 (el *prompt* pide 3–7) para no obligar al modelo a inventar brechas en perfiles muy completos. Los pasos del plan son una lista de textos dentro de `Brecha`, sin un esquema `PasoAprendizaje` aparte.
- **Commit:** `feat: esquemas Pydantic para perfil, vacantes y recomendaciones`

---

## Bloque D — Capa de LLM

### [x] T10 · Interfaz ProveedorLLM y fábrica
- **Qué:** `services/llm.py`: `ProveedorLLM` (ABC), los tipos neutrales `Herramienta`,
  `LlamadaHerramienta` y `RespuestaLLM`, la jerarquía de errores (`ErrorLLM` → `ApiKeyInvalidaError`,
  `LimiteApiError`, `ConexionLLMError`, `RechazoModeloError`, `RespuestaInvalidaError`) y
  `obtener_proveedor()` según el entorno.
- **Terminado cuando:** sin API key devuelve `ProveedorDemo` (todavía como esqueleto); con key y `LLM_PROVEEDOR=anthropic` devuelve `ProveedorAnthropic`.
- **Pruebas:** las combinaciones de variables de entorno → proveedor correcto; un proveedor desconocido produce un error claro.
- **Commit:** `feat: capa intercambiable de proveedor de LLM`

### [x] T11 · ProveedorAnthropic
- **Qué:** `services/proveedores/anthropic.py`: `generar_estructurado` (salida estructurada validada con
  Pydantic) y `chat_con_herramientas` (traduce de y hacia `RespuestaLLM`, `tool_choice=auto`,
  `strict: true`). Mapea las excepciones del SDK a nuestros errores y revisa `stop_reason`
  (`refusal`, `max_tokens`). Antes de escribir este código leo la documentación del SDK.
- **Terminado cuando:** con el cliente del SDK simulado, se traducen bien las respuestas de texto, de herramientas y de error.
- **Pruebas:** cliente simulado (`unittest.mock`): respuesta con `tool_use`, `end_turn`, `refusal`, 401, 429, 5xx, error de conexión, JSON inválido.
- **Commit:** `feat: proveedor Anthropic con traducción de herramientas y errores`

### [x] T12 · ProveedorDemo: perfil heurístico
- **Qué:** `services/catalogo_habilidades.py` (habilidades técnicas y blandas conocidas) y
  `ProveedorDemo.generar_estructurado` para `PerfilCV`: detecta habilidades, idiomas y nivel por reglas.
- **Terminado cuando:** un CV de ejemplo produce un perfil razonable y válido según `PerfilCV`, sin red.
- **Pruebas:** CV jr con Python/Django → detecta esas habilidades y nivel `jr`; CV sin años → `trainee`; el resultado valida con Pydantic.
- **Commit:** `feat: modo demo con extracción heurística de perfil`

### [x] T13 · Servicio de perfil
- **Qué:** `services/perfil.py`: `extraer_perfil(texto, proveedor)` con el *prompt* de sistema
  (el CV va delimitado como dato, ver R9) y **1 reintento** si el JSON es inválido.
- **Terminado cuando:** devuelve un `PerfilCV`; tras dos respuestas inválidas lanza `RespuestaInvalidaError`.
- **Pruebas:** con `ProveedorFalso`: éxito; inválido → válido (reintento); inválido × 2 → error.
- **Commit:** `feat: extracción de perfil estructurado del CV con el LLM`

---

## Bloque E — Agente (F5, F6)

### [x] T14 · Herramientas del agente
- **Qué:** `services/herramientas.py`: `buscar_vacantes(nivel?, modalidad?, habilidades?, limite≤10)`,
  `obtener_vacante(id)`, `calcular_match(vacante_id)` (usa el perfil del contexto) y la definición de
  `entregar_recomendaciones`. Incluye las definiciones con JSON Schema y un despachador que valida
  argumentos y convierte errores en resultados `is_error`.
- **Terminado cuando:** cada herramienta devuelve un JSON pequeño y serializable; un id inexistente o argumentos inválidos dan un error manejable, no una excepción.
- **Pruebas:** filtros de búsqueda; límite de resultados; id inexistente; argumentos inválidos; herramienta desconocida.
- **Commit:** `feat: herramientas del agente para buscar, consultar y calcular match`

### [x] T15 · Ciclo del agente
- **Qué:** `services/agente.py`: `ejecutar_agente(perfil, proveedor, vacante_externa=None)`. El ciclo
  llama al LLM, ejecuta las herramientas y devuelve los resultados; termina al recibir
  `entregar_recomendaciones` y valida con Pydantic. Corta a `AGENTE_MAX_ITERACIONES`, con 1 corrección
  si la entrega es inválida.
- **Terminado cuando:** con `ProveedorFalso` recorre un guion de varias iteraciones y devuelve `Recomendaciones`.
- **Pruebas:** ciclo feliz (3 iteraciones); límite alcanzado; entrega inválida → corrección → válida; varias llamadas en un mismo turno; herramienta con error.
- **Commit:** `feat: agente con ciclo de herramientas y límite de iteraciones`

### [x] T16 · Respaldo determinista y agente en modo demo
- **Qué:** `services/respaldo.py` (top 5 por puntaje determinista y brechas por frecuencia, marcado
  como parcial). `ProveedorDemo.chat_con_herramientas` con su guion: buscar → `calcular_match` × N →
  entregar, con puntaje LLM simulado.
- **Terminado cuando:** el agente en modo demo termina sin red; si el agente falla, el respaldo devuelve un resultado útil.
- **Pruebas:** el agente con `ProveedorDemo` devuelve `Recomendaciones` válidas; el respaldo produce top 5 ordenado y `resultado_parcial=True`.
- **Commit:** `feat: respaldo determinista y guion del agente en modo demo`

### [x] T17 · Vacante pegada (HU-04)
- **Qué:** `services/vacante_externa.py`: `estructurar_vacante(texto, proveedor)` → `VacanteEstructurada`
  (+ versión demo heurística), que se evalúa con el mismo puntaje híbrido. Se pasa al agente como
  contexto adicional.
- **Terminado cuando:** una vacante pegada aparece evaluada en el resultado y no se crea ninguna fila en `Vacante`.
- **Pruebas:** estructuración con `ProveedorFalso` y con el demo; el conteo de `Vacante` no cambia; texto vacío → error claro.
- **Commit:** `feat: análisis de una vacante pegada por el usuario`

---

## Bloque F — Persistencia y orquestación (F7)

### [x] T18 · Modelos Analisis y ResultadoMatch
- **Qué:** modelos del SPEC §6 (con copia de título y empresa, y `SET_NULL`), migración y registro en el admin (solo lectura).
- **Terminado cuando:** se pueden guardar análisis con sus resultados; borrar una vacante no rompe el historial.
- **Pruebas:** creación; orden por posición; borrar `Vacante` → el resultado conserva el título.
- **Commit:** `feat: modelos de análisis y resultados de match`

### [x] T19 · Orquestador
- **Qué:** `services/orquestador.py`: `analizar_cv(texto, origen, texto_vacante=None)` →
  perfil → agente (o respaldo) → `puntaje_final` calculado por el código → guarda todo en una
  transacción → devuelve el `Analisis`.
- **Terminado cuando:** una llamada en modo demo crea 1 `Analisis` y hasta 5 (+1 externa) `ResultadoMatch`, con los puntajes combinados bien.
- **Pruebas:** flujo con `ProveedorFalso`; puntaje final = 0.6·det + 0.4·llm; un fallo del LLM a medias no deja datos a medio guardar.
- **Commit:** `feat: orquestador del análisis completo de CV`

---

## Bloque G — Interfaz (HU-01…HU-08, HU-10)

### [ ] T20 · Formulario y vista de análisis
- **Qué:** `AnalisisForm` (archivo **o** texto, vacante opcional y validación de exclusividad), vista
  `/analizar/` que llama al orquestador y redirige a los resultados; los errores se muestran en el
  formulario; indicador de carga al enviar (JS mínimo).
- **Terminado cuando:** subir PDF/DOCX/texto en modo demo lleva a los resultados; cada error muestra su mensaje en español.
- **Pruebas:** (Django test client) éxito con PDF, DOCX y texto; ni archivo ni texto; ambos a la vez; extensión inválida; **no queda ningún archivo en disco ni en `MEDIA_ROOT`**; cada `ErrorLLM` → su mensaje.
- **Commit:** `feat: formulario y vista para analizar un CV`

### [ ] T21 · Página de resultados
- **Qué:** `/analisis/<id>/`: perfil; tarjetas del top 5 con barra de puntaje, desglose,
  habilidades coincidentes/faltantes (en *chips*) y explicación; sección de vacante externa; brechas
  con mini plan; sugerencias y palabras ATS; aviso si es un resultado parcial.
- **Terminado cuando:** se ve bien en móvil y escritorio y muestra todos los datos guardados.
- **Pruebas:** 200 con datos; 404 si no existe; aparecen el aviso de parcial y la sección externa cuando corresponde.
- **Commit:** `feat: página de resultados con top 5, brechas y sugerencias`

### [ ] T22 · Historial
- **Qué:** `/historial/` paginado (10 por página): fecha, nivel, mejor vacante y su puntaje, con enlace a los resultados. Enlace en la navbar.
- **Terminado cuando:** la lista sale ordenada del más reciente al más antiguo y la paginación funciona.
- **Pruebas:** orden; paginación (11 análisis → 2 páginas); estado vacío.
- **Commit:** `feat: historial de análisis`

### [ ] T23 · Aviso de modo demo, errores y logging
- **Qué:** *context processor* con un aviso de "Modo demo" visible en todas las páginas cuando
  corresponde; aviso de privacidad del historial (R6); logging de errores sin datos del CV; páginas 404/500 propias.
- **Terminado cuando:** sin key se ve el aviso; con key no; los logs no contienen texto del CV.
- **Pruebas:** aviso presente o ausente según el entorno; `caplog` no contiene un fragmento del CV tras un error.
- **Commit:** `feat: aviso de modo demo, páginas de error y logging seguro`

---

## Bloque H — Cierre de calidad

### [ ] T24 · Prueba de punta a punta en demo y cobertura
- **Qué:** test e2e: cargar vacantes → subir un CV de ejemplo → ver resultados → verlo en el historial,
  todo en modo demo. Medir la cobertura con `pytest-cov` y cubrir los huecos hasta ≥ 80 % en `services/`.
- **Terminado cuando:** la suite completa está en verde y la cobertura de `services/` es ≥ 80 %.
- **Pruebas:** el propio test e2e + el reporte de cobertura.
- **Commit:** `test: prueba de punta a punta en modo demo y cobertura de servicios`

---

## FASE 4 — README

### [ ] T25 · README final
- **Qué:** README en español (problema, capturas, diagrama, cómo funciona el agente, pasos para
  correrlo en local, modo demo, pruebas, decisiones técnicas y siguientes pasos) + capturas en `docs/img/`.
- **Terminado cuando:** alguien sin contexto puede clonar y correr el proyecto en modo demo con ≤ 6 comandos.
- **Commit:** `docs: README con arquitectura, guía de instalación y capturas`

---

## Resumen

| Bloque | Tareas | Resultado visible al terminar |
|---|---|---|
| A | T01–T03 | El proyecto arranca, con página de inicio y Tailwind. |
| B | T04–T05 | 20 vacantes en el admin. |
| C | T06–T09 | Matching y extracción probados sin LLM. |
| D | T10–T13 | Perfil del CV con Anthropic o en demo. |
| E | T14–T17 | El agente recomienda vacantes. |
| F | T18–T19 | Los análisis se guardan. |
| G | T20–T23 | App usable de punta a punta. |
| H | T24 | Calidad verificada. |
| FASE 4 | T25 | README de portafolio. |
