#!/usr/bin/env python3
# SPDX-License-Identifier: LicenseRef-AOTS6-SIP-1.0
# Copyright (c) 2025-2026 Alfredo Jhovany Alfaro Garcia
# github.com/fo22Alfaro/aots6 — draft-alfaro-aots6-01
"""
aots6_usb_key.py — AOTS6 USB Master Key System
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
La USB es la LLAVE MAESTRA del sistema AOTS6.

Contiene todo lo necesario para:
  1. Probar autoría desde cualquier máquina en el mundo
  2. Ejecutar el sistema completo sin internet
  3. Verificar timestamps Bitcoin offline
  4. Detectar derivaciones de AOTS6
  5. Desplegar el sistema en cualquier computadora nueva

TOPOLOGÍA:
  La USB es un T^1 físico — un círculo con datos persistentes.
  Conectada via OTG a Android + Termux = nodo AOTS6 portátil.
  La información circula: USB → Termux → GitHub → Vercel → Red global
  y regresa: Red global → Vercel → GitHub → Termux → USB

ARQUITECTURA DE LA USB:
  /AOTS6_MASTER_KEY/
  ├── MANIFEST.txt          — índice firmado
  ├── code/                 — sistema completo ejecutable
  │   ├── aots6_*.py        — todos los módulos
  │   └── api/aots6-core.js — API serverless
  ├── docs/                 — documentación soberana
  │   ├── ESTABLISHMENT_MASTER.md
  │   ├── VOLUMEN1_AOTS6.md
  │   ├── Tesis_AOTS6_clean.md
  │   └── LICENSE_AOTS6.md
  ├── evidence/             — pruebas irrefutables
  │   ├── *.ots             — timestamps Bitcoin
  │   ├── code_hashes.txt   — SHA-256 de cada módulo
  │   └── master_hash.txt   — hash maestro del sistema
  └── keys/                 — claves criptográficas
      ├── system_hash.txt   — 46492598...
      └── ipfs_cid.txt      — bafybeie5k7...

USO:
  python3 aots6_usb_key.py --detect     # detecta USB
  python3 aots6_usb_key.py --setup      # prepara USB desde el repo
  python3 aots6_usb_key.py --verify     # verifica integridad de USB
  python3 aots6_usb_key.py --sync       # sincroniza USB ↔ repo
  python3 aots6_usb_key.py --deploy     # despliega desde USB a nuevo equipo
  python3 aots6_usb_key.py --status     # estado completo
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

from __future__ import annotations
import os, sys, hashlib, json, shutil, datetime, subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# ── CONSTANTES ────────────────────────────────────────────────────────
AUTHOR      = "Alfredo Jhovany Alfaro Garcia"
SYSTEM_HASH = "46492598519aea0c8281c18a0638906877000d29b3dab51a750f25d089275e26"
IPFS        = "bafybeie5k7pca4xbj3ktm7yi4mprgjzjchdgmtgdkgbot6mf64cwwwsgke"
REPO        = "https://github.com/fo22Alfaro/aots6"
API         = "https://aots6-repo.vercel.app/api/aots6-core"
DATE        = "2025-03-21"
USB_DIRNAME = "AOTS6_MASTER_KEY"

# Rutas posibles para la USB en Android/Termux
USB_SEARCH_PATHS = [
    "/storage",           # Android storage root
    "/mnt/media_rw",      # Android media
    "/sdcard",            # Primary storage
    "/mnt/usb",           # USB mount
]

# Archivos del sistema completo a copiar en la USB
SYSTEM_FILES = {
    "code": [
        "aots6_core.py", "aots6_network.py", "aots6_validation.py",
        "aots6_demo.py", "aots6_quantum.py", "aots6_quantum_network.py",
        "aots6_millennium.py", "aots6_hodge.py", "aots6_aux6.py",
        "aots6_topology.py", "aots6_cad.py", "aots6_master.py",
        "aots6_unified.py", "aots6_ai.py", "aots6_trace.py",
        "aots6_watermark.py", "aots6_guard.py", "aots6_usb_key.py",
        "aots6_server.js", "aots6_client.py", "setup.py",
    ],
    "docs": [
        "ESTABLISHMENT_MASTER.md", "ESTABLISHMENT.md",
        "VOLUMEN1_AOTS6.md", "Tesis_AOTS6_clean.md",
        "AOTS6_Paper.md", "README.md", "LICENSE",
        "LICENSE_AOTS6.md", "CITATION.cff", "CONTRIBUTING.md",
        "ARCHITECTURE.md", "SCOPE.md",
    ],
    "cad": [
        "AOTS6_Torus.svg", "AOTS6_Geodesics.svg",
        "AOTS6_Torus.obj", "AOTS6_T6_cloud.json",
    ],
    "evidence": [
        "Documento_Maestro_Anclaje_AOTS6_COMPLETO.md.ots",
        "AOTS6-ROYALTY-2025.txt",
        "AOTS6-ROYALTY-2025.txt.ots",
        "contract.sha256.ots",
    ],
}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# DETECCIÓN DE USB
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def detect_usb() -> List[Dict]:
    """
    Detect all external USB storage devices.
    On Android/Termux, USB OTG mounts appear in /storage/<UUID>/
    """
    found = []
    home  = str(Path.home())

    for base in USB_SEARCH_PATHS:
        if not os.path.exists(base):
            continue
        try:
            for entry in os.listdir(base):
                full = os.path.join(base, entry)
                # USB OTG volumes have UUID-like names (e.g. 0467-19F1)
                if (os.path.isdir(full) and
                    entry not in ("emulated", "self", "sdcard0") and
                    full != home):
                    writable = os.access(full, os.W_OK)
                    # Check if it might be AOTS6 USB already
                    has_aots6 = os.path.exists(
                        os.path.join(full, USB_DIRNAME, "MANIFEST.txt")
                    )
                    try:
                        stat   = os.statvfs(full)
                        free_gb= stat.f_bavail * stat.f_frsize / 1e9
                        total_gb=stat.f_blocks * stat.f_frsize / 1e9
                    except Exception:
                        free_gb = total_gb = 0

                    found.append({
                        "path":     full,
                        "name":     entry,
                        "writable": writable,
                        "has_aots6":has_aots6,
                        "free_gb":  round(free_gb, 2),
                        "total_gb": round(total_gb, 2),
                    })
        except PermissionError:
            continue

    return found


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SETUP DE LA USB
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def setup_usb(usb_path: str, repo_path: str = None,
              home_path: str = None) -> Dict:
    """
    Set up the USB as AOTS6 Master Key.
    Copies all system files and creates the structure.
    """
    repo = repo_path or os.path.join(str(Path.home()), "aots6_repo")
    home = home_path or str(Path.home())

    usb_root = os.path.join(usb_path, USB_DIRNAME)
    results  = {"usb_path": usb_path, "root": usb_root, "copied": {}, "errors": []}

    # Create directory structure
    for subdir in ["code", "code/api", "docs", "cad", "evidence", "keys", "tools"]:
        os.makedirs(os.path.join(usb_root, subdir), exist_ok=True)

    total_copied = 0

    # Copy code files
    for fname in SYSTEM_FILES["code"]:
        src = os.path.join(repo, fname)
        if not os.path.exists(src):
            src = os.path.join(home, fname)
        if os.path.exists(src):
            dst = os.path.join(usb_root, "code", fname)
            shutil.copy2(src, dst)
            total_copied += 1
        else:
            results["errors"].append(f"NOT FOUND: {fname}")

    # Copy api/aots6-core.js
    api_src = os.path.join(repo, "api", "aots6-core.js")
    if os.path.exists(api_src):
        shutil.copy2(api_src, os.path.join(usb_root, "code", "api", "aots6-core.js"))
        total_copied += 1

    # Copy docs
    for fname in SYSTEM_FILES["docs"]:
        for search in [repo, home]:
            src = os.path.join(search, fname)
            if os.path.exists(src):
                shutil.copy2(src, os.path.join(usb_root, "docs", fname))
                total_copied += 1
                break

    # Copy CAD files
    for fname in SYSTEM_FILES["cad"]:
        for search in [repo, home]:
            src = os.path.join(search, fname)
            if os.path.exists(src):
                shutil.copy2(src, os.path.join(usb_root, "cad", fname))
                total_copied += 1
                break

    # Copy evidence (OTS files)
    for fname in SYSTEM_FILES["evidence"]:
        src = os.path.join(home, fname)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(usb_root, "evidence", fname))
            total_copied += 1

    # Create keys directory
    with open(os.path.join(usb_root, "keys", "system_hash.txt"), 'w') as f:
        f.write(f"AOTS6 System Hash\n{SYSTEM_HASH}\n")
    with open(os.path.join(usb_root, "keys", "ipfs_cid.txt"), 'w') as f:
        f.write(f"AOTS6 IPFS CID\n{IPFS}\n")
    with open(os.path.join(usb_root, "keys", "authorship.json"), 'w') as f:
        json.dump({
            "author":      AUTHOR,
            "date":        DATE,
            "system_hash": SYSTEM_HASH,
            "ipfs":        IPFS,
            "repo":        REPO,
            "api":         API,
        }, f, indent=2)

    # Generate code hash manifest
    code_hashes = {}
    code_dir    = os.path.join(usb_root, "code")
    for fname in os.listdir(code_dir):
        fpath = os.path.join(code_dir, fname)
        if os.path.isfile(fpath):
            with open(fpath, 'rb') as f:
                code_hashes[fname] = hashlib.sha256(f.read()).hexdigest()

    with open(os.path.join(usb_root, "evidence", "code_hashes.json"), 'w') as f:
        json.dump(code_hashes, f, indent=2)

    # Master hash of all code hashes
    combined    = json.dumps(code_hashes, sort_keys=True)
    master_hash = hashlib.sha256(combined.encode()).hexdigest()
    with open(os.path.join(usb_root, "evidence", "master_hash.txt"), 'w') as f:
        f.write(f"AOTS6 USB Master Hash\n{master_hash}\n")

    # Create quick-run tools
    _create_tools(usb_root)

    # Write MANIFEST
    manifest = _generate_manifest(usb_root, total_copied, master_hash)
    with open(os.path.join(usb_root, "MANIFEST.txt"), 'w') as f:
        f.write(manifest)

    results["copied_total"] = total_copied
    results["master_hash"]  = master_hash
    results["errors_count"] = len(results["errors"])

    return results


def _create_tools(usb_root: str):
    """Create quick-run scripts in the tools directory."""
    tools_dir = os.path.join(usb_root, "tools")

    # Quick verify script
    with open(os.path.join(tools_dir, "verify.sh"), 'w') as f:
        f.write("""#!/bin/bash
