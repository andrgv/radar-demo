"""Verify and restore the archived November 8 material-study recordings."""

import argparse
import hashlib
import json
from pathlib import Path
import tarfile
import tempfile


def main(argv=None):
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Verify the archive without extracting')
    parser.add_argument('--destination', type=Path, default=root, help='Repository root to restore into')
    args = parser.parse_args(argv)
    folder = root / 'data/material-study-2026-11-08'
    manifest = json.loads((folder / 'manifest.json').read_text())
    destination = args.destination.resolve()
    with tempfile.TemporaryFile() as combined:
        for part in manifest['parts']:
            name = part['name']
            if Path(name).name != name:
                raise ValueError('Invalid archive part path')
            digest = hashlib.sha256()
            size = 0
            with (folder / name).open('rb') as source:
                while chunk := source.read(1024 * 1024):
                    size += len(chunk)
                    digest.update(chunk)
                    combined.write(chunk)
            if size != part['bytes'] or digest.hexdigest() != part['sha256']:
                raise ValueError(f'Archive checksum or size mismatch: {name}')
        combined.seek(0)
        with tarfile.open(fileobj=combined, mode='r:gz') as archive:
            members = archive.getmembers()
            files = [m for m in members if m.isfile()]
            if (len(files) != manifest['files']
                    or sum(m.size for m in files) != manifest['uncompressed_bytes']):
                raise ValueError('Archive contents differ from manifest')
            for member in members:
                if not (member.isdir() or member.isfile()):
                    raise ValueError(f'Unexpected archive member: {member.name}')
                if not any(member.name == d or member.name.startswith(d + '/')
                           for d in manifest['directories']):
                    raise ValueError(f'Unexpected recording path: {member.name}')
                if not (destination / member.name).resolve().is_relative_to(destination):
                    raise ValueError(f'Unsafe archive path: {member.name}')
            print(f"Verified {len(files)} files in {len(manifest['directories'])} recording folders.")
            if args.check:
                return 0
            for directory in manifest['directories']:
                if (destination / directory).exists():
                    raise FileExistsError(f'{directory} already exists; use --check or a fresh --destination')
            destination.mkdir(parents=True, exist_ok=True)
            archive.extractall(destination, members=members, filter='data')
            print(f'Restored recordings into {destination}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
