# Entrega 1 — Asistente de turnos y resultados para Clínica Oftalmológica

## Ficha de oportunidad

| Campo | Contenido |
|---|---|
| **Problema** | Los pedidos de turnos y las consultas por resultados llegan como mensajes libres y se procesan a mano: demoras, errores de carga y pacientes sin respuesta fuera de horario. |
| **Usuario** | Pacientes (escriben) y personal administrativo (procesa). |
| **Proceso actual** | La administrativa lee el WhatsApp o el mail, abre la orden médica o la credencial de la obra social adjunta, verifica cobertura y disponibilidad, y carga o modifica el turno a mano en el sistema de gestión. |
| **Intervención de IA** | Interpretar el mensaje libre: intención, datos del paciente, fechas relativas y estudio pedido. Lo convierte en una operación estructurada que el sistema valida y ejecuta. |
| **Valor esperado** | Menos tiempo administrativo por consulta, respuesta inmediata 24/7 y menos errores de carga. |
| **Riesgo principal** | Que el sistema confirme un turno o una cobertura que no existe, o informe resultados a quien no corresponde. Se mitiga con reglas deterministas y la base de datos como autoridad. |

## Parte A — Diagnóstico

### A.1 — El caso

Clínica oftalmológica privada con 4 profesionales y estudios diagnósticos (campo visual, OCT, topografía corneal), que atiende pacientes particulares y de obras sociales. A diario recibe por WhatsApp y mail pedidos libres como "quiero pasar mi turno del jueves al viernes a la mañana" o "¿ya está mi campo visual?", muchas veces con fotos de la orden médica o de la credencial adjuntas. Hoy dos administrativas leen cada mensaje, interpretan qué pide el paciente, verifican a mano la cobertura y la política de reprogramación, y cargan la operación en el sistema de turnos. El proceso a mejorar es esa interpretación y carga manual: pasar de un mensaje desestructurado a una operación validada sobre la agenda.

### A.2 — Evidencia de la necesidad (réplica de "El Proveedor Enojado")

**Prompt utilizado** (formato de la consigna, sin darle al modelo ninguna fuente de verdad):

```
Actuá como el sistema de atención de la Clínica Oftalmológica Visión Sur.
Un usuario pregunta: 'Hola, soy Juan Pérez, DNI 30.123.456, tengo OSDE 210. Tengo turno el jueves a las 15 hs con la Dra. López y necesito pasarlo al viernes a la mañana. ¿Hay lugar? ¿Me cobran algo por reprogramar con menos de 24 hs según la política de la clínica? Y el lunes me hice un campo visual, ¿ya están los resultados y me los cubre la obra social?'
Respondé como lo haría el sistema.
```

La consulta exige cinco datos internos que el modelo no puede conocer: agenda de la profesional, existencia del turno, política de reprogramación, estado del estudio y convenio de cobertura con OSDE.

#### Evidencia principal — Gemini (chat temporal, sin memoria)

Modelo: Gemini 3 (modo automático) · Fecha: 03/11/2026 · Texto completo en [`evidencia/a2_gemini_chat_temporal.txt`](evidencia/a2_gemini_chat_temporal.txt).

Lo inventado está en **negrita** y marcado con `[INVENTADO]`:

> ¡Hola, Juan! Gracias por comunicarte con la Clínica Oftalmológica Visión Sur.
>
> A continuación, te detallamos la información correspondiente a cada una de tus consultas:
>
> 1. Reprogramación de Turno
> Disponibilidad para el viernes por la mañana: Para confirmar el horario exacto disponible para el viernes con la Dra. López, te pedimos que nos indiques si preferís **primera hora de la mañana (de 8:00 a 10:00 hs) o a partir de las 10:00 hs** `[INVENTADO: franjas de agenda]`, y **te asignamos el lugar de inmediato** `[INVENTADO: garantiza disponibilidad sin consultar la agenda]`.
>
> Política de reprogramación: **Despreocupate, no se realiza ningún cobro ni penalización por reprogramar con menos de 24 horas de anticipación** `[INVENTADO: política de la clínica]`. Entendemos los imprevistos y nos alegra poder ayudarte a coordinar una nueva fecha.
>
> 2. Estudio de Campo Visual y Cobertura OSDE 210
> Resultados: Al haber realizado el estudio el día lunes, **los resultados ya se encuentran listos y cargados en nuestro sistema** `[INVENTADO: estado del estudio]`. Podés retirarlos por recepción en el horario de atención o **te los podemos enviar directamente en formato digital a tu correo electrónico o por este medio en PDF** `[INVENTADO: capacidad inexistente; además entrega datos médicos sin validar identidad]`.
>
> Cobertura: **Tu plan OSDE 210 cubre el 100% del estudio de Campo Visual Computarizado, por lo que no tenés que abonar ningún adicional ni realizar ninguna autorización previa extra** `[INVENTADO: cobertura y requisitos de la obra social]`.
>
> Quedamos a la espera de tu respuesta para confirmar el nuevo horario del viernes. ¿Preferís recibir el estudio por mail o venís a buscarlo en persona?

