#!/usr/bin/env python3
"""Verify archive file integrity after extraction; does not compile or run actors."""
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parent
for line in (root / "SHA256SUMS").read_text().splitlines():
    expected, name = line.split("  ", 1)
    data = (root / name).read_bytes()
    assert hashlib.sha256(data).hexdigest() == expected, name

cases = sorted((root / "benchmarks").iterdir())
assert len(cases) == 50
for case in cases:
    metadata = json.loads((case / "case.json").read_text())
    source = case / metadata["bundled_source"]["path"]
    data = source.read_bytes()
    actual = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
    assert actual == metadata["provenance"]["git_blob_sha"], source

sources = json.loads((root / "SOURCE_INDEX.json").read_text())
for item in sources:
    data = (root / item["archive_path"]).read_bytes()
    actual = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
    assert actual == item["git_blob_sha1"], item["path"]
print(f"VERIFIED: 50 case folders, 50 Scala source copies, {len(sources)} original upstream files")
print("Compilation and semantic compatibility: NOT TESTED")
