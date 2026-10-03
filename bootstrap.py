"""Safe runtime bootstrap for Reporter.

This keeps the Docker entrypoint stable while allowing the authenticated
dashboard to restore a previously generated full backup. Restored source is
activated only when its integrity hash is valid, the backup manifest is valid,
and the restored requirements file matches the deployed requirements file.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

APP_DIR = Path("/app")
DATA_DIR = Path(os.getenv("DATA_DIR", "/app/data")).resolve()
RESTORE_DIR = DATA_DIR / "restore"
ACTIVATION_FILE = RESTORE_DIR / "activation.json"
MANIFEST_FILE = RESTORE_DIR / "manifest.json"
RESTORED_SOURCE = RESTORE_DIR / "source" / "Reporter.py"
RESTORED_REQUIREMENTS = RESTORE_DIR / "source" / "requirements.txt"
DEPLOYED_REQUIREMENTS = APP_DIR / "requirements.txt"
DEPLOYED_SOURCE = APP_DIR / "Reporter.py"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def safe_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def restore_is_valid() -> tuple[bool, str]:
    marker = safe_json(ACTIVATION_FILE)
    manifest = safe_json(MANIFEST_FILE)
    if not isinstance(marker, dict) or marker.get("active") is not True:
        return False, "runtime restore is not active"
    if not isinstance(manifest, dict) or manifest.get("format_version") != 1:
        return False, "restore manifest is missing or unsupported"
    if not RESTORED_SOURCE.is_file():
        return False, "restored Reporter.py is missing"
    if not DEPLOYED_REQUIREMENTS.is_file() or not RESTORED_REQUIREMENTS.is_file():
        return False, "requirements file is missing"

    expected_source = marker.get("source_sha256")
    if not isinstance(expected_source, str) or sha256_file(RESTORED_SOURCE) != expected_source:
        return False, "restored source integrity check failed"

    deployed_req_hash = sha256_file(DEPLOYED_REQUIREMENTS)
    restored_req_hash = marker.get("requirements_sha256")
    if deployed_req_hash != restored_req_hash or sha256_file(RESTORED_REQUIREMENTS) != restored_req_hash:
        return False, "restored dependencies differ from deployed dependencies"

    manifest_req_hash = manifest.get("requirements_sha256")
    if manifest_req_hash != restored_req_hash:
        return False, "manifest requirements hash mismatch"

    return True, "restore validated"


def main() -> None:
    ok, reason = restore_is_valid()
    if ok:
        try:
            # Syntax-check before replacing the live source.
            subprocess.run(
                [sys.executable, "-m", "py_compile", str(RESTORED_SOURCE)],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                timeout=20,
            )
            tmp_target = DEPLOYED_SOURCE.with_suffix(".restore.tmp")
            shutil.copy2(RESTORED_SOURCE, tmp_target)
            os.replace(tmp_target, DEPLOYED_SOURCE)
            print("[bootstrap] restored source activated", flush=True)
        except Exception as exc:
            print(f"[bootstrap] restored source rejected: {exc}", flush=True)
    else:
        if ACTIVATION_FILE.exists():
            print(f"[bootstrap] using deployed source: {reason}", flush=True)

    os.execv(sys.executable, [sys.executable, str(DEPLOYED_SOURCE)])


if __name__ == "__main__":
    main()
