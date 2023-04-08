#!/bin/sh
set -eu

PACKAGES=`realpath "${1}"`
mkdir -p "${PACKAGES}"

(find . -name 'cookiecutter*' -prune -o -name setup.py -print | while read path; do
    echo "`dirname ${path}`"
done) | xargs --max-procs=$(( `nproc` * 2)) -I '{}' sh -c "cd \"{}\" && python setup.py --quiet sdist --dist-dir \"${PACKAGES}\""
