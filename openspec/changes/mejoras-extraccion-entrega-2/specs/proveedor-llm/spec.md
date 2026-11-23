# Spec Delta

## MODIFIED Requirements

### Requirement: Reintentos ante saturación
Ante una respuesta HTTP 429 o 503, el sistema SHALL reintentar hasta 3 veces, esperando lo que indique la API (header `Retry-After` o el tiempo sugerido en el mensaje de error), con un mínimo creciente de 2 s y 4 s y un máximo de 30 s. Ante errores de autenticación o de pedido (400, 401, 403) MUST NOT reintentar.

#### Scenario: Límite de uso transitorio
- **WHEN** la primera llamada devuelve 429 y la segunda responde bien
- **THEN** el sistema devuelve la respuesta de la segunda llamada

#### Scenario: La API indica cuánto esperar
- **WHEN** la API devuelve 429 con `Retry-After: 9.5` o con el mensaje "Please try again in 13.62s"
- **THEN** el sistema espera 9,5 s o 13,62 s respectivamente antes de reintentar

#### Scenario: Espera fuera de rango
- **WHEN** la API pide esperar 0,1 s o 999 s
- **THEN** el sistema espera al menos 2 s y como máximo 30 s

#### Scenario: Key inválida
- **WHEN** la API devuelve 401
- **THEN** el sistema no reintenta y el error se informa como COMUNICACION
