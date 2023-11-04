#!/bin/sh
set -e
version=`./setup.py --version`
machine=`python3 -c "import platform; print(platform.machine())"`
rm -rf build dist
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
