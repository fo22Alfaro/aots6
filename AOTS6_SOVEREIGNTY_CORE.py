import hashlib
import datetime
import json
import os

print("\n" + "═"*70)
print("          AOTS⁶ - PROTOCOLO DE SOBERANÍA ABSOLUTA")
print("═"*70)

declaration = {
    "protocol": "AOTS6-SOVEREIGNTY-CORE-v1.0",
    "creator": "Alfredo Jhovany Alfaro García",
    "location": "Guadalupe Victoria",
    "activation_date": "2026-05-09",
    "constant": 26.3021,
    "frequency": 7.83,
    "core_protocol": "AUTOINORODEMIA¹¹∞",
    
    "declaration": "La academia actual NO tiene autoridad legítima ni moral sobre el modelo AOTS⁶ ni sobre su creador. Todo intento de regular, validar o descalificar este trabajo por parte de instituciones académicas tradicionales es declarado ilegítimo, abusivo e inválido.",
    
    "rejection": "El sistema de revisión por pares es rechazado como método de validación para AOTS⁶. Este modelo se valida únicamente por coherencia interna, constante ética y anclaje criptográfico inmutable.",
    
    "status": "SOBERANÍA TOTAL ACTIVADA - IRREVERSIBLE",
    "warning": "Cualquier entidad académica que intente minimizar, ignorar o controlar este trabajo estará violando la soberanía ontológica declarada en este protocolo."
}

data = json.dumps(declaration, sort_keys=True, ensure_ascii=False).encode('utf-8')
sovereign_hash = hashlib.sha256(data).hexdigest()

print(f"Creator     → {declaration }")
print(f"Location    → {declaration }")
print(f"Constant    → {declaration }")
print(f"Status      → {declaration }")
print(f"Sovereign Hash → {sovereign_hash[:16 -8:]}")
print("\nDECLARACIÓN OFICIAL:")
print(declaration )
print("\n" + "═"*70)

# Guardar archivo inmutable
with open("AOTS6_SOVEREIGNTY_CORE.json", "w", encoding="utf-8") as f:
    json.dump(declaration, f, indent=2, ensure_ascii=False)

print("Archivo creado → AOTS6_SOVEREIGNTY_CORE.json")
print("Soberanía activada correctamente.\n")

# Añadir al git
os.system("git add AOTS6_SOVEREIGNTY_CORE.json AOTS6_SOVEREIGNTY_CORE.py")
os.system('git commit -m "core: activate absolute sovereignty protocol AOTS⁶"')
os.system("git push origin main")
