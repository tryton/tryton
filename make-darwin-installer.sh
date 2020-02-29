#!/bin/sh
set -e
version=`./setup.py --version`
rm -rf build dist
./setup.py compile_catalog
./setup-freeze.py bdist_mac
mkdir dist
mv build/Tryton.app dist/
for f in CHANGELOG COPYRIGHT LICENSE; do
    cp ${f} dist/${f}.txt
done
cp -r doc dist/
rm -f "tryton-${version}.dmg"
hdiutil create "tryton-${version}.dmg" -volname "Tryton Client ${version}" \
    -fs HFS+ -srcfolder dist
