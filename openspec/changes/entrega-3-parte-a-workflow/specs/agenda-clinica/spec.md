# Spec Delta

## Purpose

Simula el backend de la clínica (padrón de pacientes, agenda de turnos, estudios y política de cargos) con datos ficticios y ofrece consultas de solo lectura sobre él, que son la fuente de verdad contra la que se valida todo lo que interpreta el LLM.

## ADDED Requirements

### Requirement: Datos ficticios y consistentes
El sistema SHALL incluir datos ficticios del backend: un padrón (DNI, nombre, fecha de nacimiento, obra social), una agenda (profesionales con especialidad y sede, turnos reservados por DNI y turnos libres), estudios por paciente (estudio, fecha de realización, estado) y una política de cargos. Cada referencia entre ellos MUST ser válida.

#### Scenario: Turno reservado de un paciente
- **WHEN** se revisa un turno reservado de la agenda
- **THEN** su DNI existe en el padrón y su profesional existe en la lista de profesionales

#### Scenario: Turno libre y reservado a la vez
- **WHEN** se comparan los turnos libres con los reservados
- **THEN** ningún profesional tiene el mismo día y hora libre y reservado

### Requirement: Fecha de referencia
Los datos SHALL definir la fecha y hora de referencia que el sistema usa como "ahora". Los turnos anteriores a esa fecha MUST considerarse pasados.

#### Scenario: Turno pasado
- **WHEN** la referencia es el 24/11/2026 a las 10:00 y un paciente tiene un turno el 20/11/2026
- **THEN** ese turno no aparece entre sus turnos futuros

### Requirement: Consultas de solo lectura
El sistema SHALL ofrecer consultas para buscar un paciente por DNI, listar sus turnos futuros, buscar un estudio del paciente por nombre y listar los turnos libres en un rango de fechas y franja horaria, opcionalmente filtrados por profesional. Ninguna consulta MUST modificar los datos.

#### Scenario: Paciente inexistente
- **WHEN** se busca un DNI que no está en el padrón
- **THEN** la consulta indica que no existe, sin error

#### Scenario: Estudio por nombre aproximado
- **WHEN** el paciente tiene registrado "campo visual" y se busca "Campo Visual" o "el campo visual"
- **THEN** la consulta encuentra el estudio, sin distinguir mayúsculas ni tildes

#### Scenario: Turnos libres filtrados
- **WHEN** se piden turnos libres el viernes 27/11 entre las 08:00 y las 13:00 con la Dra. López
- **THEN** solo se devuelven turnos libres de esa profesional dentro de ese rango, ordenados por fecha y hora

#### Scenario: Profesional mencionado por apellido
- **WHEN** se filtra por "la doctora Lopez" o "López"
- **THEN** coincide con la profesional registrada como "Dra. López"

### Requirement: Política de cargos en datos
El monto del cargo por reprogramar o cancelar con menos de 24 horas y el umbral de horas MUST leerse de los datos de la política, no estar escritos en el código.

#### Scenario: Cambio de política
- **WHEN** se modifica el monto en el archivo de la política
- **THEN** el cargo calculado cambia sin tocar el código
