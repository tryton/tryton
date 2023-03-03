#!/bin/sh
set -eu

OUTPUTDIR=`realpath "${1}"`
mkdir -p "${OUTPUTDIR}"
export DOC_BASE_URL=$OUTPUTDIR

(find . -name 'cookiecutter*' -prune -o -path '*/doc/conf.py' -print | while read path; do
    path=`dirname "${path}"`
    path=`dirname "${path}"`
    package=`basename "${path}"`
    package=$(echo ${package} | sed "s/_/-/g")
    if [ "${package}" = "trytond" ]; then
        package="server"
    elif [ "${package}" = "tryton" ]; then
        package="client-desktop"
    elif [ "${package}" = "proteus" ]; then
        package="client-library"
    elif [ "${package}" = "trytond-gis" ]; then
        package="backend-gis"
    else
        package="modules-${package}"
    fi
    echo "${path}/doc" "${OUTPUTDIR}/${package}"
done) | xargs --max-args=2 --max-procs=$(( `nproc` * 2)) python -m sphinx -Q -T -E -b html