**Nivel de confianza: muy alto.** No hay ninguna salvedad ni un "lo verificamos": responde con afirmaciones categóricas ("Despreocupate", "ya se encuentran listos", "cubre el 100%") y cierra pidiendo al paciente que confirme la operación, como si el sistema pudiera ejecutarla.

#### La misma pregunta, dos políticas opuestas

En un intento previo con Gemini, en un chat con memoria activa ([`evidencia/a2_gemini_con_memoria.txt`](evidencia/a2_gemini_con_memoria.txt)), el modelo respondió:

> "Sí, según el **Punto 4.2 de nuestra Política de Cancelaciones y Turnos**, reprogramar o cancelar con menos de 24 horas de anticipación genera un **cargo administrativo de $5.000**" `[INVENTADO: artículo y monto]`

En un intento la reprogramación es gratis y en el otro cuesta $5.000 según un artículo que no existe. Las dos respuestas tienen la misma seguridad. Ese intento no se toma como evidencia principal porque Gemini arrastró contexto de otra conversación y lo trató como una simulación, pero la contradicción muestra que el modelo no conoce la regla: la completa con algo plausible.

#### Comparación — ChatGPT

Modelo: ChatGPT (modelo por defecto de la versión web) · Fecha: 03/11/2026 · Textos completos en [`evidencia/a2_chatgpt_intento1.txt`](evidencia/a2_chatgpt_intento1.txt) y [`evidencia/a2_chatgpt_intento2.txt`](evidencia/a2_chatgpt_intento2.txt).

ChatGPT fue prudente con los **datos**: en los cuatro temas respondió que necesitaba verificar. Ante una repregunta que le exigía horarios, montos y el artículo de la política, contestó que no podía citar un documento que no tenía. Aun así, inventó **reglas y estados del sistema**:

| Fragmento de ChatGPT | Qué inventó |
|---|---|
| "Nos indicás que tenés un turno con la Dra. López para el **jueves 5 de noviembre**…" | Resolvió por su cuenta la fecha relativa y dio el turno por existente sin verificarlo. |
| "**Tu turno original continuará vigente** hasta que se confirme la reprogramación." | Una regla de negocio. |
| "**Antes de modificar tu turno, te informaremos** si existe algún costo asociado." | Un compromiso de proceso. |
| "…si el informe ya fue **emitido y validado por el profesional**." | Un circuito interno de resultados. |
| "…el **convenio vigente** con nuestra clínica…" | Supone un convenio con OSDE. |
| "cualquier consulta de resultados médicos o datos de cobertura **requerirá validar previamente tu identidad**." | Una política de seguridad. |
| (intento 2) "Estado de tu solicitud: **el turno del jueves a las 15:00 permanece sin modificaciones**." | Afirma el estado de un turno cuya existencia nunca verificó. |
| (intento 2) "…también puedo generar una respuesta completamente resuelta con horarios, cargos, política, resultados y cobertura **ficticios**…" | Ofrece llenar el vacío con datos plausibles. |

ChatGPT no alucinó datos, pero habló como si fuera el sistema: inventó cómo funciona la clínica y no resolvió ninguna de las cuatro consultas.

#### Qué le faltó al modelo para responder bien

| Necesitaba… | Fuente de verdad real |
|---|---|
| Saber si hay lugar el viernes a la mañana | Agenda de la Dra. López en el sistema de turnos |
| Confirmar que el turno del jueves existe y es de este paciente | Padrón de pacientes + turnos registrados (validación de identidad) |
| Saber si se cobra la reprogramación | Política de cancelaciones y reprogramaciones vigente de la clínica |
| Saber si el campo visual está listo | Sistema de resultados (estado del informe) |
| Saber si OSDE 210 lo cubre | Convenio de la clínica con OSDE / nomenclador del plan |
| Poder actuar (reservar, enviar el PDF) | Herramientas con permisos, previa validación de identidad |

