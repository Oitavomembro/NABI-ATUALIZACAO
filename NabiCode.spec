# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_all, collect_dynamic_libs, collect_submodules

project_root = os.path.abspath(SPECPATH)
version_file = os.path.join(project_root, 'VERSAO.txt')
version = open(version_file, encoding='utf-8-sig').read().strip().replace('.', '_')
name = f'NabiCode_v{version}'

packages = (
    'customtkinter',
    'requests',
    'cryptography',
    'lxml',
    'reportlab',
    'openpyxl',
    'matplotlib',
)

datas, binaries, hiddenimports = [
    (version_file, '.'),
    (os.path.join(project_root, 'licensing', 'trusted_public_keys.json'), 'licensing'),
], [], []
for package in packages:
    package_datas, package_binaries, package_hiddenimports = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hiddenimports
    hiddenimports += collect_submodules(package)
    binaries += collect_dynamic_libs(package)

# Imports críticos usados indiretamente pelo módulo fiscal. Mantê-los explícitos
# evita que builds em versões novas do Python omitam os pacotes completos.
hiddenimports += [
    'cryptography',
    'cryptography.x509',
    'cryptography.hazmat',
    'cryptography.hazmat.backends',
    'cryptography.hazmat.backends.openssl',
    'cryptography.hazmat.primitives',
    'cryptography.hazmat.primitives.asymmetric',
    'cryptography.hazmat.primitives.asymmetric.padding',
    'cryptography.hazmat.primitives.serialization',
    'cryptography.hazmat.primitives.serialization.pkcs12',
    'cryptography.hazmat.bindings',
    'cryptography.hazmat.bindings._rust',
    'lxml.etree',
    'requests',
    'requests.adapters',
    'urllib3',
    'certifi',
]

# Remove duplicidades mantendo a ordem para um build determinístico.
datas = list(dict.fromkeys(datas))
binaries = list(dict.fromkeys(binaries))
hiddenimports = list(dict.fromkeys(hiddenimports))

for folder in ('assets', 'config', 'docs'):
    if os.path.isdir(folder):
        datas.append((folder, folder))

schema_folder = os.path.join(project_root, 'resources', 'fiscal', 'schemas')
if os.path.isdir(schema_folder):
    datas.append((schema_folder, os.path.join('resources', 'fiscal', 'schemas')))

a = Analysis(
    ['main.py'],
    pathex=[os.path.abspath('.')],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['license_issuer'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name=name,
)
