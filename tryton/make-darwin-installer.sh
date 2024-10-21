#!/bin/sh
set -e
version=`./setup.py --version`
machine=`python3 -c "import platform; print(platform.machine())"`
rm -rf build dist
mkdir -p darwin/gtk-3.0
GDK_PIXBUF_MODULEDIR="$(dirname $(which gdk-pixbuf-query-loaders))/../lib/gdk-pixbuf-2.0/2.10.0/loaders" \
    gdk-pixbuf-query-loaders \
    | sed -e '/^#/d' \
    | sed  -e 's@/.*/lib/gdk-pixbuf-2.0@\@executable_path/lib/gdk-pixbuf-2.0@' \
    > darwin/gtk-3.0/gdk-pixbuf.loaders
gtk-query-immodules-3.0 \
    | sed -e '/^#/d' \
    | sed  -e 's@/.*/lib/gtk-3.0@\@executable_path/lib/gtk-3.0@' \
    > darwin/gtk-3.0/gtk.immodules
./setup.py compile_catalog
./setup-freeze.py bdist_mac
mkdir dist
mv build/Tryton.app dist/
for f in CHANGELOG COPYRIGHT LICENSE; do
    cp ${f} dist/${f}.txt
done
cp -r doc dist/
rm -f "tryton-${machine}-${version}.dmg"
hdiutil create "tryton-${machine}-${version}.dmg" \
    -volname "Tryton Client ${machine} ${version}" \
    -fs HFS+ -srcfolder dist
