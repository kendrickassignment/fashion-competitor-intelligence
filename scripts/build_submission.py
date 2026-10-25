"""Package committed public files, with an optional explicit private reviewer key."""

import argparse
import json
import subprocess
import zipfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--credentials", help="Private service-account JSON; never publish the resulting ZIP")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    files = subprocess.check_output(["git", "ls-files", "-z"], cwd=root).decode().split("\0")
    credential = Path(args.credentials).resolve() if args.credentials else None
    if credential:
        payload = json.loads(credential.read_text(encoding="utf-8"))
        if payload.get("type") != "service_account" or not payload.get("private_key"):
            raise ValueError("Expected a real service-account credential")
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in files:
            if name and (root / name).is_file():
                archive.write(root / name, name)
        if credential:
            archive.write(credential, "google-sheets-api.json")
    print(f"Created {output.name}; private reviewer credentials included: {bool(credential)}")


if __name__ == "__main__":
    main()