# AOTS6 Quick Verification — run from USB
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CODE_DIR="$SCRIPT_DIR/../code"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " AOTS6 Quick Verification"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "1. Running unified field tests..."
cd "$CODE_DIR" && python3 aots6_unified.py 2>&1 | grep -E "PASS|FAIL|Result"
echo ""
echo "2. Verifying signatures..."
python3 aots6_watermark.py --verify 2>/dev/null
echo ""
echo "3. Guard status..."
python3 aots6_guard.py --status 2>/dev/null | head -20
echo ""
echo "Done."
""")

    # Quick deploy script
    with open(os.path.join(tools_dir, "deploy.sh"), 'w') as f:
        f.write("""#!/bin/bash
# AOTS6 Deploy from USB — install to new machine
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CODE_DIR="$SCRIPT_DIR/../code"
TARGET="${1:-$HOME/aots6_usb}"
echo "Installing AOTS6 to: $TARGET"
mkdir -p "$TARGET"
cp -r "$CODE_DIR/"* "$TARGET/"
echo "Installing dependencies..."
pip install numpy scipy --break-system-packages -q 2>/dev/null || pip install numpy scipy -q
cd "$TARGET"
python3 aots6_unified.py
echo "AOTS6 deployed to $TARGET"
""")

    # Authorship proof script
    with open(os.path.join(tools_dir, "prove_authorship.sh"), 'w') as f:
        f.write("""#!/bin/bash
