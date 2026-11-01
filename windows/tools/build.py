"""Build a standalone Windows GUI and a reproducible release layout."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import struct
import subprocess
import sys
import zipfile
import zlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ytdlp_windows import RELEASE_ASSET, VERSION


def make_icon(target: Path) -> None:
    size = 64
    pixels = bytearray()
    for y in range(size):
        pixels.append(0)
        for x in range(size):
            arrow = (28 <= x <= 35 and 12 <= y <= 35) or (28 <= y <= 43 and abs(x - 31.5) <= (43 - y))
            tray = (13 <= x <= 50 and 49 <= y <= 53) or (13 <= x <= 17 or 46 <= x <= 50) and 42 <= y <= 53
            color = (147, 181, 255, 255) if arrow or tray else (16, 18, 23, 255)
            pixels.extend(color)

    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
    png = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', size, size, 8, 6, 0, 0, 0))
    png += chunk(b'IDAT', zlib.compress(pixels)) + chunk(b'IEND', b'')
    target.write_bytes(struct.pack('<HHH', 0, 1, 1) + struct.pack('<BBBBHHII', size, size, 0, 0, 1, 32, len(png), 22) + png)


def main():
    if os.name != 'nt':
        raise SystemExit('La compilazione dell\'eseguibile richiede Windows.')
    os.chdir(ROOT)
    build = ROOT / 'build'
    build.mkdir(exist_ok=True)
    make_icon(build / 'app.ico')
    numbers = tuple(map(int, VERSION.split('.'))) + (0,)
    (build / 'version.txt').write_text(f'''VSVersionInfo(
      ffi=FixedFileInfo(filevers={numbers}, prodvers={numbers}, mask=0x3f, flags=0x0,
                       OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
      kids=[StringFileInfo([StringTable('041004B0', [
        StringStruct('CompanyName', 'Francesco Pio Pipino'),
        StringStruct('FileDescription', 'YtDlp per Windows'),
        StringStruct('FileVersion', '{VERSION}'),
        StringStruct('ProductName', 'YtDlp'),
        StringStruct('ProductVersion', '{VERSION}'),
        StringStruct('OriginalFilename', 'YtDlp.exe')
      ])]), VarFileInfo([VarStruct('Translation', [1040, 1200])])])''', 'utf-8')
    subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onefile',
                    '--windowed', '--name', 'YtDlp', '--icon', str(build / 'app.ico'),
                    '--version-file', str(build / 'version.txt'), 'main.py'], check=True)
    archive = ROOT / 'dist' / RELEASE_ASSET
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as package:
        package.write(ROOT / 'dist' / 'YtDlp.exe', 'YtDlp.exe')
        package.write(ROOT / 'README.md', 'README.txt')
        package.write(ROOT / 'THIRD_PARTY.md', 'THIRD_PARTY.txt')
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix('.zip.sha256').write_text(f'{digest}  {archive.name}\n', 'ascii')
    print(f'Build {VERSION}: {archive}')


if __name__ == '__main__':
    main()
