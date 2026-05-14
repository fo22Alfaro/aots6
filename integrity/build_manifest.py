import hashlib
import json
import logging
from pathlib import Path
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

ROOT = Path(".").resolve()
EXCLUDED_DIRS = {".git", "__pycache__", "snapshots", "keys"}
MANIFEST_DIR = ROOT / "integrity" / "manifests"

def hash_file_worker(filepath: Path) -> dict:
    try:
        sha256 = hashlib.sha256()
        sha3 = hashlib.sha3_512()
        
        with open(filepath, "rb") as f:
            while chunk := f.read(65536): 
                sha256.update(chunk)
                sha3.update(chunk)
                
        return {
            "path": str(filepath.relative_to(ROOT)),
            "sha256": sha256.hexdigest(),
            "sha3_512": sha3.hexdigest(),
            "size_bytes": filepath.stat().st_size,
            "modified": datetime.fromtimestamp(filepath.stat().st_mtime, tz=timezone.utc).isoformat()
        }
    except Exception as e:
        return None

def main():
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    files_to_hash = [
        f for f in ROOT.rglob("*") 
        if f.is_file() and not any(ex in f.parts for ex in EXCLUDED_DIRS)
    ]

    manifest_data = {
        "metadata": {
            "kernel": "AOTS6-PQ-TERMUX",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "file_count": len(files_to_hash)
        },
        "files": {}
    }

    with ThreadPoolExecutor() as executor:
        for res in executor.map(hash_file_worker, files_to_hash):
            if res:
                manifest_data["files"][res.pop("path")] = res

    out_path = MANIFEST_DIR / "latest_manifest.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2, sort_keys=True)

    logging.info("Manifiesto generado de forma nativa.")

if __name__ == "__main__":
    main()