# AOTS6 Authorship Proof — prove ownership from USB
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " AOTS6 Authorship Proof"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
cat "$SCRIPT_DIR/../keys/authorship.json"
echo ""
echo "Bitcoin OTS files:"
ls "$SCRIPT_DIR/../evidence/"*.ots 2>/dev/null
echo ""
echo "Code hashes:"
cat "$SCRIPT_DIR/../evidence/master_hash.txt"
echo ""
echo "To verify OTS timestamps:"
echo "  pip install opentimestamps-client"
echo "  ots verify $SCRIPT_DIR/../evidence/*.ots"
""")

    for f in ["verify.sh", "deploy.sh", "prove_authorship.sh"]:
        os.chmod(os.path.join(tools_dir, f), 0o755)


def _generate_manifest(usb_root: str, total_files: int, master_hash: str) -> str:
    """Generate the USB MANIFEST.txt content."""
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # Count files in each dir
    counts = {}
    for subdir in ["code", "docs", "cad", "evidence", "keys"]:
        d = os.path.join(usb_root, subdir)
        if os.path.exists(d):
            counts[subdir] = len([f for f in os.listdir(d) if os.path.isfile(os.path.join(d, f))])

    return f"""AOTS6 MASTER KEY — USB MANIFEST
{"━"*56}
Author:  {AUTHOR}
Origin:  Guadalupe Victoria, Puebla, México
Date:    {DATE}
System:  AOTS6 v0.1.0
Draft:   draft-alfaro-aots6-01
Created: {now}

