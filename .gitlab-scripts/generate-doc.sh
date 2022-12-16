#!/bin/sh
set -eu

OUTPUTDIR=`realpath "${1}"`
mkdir -p "${OUTPUTDIR}"

find . -path '*/doc/conf.py' | while read path; do
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
    (cd "${path}" && python -m sphinx -T -E -b html doc "${OUTPUTDIR}/${package}")
done
