#!/bin/sh
set -e
version=`./setup.py --version`
series=${version%.*}
bits=`python -c "import platform; print(platform.architecture()[0])"`
rm -rf build dist
./setup.py compile_catalog
./setup-freeze.py install_exe -d dist
makensis -DVERSION=${version} -DSERIES=${series} -DBITS=${bits} setup.nsi
