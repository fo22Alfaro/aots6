import subprocess
import sys
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

ROOT = Path(".").resolve()
MANIFEST = ROOT / "integrity" / "manifests" / "latest_manifest.json"
SIG_PATH = ROOT / "integrity" / "manifests" / "latest_manifest.sig"
PUB_KEY = ROOT / "keys" / "public.pem"

def main():
    if not all(p.exists() for p in [MANIFEST, SIG_PATH, PUB_KEY]):
        logging.error("Artefactos de integridad incompletos.")
        sys.exit(1)

    try:
        subprocess.run([
            "openssl", "pkeyutl", "-verify",
            "-pubin", "-inkey", str(PUB_KEY),
            "-rawin", "-in", str(MANIFEST),
            "-sigfile", str(SIG_PATH)
        ], check=True, capture_output=True)
        
        logging.info("Validacion criptografica: SOBERANIA E INTEGRIDAD CONFIRMADAS.")
    except subprocess.CalledProcessError:
        logging.critical("VIOLACION DE INTEGRIDAD DETECTADA.")
        sys.exit(1)

if __name__ == "__main__":
    main()