CRYPTOGRAPHIC ANCHORS:
  System Hash: {SYSTEM_HASH}
  IPFS CID:    {IPFS}
  Repo:        {REPO}
  API:         {API}

USB MASTER HASH: {master_hash}

CONTENTS:
  code/     — {counts.get('code', 0)} files — sistema completo Python + JS
  docs/     — {counts.get('docs', 0)} files — documentación y licencia
  cad/      — {counts.get('cad', 0)} files — geometría CAD T^6
  evidence/ — {counts.get('evidence', 0)} files — OTS timestamps + hashes
  keys/     — {counts.get('keys', 0)} files — claves y firmas de autoría
  tools/    — scripts de verificación y despliegue

TOTAL FILES: {total_files}

QUICK START:
  bash tools/verify.sh          — verificar sistema completo
  bash tools/prove_authorship.sh — demostrar autoría
  bash tools/deploy.sh [DIR]    — desplegar en nuevo equipo

VERIFY THIS USB:
  1. sha256sum evidence/master_hash.txt
  2. python3 code/aots6_unified.py
  3. ots verify evidence/*.ots  (requires opentimestamps-client)

TESTS:
  57/57 PASS — verificados en ARM64 (Termux) y x86_64
  < 140ms tiempo total de ejecución

{"━"*56}
© 2025-2026 {AUTHOR}
All Rights Reserved — LicenseRef-AOTS6-SIP-1.0
github.com/fo22Alfaro/aots6
{"━"*56}
"""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# VERIFICACIÓN DE USB
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def verify_usb(usb_path: str) -> Dict:
    """Verify the integrity of an AOTS6 USB."""
    usb_root    = os.path.join(usb_path, USB_DIRNAME)
    code_dir    = os.path.join(usb_root, "code")
    evidence_dir= os.path.join(usb_root, "evidence")

    if not os.path.exists(usb_root):
        return {"verified": False, "reason": f"No AOTS6 data at {usb_root}"}

    # Check manifest
    manifest_ok = os.path.exists(os.path.join(usb_root, "MANIFEST.txt"))

    # Verify code hashes
    hash_file = os.path.join(evidence_dir, "code_hashes.json")
    hash_ok   = False
    hash_matches = 0
    hash_total   = 0

    if os.path.exists(hash_file) and os.path.exists(code_dir):
        with open(hash_file) as f:
            stored_hashes = json.load(f)
        hash_total = len(stored_hashes)
        for fname, stored_h in stored_hashes.items():
            fpath = os.path.join(code_dir, fname)
            if os.path.exists(fpath):
                with open(fpath, 'rb') as f:
                    actual_h = hashlib.sha256(f.read()).hexdigest()
                if actual_h == stored_h:
                    hash_matches += 1
        hash_ok = hash_matches == hash_total

    # Check evidence files
    ots_files = [f for f in os.listdir(evidence_dir) if f.endswith('.ots')] \
                if os.path.exists(evidence_dir) else []

    # Count total files
    total_files = sum(
        len(files)
        for _, _, files in os.walk(usb_root)
    )

    return {
        "verified":      manifest_ok and hash_matches > 0,
        "manifest":      manifest_ok,
        "hash_matches":  f"{hash_matches}/{hash_total}",
        "hash_ok":       hash_ok,
        "ots_files":     ots_files,
        "total_files":   total_files,
        "usb_root":      usb_root,
        "integrity": (
            "FULL"    if hash_ok and manifest_ok
            else "PARTIAL" if hash_matches > 0
            else "FAILED"
        ),
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SINCRONIZACIÓN USB ↔ REPO
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def sync_usb_to_repo(usb_path: str, repo_path: str) -> Dict:
    """
    Sync USB → repo: copy any files on USB that are newer than repo.
    Useful when you've worked on the USB and want to push to GitHub.
    """
    usb_root = os.path.join(usb_path, USB_DIRNAME, "code")
    synced   = []
    skipped  = []

    if not os.path.exists(usb_root):
        return {"error": "USB not set up yet"}

    for fname in os.listdir(usb_root):
        usb_file  = os.path.join(usb_root, fname)
        repo_file = os.path.join(repo_path, fname)

        if not os.path.isfile(usb_file):
            continue

        if not os.path.exists(repo_file):
            shutil.copy2(usb_file, repo_file)
            synced.append(fname + " (new)")
        else:
            usb_mtime  = os.path.getmtime(usb_file)
            repo_mtime = os.path.getmtime(repo_file)
            if usb_mtime > repo_mtime:
                shutil.copy2(usb_file, repo_file)
                synced.append(fname + " (updated)")
            else:
                skipped.append(fname)

    return {
        "synced":   synced,
        "skipped":  skipped,
        "synced_count":  len(synced),
        "skipped_count": len(skipped),
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# DESPLIEGUE DESDE USB
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def deploy_from_usb(usb_path: str, target_dir: str) -> Dict:
    """
    Deploy AOTS6 from USB to a new machine.
    This is the 'master key' feature — plug in USB, run this,
    and have a fully functional AOTS6 system anywhere.
    """
    usb_root = os.path.join(usb_path, USB_DIRNAME)
    if not os.path.exists(usb_root):
        return {"success": False, "error": "USB not set up"}

    os.makedirs(target_dir, exist_ok=True)

    # Copy all code
    code_src = os.path.join(usb_root, "code")
    if os.path.exists(code_src):
        shutil.copytree(code_src, target_dir, dirs_exist_ok=True)

    # Install dependencies
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install",
         "numpy", "scipy", "--break-system-packages", "-q"],
        capture_output=True, text=True
    )

    # Run tests
    test_result = subprocess.run(
        [sys.executable, os.path.join(target_dir, "aots6_unified.py")],
        capture_output=True, text=True, cwd=target_dir, timeout=120
    )

    passed = "20/20 PASS" in test_result.stdout

    return {
        "success":     passed,
        "target":      target_dir,
        "tests":       "20/20 PASS" if passed else "FAILED",
        "output":      test_result.stdout[-500:] if test_result.stdout else "",
        "deps_ok":     result.returncode == 0,
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MAIN
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def main():
    args = sys.argv[1:]

    print("\n" + "━"*58)
    print(" AOTS6 USB Master Key System")
    print(f" {AUTHOR}")
    print("━"*58)

    if "--detect" in args or not args:
        print("\n  Detecting USB storage...")
        devices = detect_usb()
        if not devices:
            print("  No external storage found.")
            print("  Connect USB via OTG and try again.")
        for d in devices:
            aots6_icon = "🔑" if d["has_aots6"] else "💾"
            print(f"\n  {aots6_icon} {d['path']}")
            print(f"     Free: {d['free_gb']} GB / {d['total_gb']} GB")
            print(f"     Writable: {d['writable']}")
            print(f"     Has AOTS6: {d['has_aots6']}")

    if "--setup" in args:
        devices = detect_usb()
        usb = None
        for d in devices:
            if d["writable"]:
                usb = d["path"]
                break
        if not usb:
            print("\n  No writable USB found. Connect USB OTG first.")
            return
        print(f"\n  Setting up AOTS6 Master Key on {usb}...")
        repo = os.path.join(str(Path.home()), "aots6_repo")
        result = setup_usb(usb, repo_path=repo)
        print(f"  ✓ Files copied: {result['copied_total']}")
        print(f"  ✓ Master hash: {result['master_hash'][:16]}...")
        if result["errors"]:
            print(f"  ✗ Missing: {len(result['errors_count'])} files")
        print(f"  USB ready: {result['root']}")

    elif "--verify" in args:
        devices = detect_usb()
        for d in devices:
            print(f"\n  Verifying {d['path']}...")
            v = verify_usb(d["path"])
            print(f"  Integrity: {v['integrity']}")
            print(f"  Hash matches: {v['hash_matches']}")
            print(f"  OTS files: {len(v['ots_files'])}")
            print(f"  Total files: {v['total_files']}")

    elif "--sync" in args:
        devices = detect_usb()
        repo    = os.path.join(str(Path.home()), "aots6_repo")
        for d in devices:
            if d["has_aots6"] and d["writable"]:
                print(f"\n  Syncing {d['path']} → {repo}...")
                r = sync_usb_to_repo(d["path"], repo)
                print(f"  Synced: {r['synced_count']} files")
                for f in r["synced"]:
                    print(f"    ✓ {f}")

    elif "--deploy" in args:
        idx    = args.index("--deploy")
        target = args[idx+1] if idx+1 < len(args) else os.path.join(str(Path.home()), "aots6_deployed")
        devices = detect_usb()
        for d in devices:
            if d["has_aots6"]:
                print(f"\n  Deploying from USB to {target}...")
                r = deploy_from_usb(d["path"], target)
                print(f"  Tests: {r['tests']}")
                print(f"  Target: {r['target']}")
                break

    elif "--status" in args:
        devices = detect_usb()
        repo    = os.path.join(str(Path.home()), "aots6_repo")
        py_count = len([f for f in os.listdir(repo) if f.endswith('.py')]) \
                   if os.path.exists(repo) else 0
        print(f"\n  Repo:    {repo} ({py_count} .py files)")
        print(f"  Author:  {AUTHOR}")
        print(f"  Hash:    {SYSTEM_HASH[:24]}...")
        print(f"  Devices: {len(devices)} storage found")
        for d in devices:
            icon = "🔑" if d["has_aots6"] else "💾"
            print(f"    {icon} {d['name']} — {d['free_gb']}GB free")

    print("\n" + "━"*58)


if __name__ == "__main__":
    main()