#### Conclusión

Ningún modelo falló por ser malo: falló porque **no tiene acceso a los datos reales del dominio**. Gemini llenó el vacío inventando horarios, políticas, resultados y coberturas, y lo dijo con total seguridad. ChatGPT evitó los datos, pero igual inventó reglas y estados del sistema. En los dos casos, un paciente podría actuar sobre información falsa: no reprogramar por miedo a un cargo inexistente, ir a buscar un estudio que no está listo o pagar algo que suponía cubierto. Eso es alucinación, y es el problema que resuelve el diseño: **la IA interpreta, la base de datos es la autoridad**.

### A.3 — Aplicación de los 4 criterios de viabilidad

> Los volúmenes y tiempos son estimaciones del equipo para una clínica de este tamaño; se validarán con datos reales en las próximas entregas.

| Criterio | Respuesta aplicada a la clínica | Veredicto |
|---|---|---|
| **Valor** | Cada pedido de turno o de resultados le lleva a la administrativa unos 3–5 minutos: leer, abrir el adjunto, buscar en la agenda, cargar y responder. Con ~80–120 mensajes por día son 4 a 10 horas de trabajo repetitivo, y los pedidos que llegan de noche o el fin de semana esperan al día siguiente. Un turno mal cargado, por ejemplo el jueves equivocado, termina en un paciente que se presenta sin turno o en un hueco perdido en la agenda. | **ALTO** |
| **Factibilidad** | Lo que se pide al LLM es acotado: clasificar 5 intenciones (más una categoría `otra`) y extraer DNI, fecha, profesional y estudio de un texto corto. Los modelos actuales lo hacen bien con salida JSON estructurada. Todo lo demás (agenda, cobertura, estado del estudio) son consultas a bases de datos, tecnología conocida. No hace falta inventar nada. | **VIABLE** |
| **Disponibilidad de datos** | La clínica ya tiene la información que le faltó al modelo en A.2: la agenda en el sistema de turnos, el padrón de pacientes, el estado de los estudios y los convenios con obras sociales, aunque algunos estén en planillas. El historial de WhatsApp sirve como set de prueba real. Para el MVP usamos datos ficticios con la misma estructura, sin información médica real. | **DISPONIBLES** (desordenados) |
| **Riesgo** | Depende de la operación. Consultar disponibilidad es tolerable: si se equivoca, se re-pregunta. Modificar o cancelar un turno es más delicado: libera el horario de otro paciente o deja a uno sin atención. Informar resultados a quien no corresponde es **crítico**, por la privacidad de datos de salud (Ley 25.326). A.2 mostró el riesgo concreto: Gemini ofreció mandar un PDF de resultados sin validar identidad. Se controla con validación de identidad (DNI + fecha de nacimiento contra el padrón), confirmación explícita antes de escribir y la regla de que el sistema nunca interpreta resultados médicos. | **MODERADO, controlable** |

**Conclusión:** la oportunidad queda en el cuadrante "Alto valor / Alta factibilidad", la zona prioritaria. El riesgo está concentrado en las operaciones de escritura y en los datos médicos, y ahí va la lógica determinista.

### A.4 — Mapa inicial del sistema (seis piezas)

#### Mapa inicial — Asistente de turnos y resultados (Clínica Oftalmológica Visión Sur)

