#!/bin/sh

VERSION=`python -c "import os; execfile(os.path.join('tryton', 'version.py')); print VERSION"`
GTK_INST_DIR=~/gtk/inst
GTK_VERSION=2.10.0
PANGO_VERSION=1.6.0

mkdir -p dist/tryton.app/Contents/Resources/lib/pango/${PANGO_VERSION}/modules
cp -r ${GTK_INST_DIR}/lib/pango/${PANGO_VERSION}/modules/*.so dist/tryton.app/Contents/Resources/lib/pango/${PANGO_VERSION}/modules/

pango-querymodules | sed -e "s#${GTK_INST_DIR}#@executable_path/../Resources#" >dist/tryton.app/Contents/Resources/pango.modules
echo -e "[Pango]\nModuleFiles=./pango.modules\n" >dist/tryton.app/Contents/Resources/pangorc

mkdir -p dist/tryton.app/Contents/Resources/lib/gtk-2.0/${GTK_VERSION}/loaders/
cp -r ${GTK_INST_DIR}/lib/gtk-2.0/${GTK_VERSION}/loaders/*.so dist/tryton.app/Contents/Resources/lib/gtk-2.0/${GTK_VERSION}/loaders/

mkdir -p dist/tryton.app/Contents/Resources/lib/gtk-2.0/${GTK_VERSION}/engines/
cp ${GTK_INST_DIR}/lib/gtk-2.0/${GTK_VERSION}/engines/libclearlooks.so dist/tryton.app/Contents/Resources/lib/gtk-2.0/${GTK_VERSION}/engines/

cp ${GTK_INST_DIR}/share/themes/Clearlooks/gtk-2.0/gtkrc dist/tryton.app/Contents/Resources/gtkrc

gdk-pixbuf-query-loaders | sed -e "s#${GTK_INST_DIR}#@executable_path/../Resources#" >dist/tryton.app/Contents/Resources/gdk-pixbuf.loaders

for library in dist/tryton.app/Contents/Resources/lib/gtk-2.0/${GTK_VERSION}/{loaders,engines}/*.so dist/tryton.app/Contents/Resources/lib/pango/${PANGO_VERSION}/modules/*.so; do
    libs="`otool -L $library 2>/dev/null | fgrep compatibility | cut -d\( -f1 | grep ${GTK_INST_DIR} | sort | uniq`"
    for lib in $libs; do
        fixed=`echo $lib | sed -e s,\${GTK_INST_DIR}/lib,@executable_path/../Frameworks,`
        install_name_tool -change $lib $fixed $library
    done
done


for i in CHANGELOG COPYRIGHT LICENSE README TODO; do
    cp ${i} dist/${i}.txt
done

cp -r doc dist

if [[ -e tryton-${VERSION}.dmg ]]; then
    rm tryton-${VERSION}.dmg
fi

hdiutil create tryton-${VERSION}.dmg -volname "Tryton Client ${VERSION}" -fs HFS+ -srcfolder dist
