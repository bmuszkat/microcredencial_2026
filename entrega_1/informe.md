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
