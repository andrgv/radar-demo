"""Verify exact bulk-evidence originals against the retained archive manifest."""
import argparse
import hashlib
import json
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=root/'evidence/archive-manifest.json')
    parser.add_argument('--evidence-root', type=Path, default=root/'evidence',
                        help='The evidence/ directory in this checkout or in an external backup')
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    archive_root = args.evidence_root.resolve()
    if not archive_root.is_dir():
        parser.error('Evidence root is not a directory: '+str(archive_root))
    failures = []
    for entry in manifest['files']:
        path = (archive_root/entry['evidence_relative_path']).resolve()
        if not path.is_relative_to(archive_root):
            parser.error('Manifest artifact escapes evidence root')
        if not path.is_file():
            failures.append('Missing: '+entry['evidence_relative_path'])
            continue
        if path.stat().st_size != entry['bytes']:
            failures.append('Size mismatch: '+entry['evidence_relative_path'])
            continue
        digest = hashlib.sha256()
        with path.open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024*1024), b''):
                digest.update(chunk)
        if digest.hexdigest() != entry['sha256']:
            failures.append('SHA-256 mismatch: '+entry['evidence_relative_path'])
    if failures:
        print('\n'.join(failures))
        raise SystemExit(1)
    print(f"Verified {len(manifest['files'])} artifacts: sizes and SHA-256 match.")


if __name__ == '__main__':
    main()
