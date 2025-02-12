#!/usr/bin/env python3
import os
import sys

try:
    DIR = os.path.abspath(os.path.normpath(os.path.join(__file__,
        '..', '..', 'tryton')))
    if os.path.isdir(DIR):
        sys.path.insert(0, os.path.dirname(DIR))
except NameError:
    pass

if hasattr(sys, 'frozen'):
    prefix = os.path.dirname(sys.executable)
    share = os.path.join(prefix, 'share')
    os.environ['GTK_EXE_PREFIX'] = prefix
    os.environ['GTK_DATA_PREFIX'] = prefix
    os.environ['EV_BACKENDS_DIR'] = os.path.join(
        prefix, 'lib', 'evince', '4', 'backends')
    os.environ['XDG_DATA_DIRS'] = share
    os.environ['GDK_PIXBUF_MODULE_FILE'] = os.path.join(
            share, 'gtk-3.0', 'gdk-pixbuf.loaders')
    os.environ['GTK_IM_MODULE_FILE'] = os.path.join(
            share, 'gtk-3.0', 'gtk.immodules')
    os.environ['GI_TYPELIB_PATH'] = os.path.join(
            prefix, 'lib', 'girepository-1.0')
    os.environ.setdefault('SSL_CERT_FILE',
        os.path.join(share, 'ssl', 'cert.pem'))
    os.environ.setdefault('SSL_CERT_DIR',
        os.path.join(share, 'ssl', 'certs'))

    if sys.platform == 'win32':
        # cx_freeze >= 5 put python modules under lib directory
        # and dependencies of gdk-pixbuf loaders
        sys.path.append(os.path.join(prefix, 'lib'))
        sys.path.append(os.path.join(
                prefix, 'lib', 'gdk-pixbuf-2.0', '2.10.0', 'loaders'))

    # On first launch the MacOSX app launcher may append an extra unique
    # argument starting with -psn_. This must be filtered to not crash the
    # option parser.
    if sys.platform == 'darwin':
        sys.argv = [a for a in sys.argv if not a.startswith('-psn_')]

if os.environ.get('FLATPAK_ID') and os.environ.get('XDG_RUNTIME_DIR'):
    # Set $TMPDIR to share files outside the sandbox
    os.environ['TMPDIR'] = os.path.join(
        os.environ.get('XDG_RUNTIME_DIR'), 'app', os.environ.get('FLATPAK_ID'))


# Disable dbusmenu to show second menu in tabs
os.environ['UBUNTU_MENUPROXY'] = '0'
# overlay-scrollbar breaks treeview height
os.environ['LIBOVERLAY_SCROLLBAR'] = '0'

from tryton.client import main
if __name__ == "__main__":
    main()
