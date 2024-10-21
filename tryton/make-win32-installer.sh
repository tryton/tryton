#!/bin/sh
set -e
version=`./setup.py --version`
series=${version%.*}
bits=`python -c "import platform; print(platform.architecture()[0])"`
rm -rf build dist
mkdir -p win32/gtk-3.0
gdk-pixbuf-query-loaders | sed -e '/^#/d' > win32/gtk-3.0/gdk-pixbuf.loaders
gtk-query-immodules-3.0 | sed -e '/^#/d' > win32/gtk-3.0/gtk.immodules
./setup.py compile_catalog
./setup-freeze.py install_exe -d dist
cp `which gdbus.exe` dist/
makensis -DVERSION=${version} -DSERIES=${series} -DBITS=${bits} setup.nsi
