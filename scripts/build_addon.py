#!/usr/bin/env python3
"""Build a Kodi package from an explicit runtime-file allowlist."""
from pathlib import Path
import argparse
import hashlib
import re
import xml.etree.ElementTree as ET
import zipfile


def build_addon(root, output):
    root, output = Path(root), Path(output)
    addon = ET.parse(root / 'addon.xml').getroot()
    addon_id, version = addon.get('id'), addon.get('version')
    if not re.fullmatch(r'[a-z0-9._-]+', addon_id or '') or not re.fullmatch(r'[0-9A-Za-z._-]+', version or ''):
        raise ValueError('Invalid addon ID or version')
    paths = [root / name for name in ('addon.xml', 'service.py', 'LICENSE')]
    for pattern in ('lib/**/*.py', 'resources/settings.xml', 'resources/*.png',
                    'resources/language/resource.language.*/strings.po', 'resources/skins/**/*.xml'):
        paths.extend(root.glob(pattern))
    output.mkdir(parents=True, exist_ok=True)
    destination = output / (addon_id + '-' + version + '.zip')
    with zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(set(paths)):
            relative = path.relative_to(root)
            if path.is_symlink() or any(part.startswith('.') or part == '__pycache__' for part in relative.parts):
                continue
            info = zipfile.ZipInfo(addon_id + '/' + relative.as_posix(), date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())
    # Kodi repository metadata currently requests MD5 package sidecars.
    destination.with_suffix('.zip.md5').write_text(hashlib.md5(destination.read_bytes()).hexdigest() + '\n')
    return destination


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output', type=Path, default=Path('dist'))
    args = parser.parse_args()
    print(build_addon(args.root, args.output))