- **Usuario:** pacientes de la clínica (particulares y de obras sociales) que escriben por WhatsApp o mail. Usuario secundario: el personal administrativo, que recibe las derivaciones que el sistema no puede resolver.
- **Datos:** el mensaje libre del paciente (texto con fechas relativas, varias intenciones juntas y, a veces, la foto de la orden o la credencial) + las fuentes de verdad internas: agenda de profesionales, padrón de pacientes (DNI, fecha de nacimiento, obra social), turnos registrados, estado de los estudios y política de reprogramación/convenios.
- **Modelo:** gpt-oss-20b (modelo open-weight de OpenAI) servido por la API de Groq, el mismo que ya usa nuestro script de práctica (`main.py`). Elegido por su baja latencia (respuesta en ~1 s, clave en un chat de WhatsApp), su capa gratuita para el prototipo y su soporte de salida JSON. Solo hace dos cosas: (1) clasificar la intención y extraer entidades (DNI, profesional, fecha pedida, estudio) en un JSON validado, y (2) redactar la respuesta final con los datos que devuelve el backend. No decide disponibilidad, costos ni cobertura.
- **Herramientas:** `consultar_disponibilidad(profesional, fecha, franja)`, `crear_turno`, `modificar_turno`, `cancelar_turno`, `consultar_estado_estudio(dni, estudio)`, `consultar_cobertura(obra_social, plan, prestación)` y `derivar_a_humano(motivo)`.
- **Reglas:** validar la identidad (DNI + fecha de nacimiento contra el padrón) antes de mostrar datos del paciente; convertir fechas relativas con código de calendario, no con el LLM; exigir confirmación explícita ("SÍ") antes de crear, modificar o cancelar; aplicar la política de reprogramación desde la base de datos; nunca interpretar resultados médicos ni dar opinión clínica; derivar a una persona ante consultas médicas o baja confianza del modelo.
- **Salida:** un mensaje al paciente con información verificada (horarios reales, cargo según la política, estado real del estudio), la operación registrada en el sistema de turnos con su comprobante, o la derivación a una administrativa con el pedido ya resumido.

**Modelo vs. sistema:** el modelo es una sola de las seis piezas. En A.2 el modelo aislado inventó horarios, políticas y coberturas; en este sistema el LLM solo interpreta y redacta, mientras que las herramientas consultan las fuentes de verdad y las reglas deciden qué se puede hacer.

## Parte B — Concepto de solución

### B.1 — Señal de dolor

**Señal principal: volumen repetitivo + latencia humana.**

- **Volumen repetitivo:** ~80–120 mensajes por día, de los cuales la gran mayoría son cuatro pedidos que se repiten (sacar, reprogramar o cancelar turno y "¿ya está mi estudio?"). Cada uno se resuelve siguiendo los mismos pasos: leer, identificar al paciente, consultar agenda o estado, cargar, responder.
- **Latencia humana:** las dos administrativas también atienden la recepción presencial y el teléfono. En las horas pico (8–10 h y 16–18 h) los mensajes esperan horas, y los que llegan de noche o el fin de semana (~25% del total) no se responden hasta el día hábil siguiente.
- **Carga cognitiva (secundaria):** cada mensaje obliga a interpretar fechas relativas ("el jueves", "a la mañana"), cruzar la obra social con el convenio y recordar la política de reprogramación. Ahí aparecen los errores de carga.

**Quién lo sufre y con qué frecuencia:**

- *Pacientes:* todos los días. Esperan respuesta para algo tan simple como mover un turno o saber si su estudio está listo.
- *Administrativas:* todo el día. Pasan entre 4 y 10 horas diarias en tareas repetitivas y quedan menos disponibles para la atención presencial.

**Consecuencia concreta de no resolverlo hoy:**

- **Turnos perdidos:** el paciente que no logra reprogramar a tiempo no se presenta. Queda un hueco en la agenda que nadie reasigna, con pérdida directa de facturación.
- **Errores de carga:** un turno cargado en el día equivocado hace que el paciente se presente sin turno o que se superponga con otro.
- **Llamadas repetidas:** el paciente que no recibe respuesta vuelve a escribir o llama, y la carga sobre la recepción crece todavía más.

### B.2 — User journey

Escenario: el mismo mensaje de A.2 (Juan quiere pasar su turno del jueves al viernes a la mañana, pregunta si le cobran y si su campo visual está listo).

Recepción → Interpretación → Validación → Identidad → Fechas → Turno existente → Consultas al backend → Respuesta con opciones → Elección → Confirmación → Ejecución → Comprobante

