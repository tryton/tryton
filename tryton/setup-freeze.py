import os
import re
import sys
import tempfile
import user
from subprocess import Popen, PIPE, check_call

from cx_Freeze import setup, Executable

include_files = [
    (os.path.join('tryton', 'data'), 'data'),
    (os.path.join('tryton', 'plugins'), 'plugins'),
    (os.path.join(sys.prefix, 'share', 'glib-2.0', 'schemas'),
        os.path.join('share', 'glib-2.0', 'schemas')),
    (os.path.join(sys.prefix, 'lib', 'gtk-3.0'),
        os.path.join('lib', 'gtk-3.0')),
    (os.path.join(sys.prefix, 'lib', 'gdk-pixbuf-2.0'),
        os.path.join('lib', 'gdk-pixbuf-2.0')),
    (os.path.join(sys.prefix, 'share', 'locale'),
        os.path.join('share', 'locale')),
    (os.path.join(sys.prefix, 'share', 'icons', 'Adwaita'),
        os.path.join('share', 'icons', 'Adwaita')),
    (os.path.join(sys.platform, 'gtk-3.0', 'gtk.immodules'),
        os.path.join('etc', 'gtk-3.0', 'gtk.immodules')),
    (os.path.join(sys.platform, 'gtk-3.0', 'gdk-pixbuf.loaders'),
        os.path.join('etc', 'gtk-3.0', 'gdk-pixbuf.loaders')),
    ]

required_gi_namespaces = [
    'Atk-1.0',
    'GLib-2.0',
    'GModule-2.0',
    'GObject-2.0',
    'Gdk-3.0',
    'GdkPixbuf-2.0',
    'Gio-2.0',
    'GooCanvas-2.0',
    'Gtk-3.0',
    'Pango-1.0',
    'PangoCairo-1.0',
    'PangoFT2-1.0',
    'Rsvg-2.0',
    'cairo-1.0',
    'fontconfig-2.0',
    'freetype2-2.0',
    ]


def replace_path(match):
    libs = [os.path.basename(p) for p in match.group(1).split(',')]
    required_libs.update(libs)
    if sys.platform == 'darwin':
        libs = [os.path.join('@executable_path', l) for l in libs]
    return 'shared-library="%s"' % ','.join(libs)
lib_re = re.compile(r'shared-library="([^\"]*)"')

required_libs = set()
temp = tempfile.mkdtemp()
for ns in required_gi_namespaces:
    gir_name = '%s.gir' % ns
    gir_file = os.path.join(sys.prefix, 'share', 'gir-1.0', gir_name)
    gir_tmp = os.path.join(temp, gir_name)
    with open(gir_file, 'r') as src, open(gir_tmp, 'w') as dst:
        for line in src:
            dst.write(lib_re.sub(replace_path, line))
    typefile_name = '%s.typelib' % ns
    typefile_file = os.path.join('lib', 'girepository-1.0', typefile_name)
    typefile_tmp = os.path.join(temp, typefile_name)
    check_call(['g-ir-compiler', '--output=' + typefile_tmp, gir_tmp])

    include_files.append((typefile_tmp, typefile_file))

if sys.platform == 'win32':
    required_libs.update([
        'libcroco-0.6-3.dll',
        'libepoxy-0.dll',
        ])
    include_files.append(
        (os.path.join(sys.prefix, 'ssl'), os.path.join('etc', 'ssl')))
    lib_path = os.getenv('PATH', os.defpath).split(os.pathsep)
else:
    lib_path = [os.path.join(sys.prefix, 'lib')]
for lib in required_libs:
    for path in lib_path:
        path = os.path.join(path, lib)
        if os.path.isfile(path):
            break
    else:
        raise Exception('%s not found' % lib)
    include_files.append((path, lib))

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
            'packages': ['gi'],
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
