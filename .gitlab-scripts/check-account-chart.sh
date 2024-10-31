#!/bin/sh
set -eu

OUTPUT=${1:-`mktemp -d`}

for module in account account_asset account_deposit sale_advance_payment
do
    module="modules/${module}"
    mkdir -p "${OUTPUT}/${module}"
    for lang in de en es fr
    do
        printf "Check ${module} ${lang} ..."
        file="${module}/account_chart_${lang}.xml"
        xsltproc --stringparam lang "${lang}" "modules/account/localize.xsl" "${module}/account_chart.xml" > "${OUTPUT}/${file}"
        cmp "${file}" "${OUTPUT}/${file}"
        printf "OK\n"
    done
done

module="modules/account_be"
mkdir -p "${OUTPUT}/${module}"
for lang in fr nl
do
    printf "Check ${module} ${lang} ..."
    for template in account tax
    do
        file="${module}/${template}_be_${lang}.xml"
        xsltproc --stringparam lang "${lang}" "${module}/localize.xsl" "${module}/${template}_be.xml" > "${OUTPUT}/${file}"
        cmp "${file}" "${OUTPUT}/${file}"
    done
    printf "OK\n"
done

module="modules/account_es"
mkdir -p "${OUTPUT}/${module}"
for chart in normal pyme
do
    printf "Check ${module} ${chart} ..."
    for template in account tax
    do
        file="${module}/${template}_${chart}.xml"
        xsltproc --stringparam chart "${chart}" "${module}/create_chart.xsl" "${module}/${template}.xml" > "${OUTPUT}/${file}"
        cmp "${file}" "${OUTPUT}/${file}"
    done
    printf "OK\n"
done

module="modules/account_syscohada"
mkdir -p "${OUTPUT}/${module}"
for chart in 2001 2016
do
    for lang in fr
    do
        printf "Check ${module} ${chart} ${lang} ..."
        file="${module}/account_syscohada_${chart}_${lang}.xml"
        xsltproc --stringparam chart "${chart}" --stringparam lang "${lang}" "${module}/localize.xsl" "${module}/account_syscohada.xml" | sed -e "s/\$country/SYSCOHADA/" > "${OUTPUT}/${file}"
        cmp "${file}" "${OUTPUT}/${file}"
        printf "OK\n"
    done
done
