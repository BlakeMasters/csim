#!/usr/bin/env python3
"""Verify tracked release file hashes. Extra runs/ files are allowed; no authentication."""
from pathlib import Path
import hashlib,re,sys
ROOT=Path(__file__).resolve().parents[1]
manifest=ROOT/'MANIFEST.sha256'
if not manifest.exists():
    raise SystemExit('MANIFEST.sha256 not present; release assembly has not completed.')
errors=[];count=0
for line in manifest.read_text(encoding='utf-8').splitlines():
    digest,sep,name=line.partition('  ')
    if not sep or not re.fullmatch(r'[0-9a-f]{64}',digest):
        errors.append(f'malformed manifest line: {line!r}'); continue
    target=(ROOT/name).resolve()
    if not target.is_relative_to(ROOT) or not target.is_file():
        errors.append(f'missing or unsafe: {name}'); continue
    if hashlib.sha256(target.read_bytes()).hexdigest()!=digest:
        errors.append(f'hash mismatch: {name}')
    count+=1
if errors:
    print('\n'.join(errors)); raise SystemExit(1)
print(f'OK: {count} tracked files match. Integrity only; not scientific validation or publisher authentication.')