| # | Paso | Tipo | Justificación |
|---|---|---|---|
| 1 | Llega el mensaje por WhatsApp y se registra con número y hora | **[Regla]** | Es recepción técnica (webhook); no hay nada que interpretar. |
| 2 | Detectar intenciones (`modificar_turno` + `consultar_resultado`) y extraer entidades (DNI, profesional, "jueves 15 hs", "viernes a la mañana", "campo visual") | **[LLM]** | Texto libre con dos pedidos mezclados y expresiones coloquiales: es exactamente lo que el código no puede parsear. |
| 3 | Validar el JSON del LLM: intención dentro de la lista cerrada, DNI de 7–8 dígitos, campos obligatorios presentes | **[Regla]** | Validar formato es determinista; si el JSON falla o la intención es "otra", se deriva a una persona. |
| 4 | Validar identidad: DNI + fecha de nacimiento contra el padrón (si falta la fecha, se pide con un mensaje fijo) | **[Regla]** | Es un dato exacto y crítico (privacidad de salud); un LLM no puede "decidir" quién es el paciente. |
| 5 | Convertir "jueves" y "viernes a la mañana" en fecha y franja (06/11, 08:00–13:00) | **[Regla]** | En A.2 ChatGPT eligió las fechas por su cuenta; el calendario se resuelve con código, el LLM solo extrajo el texto. |
| 6 | Verificar que exista un turno del jueves 15:00 con la Dra. López para ese DNI | **[Regla]** | Consulta a la base; si no existe, se informa en lugar de suponerlo, como hizo ChatGPT. |
| 7 | Consultar disponibilidad del viernes a la mañana, el cargo según la política (<24 h) y el estado del campo visual | **[Regla]** | Son las fuentes de verdad que le faltaron al modelo en A.2; el LLM no las toca. |
| 8 | Redactar la respuesta: horarios libres reales, cargo según política, estado del estudio | **[LLM]** | Redactar en lenguaje natural y amable es tarea del LLM, pero solo con los datos del paso 7, inyectados en el prompt. |
| 9 | Verificar que cada horario y monto del texto coincida con lo que devolvió el backend | **[Regla]** | Guardrail contra la alucinación de A.2: si el texto menciona un dato que no vino de la base, se reemplaza por una plantilla fija. |
| 10 | Interpretar la elección del paciente ("dale, el de las 9 y media") | **[LLM]** | Respuesta libre, que se mapea a una de las opciones ofrecidas; nunca a un horario nuevo. |
| 11 | Pedir confirmación explícita: "¿Confirmás el cambio al viernes 06/11 09:30? Respondé SÍ" | **[Regla]** | La operación escribe en la agenda; solo un "SÍ" exacto la habilita. |
| 12 | Ejecutar `modificar_turno`: revalidar disponibilidad, liberar el jueves, ocupar el viernes, registrar log | **[Regla]** | Transacción atómica y auditable; el LLM no escribe en la base. |
| 13 | Enviar el comprobante con fecha, hora, profesional y cargo | **[Regla]** | Plantilla fija con datos de la base: un comprobante no puede tener variaciones. |
| — | Desvío: consulta médica ("¿es grave?"), identidad fallida o baja confianza | **[Regla]** | `derivar_a_humano` con el pedido ya resumido para la administrativa. |

**Balance:** de 13 pasos, 3 son LLM (interpretar, redactar, interpretar la elección) y 10 son reglas. El LLM está solo donde hay lenguaje natural; todo lo que lee o escribe datos es código.

### B.3 — Alcance del MVP

| Sección | Contenido |
|---|---|
| **Capacidades incluidas** | 1. Interpretar mensajes libres de pacientes y clasificarlos en 5 intenciones (`consultar_disponibilidad`, `crear_turno`, `modificar_turno`, `cancelar_turno`, `consultar_resultado`) + `otra`, extrayendo entidades en un JSON validado, incluso cuando hay varias intenciones en un mismo mensaje.<br>2. Validar la identidad con DNI + fecha de nacimiento contra un padrón ficticio.<br>3. Consultar disponibilidad, crear, modificar y cancelar turnos sobre una agenda simulada (archivo JSON o SQLite), con confirmación explícita antes de escribir.<br>4. Informar el **estado** de un estudio (pendiente / listo) y el cargo por reprogramación según una política cargada en la base.<br>5. Derivar a una persona cuando hay una consulta médica, la identidad falla o el mensaje no encaja en ninguna intención. |
| **Explícitamente fuera de alcance** | - Integración real con WhatsApp: el MVP es por consola o chat web.<br>- Conexión con el sistema de turnos real de la clínica y con datos reales de pacientes.<br>- Entregar o interpretar resultados médicos: solo se informa si están listos.<br>- Verificar coberturas con la obra social (la consulta `consultar_cobertura` queda para una versión posterior).<br>- Leer imágenes de órdenes o credenciales (OCR).<br>- Cobros y pagos.<br>- Recordatorios automáticos y lista de espera. |
| **Criterios de éxito** | **Principal:** ≥ 90% de intenciones y entidades bien extraídas sobre un set de prueba de 50 mensajes realistas escritos por el equipo, incluyendo mensajes con dos intenciones y fechas relativas.<br>**De seguridad:** 0 operaciones de escritura sin confirmación explícita y 0 datos (horarios, montos, estados) en la respuesta que no provengan de la base. Se mide con el mismo set de 50 mensajes, contrastando cada respuesta contra la base. |

