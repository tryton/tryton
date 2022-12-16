#!/bin/sh
set -e
version=`./setup.py --version`
series=${version%.*}
./setup.py compile_catalog
./setup-freeze.py install_exe -d dist
cp `which gdbus.exe` dist/
makensis -DVERSION=${version} -DSERIES=${series} setup.nsi
