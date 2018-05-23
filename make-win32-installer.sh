#!/bin/sh
set -e
version=`python setup.py --version`
series=${version%.*}
python setup.py compile_catalog
python setup-freeze.py install_exe -d dist
makensis -DVERSION=${version} -DSERIES=${series} setup.nsi
