import subprocess
import sys
import json
from pathlib import Path

# Este script lo ejecutan los nodos externos. No contiene ciencia AOTS6.
# Solo contiene la lógica de validación de confianza cero.

STATE_FILE = Path("toroidal_state.json")
SIG_FILE = Path("toroidal_state.sig")
PUB_KEY = Path("../keys/public.pem")

def verify_sovereign_state():
    if not all(p.exists() for p in [STATE_FILE, SIG_FILE, PUB_KEY]):
        print("[-] Error: Faltan artefactos P2P para sincronización.")
        sys.exit(1)

    try:
        # Validación matemática de que el bloque vino del celular de Alfredo
        subprocess.run([
            "openssl", "pkeyutl", "-verify",
            "-pubin", "-inkey", str(PUB_KEY),
            "-rawin", "-in", str(STATE_FILE),
            "-sigfile", str(SIG_FILE)
        ], check=True, capture_output=True)
        
        with open(STATE_FILE, "r") as f:
            data = json.load(f)
            
        print("[+] RED AOTS6 SINCRONIZADA.")
        print(f"    Hash del Estado Toroidal: {data['quantum_state_hash']}")
        print("    Confianza Cero: ORIGEN VALIDADO CRIPTOGRÁFICAMENTE.")
        
    except subprocess.CalledProcessError:
        print("[!] ALERTA: Violación de integridad. Firma rechazada.")
        sys.exit(1)

if __name__ == "__main__":
    verify_sovereign_state()
