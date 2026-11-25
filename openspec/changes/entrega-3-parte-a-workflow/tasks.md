# Tasks

## 1. Datos ficticios y sensores

- [x] 1.1 Crear `entrega_3/conftest.py` (agrega `entrega_2` y `entrega_3` al `sys.path`) y los datos de `entrega_3/datos/` (design D8): `padron.json`, `agenda.json` con `fecha_referencia`, `estudios.json` y `politica_cargos.json`, preparados para los 8 casos de D12. Agregar `entrega_3/tests/test_datos.py`: referencias válidas, ningún turno libre y reservado a la vez, Juan Pérez con su turno y su estudio, un turno a menos de 24 h y un paciente con dos turnos con la misma profesional. Verificar con `python -m pytest entrega_3`
- [x] 1.2 Crear `entrega_3/herramientas.py` con las consultas de solo lectura (spec `agenda-clinica`): buscar paciente, turnos futuros, buscar estudio (sin mayúsculas ni tildes), turnos libres por rango, franja y profesional (por apellido), y política de cargos. Agregar `tests/test_herramientas.py` con un test por escenario de la spec y uno que confirme que ninguna consulta modifica los datos. Verificar con `pytest`

## 2. Reglas del dominio

- [ ] 2.1 En `entrega_3/reglas.py`, implementar la anonimización del DNI (design D6): un candidato → texto con `[DNI]` y el valor normalizado; ninguno → sin cambios; dos o más → candidatos múltiples. Agregar `tests/test_reglas.py` con DNI con y sin puntos, un teléfono de 10 dígitos que no se toma, dos DNI distintos, el mismo DNI repetido y "30.123" sin detectar. Verificar con `pytest`
- [ ] 2.2 En `reglas.py`, implementar la conversión de fechas relativas (design D7) con la fecha de referencia como parámetro: días de la semana, hoy / mañana / pasado mañana, "la semana que viene", `dd/mm`, franjas, hora explícita y "no se entiende". Agregar tests de cada forma, entre ellos "viernes a la mañana" → 27/11 08:00–13:00 (no el día siguiente), "jueves a las 15 hs" → 26/11 15:00 y "cuando pueda" → no se entiende. Verificar con `pytest`
- [ ] 2.3 En `reglas.py`, implementar el cálculo del cargo (< 24 h, con monto y umbral leídos de la política) y la prioridad de estados para el estado global (design D5). Agregar tests: 25/11 09:00 → cargo, 26/11 15:00 → sin cargo, exactamente 24 h → sin cargo, y combinaciones de estados → el más restrictivo. Verificar con `pytest`

## 3. Prompt de extracción v3

- [ ] 3.1 Escribir `entrega_3/prompts/extraccion_v3.txt` (design D14) y `tests/test_prompt_v3.py`: cada ejemplo cumple el contrato v2, ningún ejemplo coincide con el set de evaluación ni con el lote de la E2, las intenciones del prompt son exactamente las del contrato y ningún ejemplo trae un DNI en claro. Verificar con `pytest`

## 4. Respuesta al paciente

- [ ] 4.1 Crear `entrega_3/redactor.py` y `entrega_3/prompts/redaccion_v1.txt` (design D10): contrato de la salida `{"respuesta"}`, llamada al LLM inyectado con los datos validados y plantillas por estado (acuse de revisión, preguntas pendientes, derivación, fuera de alcance y respaldo cuando falla la redacción). Agregar `tests/test_redactor.py`: el redactor no recibe el mensaje original, una salida fuera de contrato o un error de comunicación usan la plantilla y las plantillas no exponen motivos internos. Verificar con `pytest`
- [ ] 4.2 En `redactor.py`, implementar el guardrail de horarios, fechas, montos y DNI (design D11). Agregar tests con los escenarios de la spec `respuesta-paciente`: un monto inventado, un horario inventado, un texto respaldado y el DNI en el texto, más las formas "15 hs", "15:00", "a las 9", "$12.000" y "$ 12000". Verificar con `pytest`

## 5. Lote de casos (antes de cualquier corrida real)

- [ ] 5.1 Escribir `entrega_3/datos/lote_workflow.json` con los 8 casos de design D12: mensaje, estado global esperado, estado esperado por intención, por qué y respuestas simuladas para correr sin API. Agregar un test de estructura (8 casos, ids únicos, estados válidos, al menos un `COMPLETADO` y un `REVISION_HUMANA`). Verificar con `pytest` y **con tu revisión antes del commit**. Este commit tiene que quedar antes de la primera corrida real

## 6. Workflow

- [ ] 6.1 Crear `entrega_3/workflow.py` con la traza (número, nombre, tipo y resultado) y los pasos de mensaje 0 a 5 (design D3 y D4): anonimizar, extraer con v3, validar y reponer el DNI, enrutar, decidir si hace falta identificar al paciente e identificarlo. El LLM es inyectable (D13). Agregar `tests/test_workflow.py` con un LLM falso: un JSON fuera de contrato, un error de comunicación, un pedido sin DNI, un DNI fuera del padrón, dos candidatos a DNI y la verificación de que el LLM nunca recibe el DNI. Verificar con `pytest`
- [ ] 6.2 Agregar a `workflow.py` los pasos 6 a 9 por intención y el estado global: fechas, turno, estudio y disponibilidad, cargo, `PENDIENTE_CONFIRMACION`, `DERIVADO`, `otra` y pedido contradictorio. Agregar tests de cada condición de la tabla de puntos de control (design D4). Verificar con `pytest`
- [ ] 6.3 Agregar a `workflow.py` los pasos 10 y 11 (redactor y guardrail), el punto de entrada por consola (lote completo o un mensaje suelto, modo simulación sin key y pausa entre llamadas) y un test por caso del lote en modo simulación que compare el estado global y el de cada intención con el esperado. Verificar con `pytest` y con `python entrega_3/workflow.py` sin key (simulación)

## 7. Corrida real

- [ ] 7.1 Correr `python entrega_3/workflow.py` contra Groq y guardar la salida en `entrega_3/evidencia/workflow_groq_<fecha>.txt` (con `org_[OCULTO]` si aparece). Verificar que estén los 8 casos con su traza, y registrar cuáles dieron el estado esperado y cuáles no, sin modificar el lote

## 8. Documentación

- [ ] 8.1 Escribir `entrega_3/informe.md`, Parte A: tabla de pasos (Regla / LLM / Sensor / Humano) con su origen en el journey, tabla de puntos de control, diagrama Mermaid (A.2) con LLM, reglas, sensores y estados diferenciados, resultados del lote (A.3) con la traza del caso que se completa y del que se detiene, simplificaciones declaradas (identidad por DNI, `PENDIENTE` mixto) y observaciones de la corrida real. Verificar que cada número y estado coincida con el archivo de evidencia
- [ ] 8.2 Actualizar el `README.md` de la raíz: fila de la Entrega 3 en la tabla de entregas, comandos (`python entrega_3/workflow.py`, `python -m pytest entrega_3`) y la carpeta `entrega_3/` en el árbol. Verificar que los comandos documentados corren tal cual desde la raíz

## 9. Verificación final

- [ ] 9.1 Correr `python -m pytest` (E2 y E3 en verde), `python entrega_2/app.py` en simulación (la E2 no se rompió), buscar keys en el historial (`gsk_`, `sk-`, `AIza`, `sk-ant-`, `org_`) y correr `openspec validate entrega-3-parte-a-workflow --strict`

## Workflow follow-up

- Revisión del usuario y push.
- Archivar el cambio con `/opsx:archive` para sincronizar las specs vigentes.
