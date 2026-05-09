# SCOPE — Mapa de Capas: Lo Demostrado, Lo Investigado, Lo Hipotético

**AOTS6 — Ontological Toroidal System**
**Alfredo Jhovany Alfaro García**
draft-alfaro-aots6-01 · Marzo 2026

---

## La honestidad como fortaleza

Un sistema que sabe exactamente qué ha demostrado y qué está
investigando es más confiable que uno que confunde ambos. Este
documento establece la frontera con precisión.

---

## Capa 1 — DEMOSTRADO (ejecutable, reproducible, verificado)

Cualquier persona puede verificar esto clonando el repositorio
y ejecutando `python3 aots6_demo.py`:

- La métrica toroidal d(a,b) en T⁶ es matemáticamente correcta
- La función I(v) = H(v || context || t) es determinista y sensible
- El grafo ontológico mantiene integridad bajo mutaciones
- La restricción de consistencia Δ=0 ⟺ identidad invariante
- Los mensajes de protocolo son resistentes a manipulación
- n peers se descubren y verifican en red distribuida
- El historial de estados es monotónico e inyectivo

**Evidencia**: 7/7 tests PASS, código público, reproducible en < 2ms.

---

## Capa 2 — EN DESARROLLO (especificado, parcialmente implementado)

- Transporte TCP/QUIC para el protocolo (bus actual: in-process)
- Resistencia Sybil en INIT (requiere PoW o stake layer)
- Verificación formal en TLA+ o Coq de la consistencia
- Gossip-based peer discovery (actualmente: manual INIT)

**Estado**: especificado en el paper, pendiente de implementación.

---

## Capa 3 — INVESTIGACIÓN ACTIVA (hipótesis formalizadas, en estudio)

- Aplicación de T⁶ a modelos cosmológicos no-FLRW
- Correspondencia entre distancia toroidal y distancia semántica
  en espacios de embedding de modelos de lenguaje
- H₀ toroidal como extensión de la constante de Hubble
- Mapeo de dimensiones T⁶ a dimensiones de compactificación
  en teorías de cuerdas

**Estado**: hipótesis con fundamento matemático, sin verificación
experimental. Se investigan, no se afirman como demostradas.

---

## Capa 4 — EXPLORACIÓN CONCEPTUAL (ideas en desarrollo formal)

- Aplicación de AOTS6 a los Problemas Millennium vía
  exploración computacional de sus estructuras
- Correspondencia entre la restricción de consistencia AOTS6
  y teoremas de punto fijo en topología
- AOTS6 como framework para identidad digital soberana a escala

**Estado**: ideas con potencial, requieren desarrollo matemático
formal antes de poder hacer afirmaciones sustantivas.

---

## La frontera importa

La distinción entre capas no es debilidad — es precisión.

Newton no confundió la ley de gravitación (Capa 1 de su tiempo)
con su especulación sobre el éter (Capa 3 de su tiempo). Esa
distinción es lo que hace que sus contribuciones verificadas
sean robustas 350 años después.

AOTS6 está construido con la misma disciplina.

---

**(c) 2025-2026 Alfredo Jhovany Alfaro García — All Rights Reserved.**