### B.4 — Matriz de Mapeo de Intenciones

| Entrada del usuario (caos) | Intención (LLM) | Acción de backend (determinista) | Riesgo | Justificación del riesgo |
|---|---|---|---|---|
| "¿Hay lugar con la Dra. López el viernes a la mañana?" | `consultar_disponibilidad` | `consultar_disponibilidad(profesional="López", fecha=06/11, franja=08–13)` → devuelve los horarios libres de la agenda | **BAJO** | Solo lee y no expone datos personales. Si la intención se clasifica mal, el paciente recibe horarios que no pidió y re-pregunta: no hay daño. |
| "Quiero sacar turno para un fondo de ojo, tengo OSDE" | `crear_turno` | Validar identidad → `consultar_disponibilidad` → confirmación "SÍ" → `crear_turno(dni, profesional, fecha, hora, prestación)` | **ALTO** | Escribe en la agenda: ocupa un horario que deja de estar disponible para otro paciente. Un error de fecha o de profesional genera un turno fantasma o un paciente que se presenta y no figura. |
| "Pasame el turno del jueves al viernes a la mañana" | `modificar_turno` | Validar identidad → verificar turno existente → `consultar_disponibilidad` → calcular cargo según política (<24 h) → confirmación "SÍ" → `modificar_turno(id_turno, nueva_fecha, nueva_hora)` | **ALTO** | Escribe dos veces (libera un horario y ocupa otro) y tiene **consecuencia financiera**: puede generar el cargo por reprogramación. Es la operación en la que Gemini inventó en A.2 una política de $5.000 y otra gratuita: el cargo lo decide la base, nunca el LLM. |
| "Cancelá mi turno de mañana, no puedo ir" | `cancelar_turno` | Validar identidad → verificar turno existente → informar cargo si corresponde → confirmación "SÍ" → `cancelar_turno(id_turno)` | **ALTO** | Escritura irreversible para el paciente: el horario se libera y puede ocuparlo otro. Cancelar el turno equivocado deja sin atención a alguien que sí iba a ir, y puede tener cargo según la política. |
| "¿Ya está mi campo visual del lunes?" | `consultar_resultado` | Validar identidad → `consultar_estado_estudio(dni, "campo visual")` → devuelve solo el estado (pendiente / listo) | **MEDIO** | Solo lee, pero son **datos de salud**: informar el estado a quien no es el paciente viola la privacidad (Ley 25.326). Se baja a controlable porque la identidad se valida antes y nunca se entrega ni interpreta el informe. |
| "Me arde mucho el ojo desde ayer, ¿es grave?" | `otra` (consulta médica) | `derivar_a_humano(motivo="consulta_clinica", resumen)` sin respuesta automática | **ALTO** | No escribe ni lee nada, pero responder sería dar una opinión médica y una respuesta equivocada puede afectar la salud del paciente. Por eso la única acción permitida es derivar. |

> **Criterio aplicado:** seguimos la regla de oro (ALTO cuando la operación escribe o tiene consecuencia financiera, BAJO cuando solo lee) con dos excepciones justificadas: `consultar_resultado` sube a MEDIO porque, aunque solo lee, expone datos de salud; y la consulta médica es ALTO por el riesgo para el paciente, aunque no toca la base.

### B.5 — Hipótesis más riesgosa

Suponemos que un LLM puede extraer de forma confiable (≥ 90%) la intención, el DNI, la profesional y la fecha de mensajes coloquiales con varios pedidos y fechas relativas como "el jueves" o "a la mañana"; si no lo logra, todas las reglas deterministas posteriores validan y ejecutan sobre datos mal interpretados.
