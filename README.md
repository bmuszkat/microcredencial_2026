microcredencial
# Asistente Inteligente de Atención al Paciente – Clínica Oftalmológica

## 1. Descripción del negocio

El proyecto está orientado a una **clínica especializada en oftalmología**, dedicada a la atención de pacientes, consultas oftalmológicas y realización de estudios de diagnóstico visual.

La clínica recibe diariamente un alto volumen de consultas a través de WhatsApp, correo electrónico y teléfono.

Las principales gestiones administrativas son:

- **Creación de turnos:** solicitud de turnos para consultas y estudios oftalmológicos.
- **Modificación de turnos:** reprogramación de fechas y horarios.
- **Cancelación de turnos:** anulación de reservas existentes.
- **Consulta de resultados médicos:** verificación de disponibilidad de resultados de estudios oftalmológicos.

## 2. Problemática identificada

Actualmente, gran parte de estas consultas es gestionada manualmente por el personal administrativo.

Esto genera las siguientes dificultades:

- **Alto volumen de consultas repetitivas:** los pacientes realizan constantemente solicitudes similares.
- **Sobrecarga administrativa:** el personal dedica gran parte de su tiempo a gestionar turnos y responder consultas sobre resultados.
- **Demoras en la atención:** durante los horarios de mayor demanda, los tiempos de respuesta aumentan.
- **Atención limitada:** los pacientes no pueden resolver sus solicitudes fuera del horario administrativo.
- **Posibles errores manuales:** pueden producirse equivocaciones al crear, modificar o cancelar turnos.

## 3. Solución propuesta

Se propone desarrollar un **agente de Inteligencia Artificial** que automatice la atención administrativa de la clínica mediante conversaciones en lenguaje natural.

El asistente podrá identificar las necesidades del paciente y ejecutar acciones utilizando herramientas conectadas al sistema de gestión.

### Funcionalidades principales

**Gestión de turnos**
- Consultar disponibilidad de profesionales.
- Crear nuevos turnos.
- Modificar fechas y horarios.
- Cancelar turnos existentes.
- Confirmar las operaciones realizadas.

**Consulta de resultados médicos**
- Identificar al paciente mediante un proceso de validación.
- Consultar el estado de sus estudios oftalmológicos.
- Informar si los resultados están disponibles.
- Facilitar el acceso seguro a los resultados publicados.

El agente no realizará diagnósticos ni interpretará resultados médicos.

## 4. Implementación inicial (MVP)

Se desarrollará un prototipo en Python que simule el funcionamiento del asistente inteligente.

El MVP incluirá:

1. **Modelo de IA:** interpretación de mensajes y detección de la intención del paciente.
2. **Sistema de turnos simulado:** almacenamiento de profesionales, horarios y reservas.
3. **Herramientas:** funciones para crear, modificar, cancelar y consultar turnos.
4. **Resultados médicos simulados:** consulta del estado de disponibilidad de estudios.
5. **Reglas de negocio:** validación de identidad, disponibilidad y confirmación de operaciones.
6. **Interfaz conversacional:** interacción entre el paciente y el agente.

Se utilizarán datos ficticios para evitar el tratamiento de información médica sensible durante las pruebas.

## 5. Modelo conceptual de 6 piezas

| Componente | Aplicación |
|---|---|
| **Usuario** | Pacientes de la clínica oftalmológica |
| **Datos** | Mensajes, DNI, turnos, agendas y estado de estudios |
| **Modelo** | LLM para interpretar solicitudes |
| **Herramientas** | Crear, modificar, cancelar turnos y consultar resultados |
| **Reglas** | Validación de identidad, disponibilidad y privacidad |
| **Salida** | Turnos gestionados y estado de resultados informado |

## 6. Beneficios esperados

- Reducir la carga de trabajo del personal administrativo.
- Disminuir los tiempos de respuesta.
- Brindar atención automatizada las 24 horas.
- Reducir errores en la gestión de turnos.
- Mejorar la experiencia de los pacientes.
- Permitir que el personal se concentre en consultas que requieren atención humana.

## 7. Objetivo del proyecto

**Automatizar la gestión de turnos y las consultas sobre disponibilidad de resultados médicos de una clínica oftalmológica mediante un agente de Inteligencia Artificial**, mejorando la eficiencia administrativa y ofreciendo una atención más rápida y accesible para los pacientes.