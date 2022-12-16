#!/bin/sh
set -e
version=`python setup.py --version`
python setup.py compile_catalog
python setup-freeze.py install_exe -d dist
makensis -DVERSION=${version} setup.nsi
makensis -DVERSION=${version} setup-single.nsi
