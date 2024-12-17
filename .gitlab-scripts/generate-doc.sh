#!/bin/sh
set -eu

OUTPUTDIR=`realpath "${1}"`
mkdir -p "${OUTPUTDIR}"
: ${DOC_BASE_URL:=${OUTPUTDIR}}
: ${MAX_PROCS:=$(( `nproc` * 2 ))}
export DOC_BASE_URL

requirements=$(mktemp "${TMPDIR}/requirements-doc-XXXXXXXXXX.txt")
find . -name 'cookiecutter*' -prune -o -path '*/doc/requirements-doc.txt' -exec cat {} + | sort | uniq > "${requirements}"
pip install setuptools
pip install -r "${requirements}"

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
    elif [ "${package}" = "." ]; then
        package=""
    else
        package="modules-${package}"
    fi
    echo "${path}/doc" "${OUTPUTDIR}/${package}"
done) | xargs --max-args=2 --max-procs=${MAX_PROCS} python -m sphinx -Q -T -E -b html
