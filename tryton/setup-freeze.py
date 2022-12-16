import os
import sys
import user
from subprocess import Popen, PIPE

from cx_Freeze import setup, Executable

include_files = [
    ('tryton/data', 'data'),
    ('tryton/plugins', 'plugins'),
    (os.path.join(sys.prefix, 'lib/gtk-2.0'), 'lib/gtk-2.0'),
    (os.path.join(sys.prefix, 'lib/gdk-pixbuf-2.0'), 'lib/gdk-pixbuf-2.0'),
    (os.path.join(sys.prefix, 'share/locale'), 'share/locale'),
    ('%s/gtk-2.0/gtkrc' % sys.platform, 'etc/gtk-2.0/gtkrc'),
    ('%s/gtk-2.0/gtk.immodules' % sys.platform, 'etc/gtk-2.0/gtk.immodules'),
    ('%s/gtk-2.0/gdk-pixbuf.loaders' % sys.platform,
        'etc/gtk-2.0/gdk-pixbuf.loaders'),
    ]

if sys.platform == 'win32':
    include_files.extend([
        (os.path.join(sys.prefix, 'share/themes/MS-Windows'),
            'share/themes/MS-Windows'),
        (os.path.join(sys.prefix, 'ssl'), 'etc/ssl'),
        ])
    dll_paths = os.getenv('PATH', os.defpath).split(os.pathsep)
    required_dlls = [
        'librsvg-2-2.dll',
        'libcroco-0.6-3.dll',
        ]
    for dll in required_dlls:
        for path in dll_paths:
            path = os.path.join(path, dll)
            if os.path.isfile(path):
                break
        else:
            raise Exception('%s not found' % dll)
        include_files.append((path, dll))

elif sys.platform == 'darwin':
    include_files.extend([
        (os.path.join(sys.prefix, 'share/themes/Clearlooks'),
            'share/themes/Clearlooks'),
        (os.path.join(sys.prefix, 'share/themes/Mac'),
            'share/themes/Mac'),
        ])

version = Popen(
    'python setup.py --version', stdout=PIPE, shell=True).stdout.read()
version = version.strip()

setup(name='tryton',
    version=version,
    options={
        'build_exe': {
            'no_compress': True,
            'include_files': include_files,
            'silent': True,
            'packages': ['gtk'],
            'include_msvcr': True,
            },
        'bdist_mac': {
            'iconfile': os.path.join(
                'tryton', 'data', 'pixmaps', 'tryton', 'tryton.icns'),
            'bundle_name': 'Tryton',
            }
        },
    executables=[Executable(
            'bin/tryton',
            base='Win32GUI' if sys.platform == 'win32' else None,
            icon=os.path.join(
                'tryton', 'data', 'pixmaps', 'tryton', 'tryton.ico'),
            )])
