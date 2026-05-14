import subprocess
import sys
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

ROOT = Path(".").resolve()
MANIFEST = ROOT / "integrity" / "manifests" / "latest_manifest.json"
SIG_PATH = ROOT / "integrity" / "manifests" / "latest_manifest.sig"
PRIV_KEY = ROOT / "keys" / "private.pem"

def main():
    if not MANIFEST.exists() or not PRIV_KEY.exists():
        logging.error("Falta el manifiesto o la llave privada.")
        sys.exit(1)

    try:
        subprocess.run([
            "openssl", "pkeyutl", "-sign",
            "-inkey", str(PRIV_KEY),
            "-rawin", "-in", str(MANIFEST),
            "-out", str(SIG_PATH)
        ], check=True, capture_output=True)
        
        logging.info("Estado del kernel firmado exitosamente via OpenSSL.")
    except subprocess.CalledProcessError as e:
        logging.error(f"Error nativo al firmar: {e.stderr.decode()}")
        sys.exit(1)

if __name__ == "__main__":
    main()
