#!/usr/bin/env python
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from __future__ import print_function

import csv
import os
import sys

try:
    from urllib.error import HTTPError
    from urllib.request import urlopen
except ImportError:
    from urllib2 import urlopen, HTTPError

import zipfile
from argparse import ArgumentParser
from io import BytesIO, TextIOWrapper

try:
    from progressbar import ETA, Bar, ProgressBar, SimpleProgress
except ImportError:
    ProgressBar = None

try:
    from proteus import Model, config
except ImportError:
    prog = os.path.basename(sys.argv[0])
    sys.exit("proteus must be installed to use %s" % prog)


def clean(code):
    sys.stderr.write('Cleaning')
    PostalCode = Model.get('country.postal_code')
    PostalCode._proxy.delete(
        [c.id for c in PostalCode.find([('country.code', '=', code)])], {})
    print('.', file=sys.stderr)


def fetch(code):
    sys.stderr.write('Fetching')
    url = 'https://download.geonames.org/export/zip/%s.zip' % code
    try:
        responce = urlopen(url)
    except HTTPError as e:
        sys.exit("\nError downloading %s: %s" % (code, e.reason))
    data = responce.read()
    with zipfile.ZipFile(BytesIO(data)) as zf:
        data = zf.read('%s.txt' % code)
    print('.', file=sys.stderr)
    return data


def import_(data):
    PostalCode = Model.get('country.postal_code')
    Country = Model.get('country.country')
    Subdivision = Model.get('country.subdivision')
    print('Importing', file=sys.stderr)

    def get_country(code):
        country = countries.get(code)
        if not country:
            try:
                country, = Country.find([('code', '=', code)])
            except ValueError:
                sys.exit("Error missing country with code %s" % code)
            countries[code] = country
        return country
    countries = {}

    def get_subdivision(country, code):
        code = '%s-%s' % (country, code)
        subdivision = subdivisions.get(code)
        if not subdivision:
            try:
                subdivision, = Subdivision.find([('code', '=', code)])
            except ValueError:
                return
            subdivisions[code] = subdivision
        return subdivision
    subdivisions = {}

    if ProgressBar:
        pbar = ProgressBar(
            widgets=[SimpleProgress(), Bar(), ETA()])
    else:
        pbar = iter
    f = TextIOWrapper(BytesIO(data), encoding='utf-8')
    codes = []
    for row in pbar(list(csv.DictReader(
                    f, fieldnames=_fieldnames, delimiter='\t'))):
        country = get_country(row['country'])
        for code in ['code1', 'code2', 'code3']:
            subdivision = get_subdivision(row['country'], row[code])
            if code == 'code1' or subdivision:
                codes.append(
                    PostalCode(country=country, subdivision=subdivision,
                        postal_code=row['postal'], city=row['place']))
    PostalCode.save(codes)


_fieldnames = ['country', 'postal', 'place', 'name1', 'code1',
    'name2', 'code2', 'name3', 'code3', 'latitude', 'longitude', 'accuracy']


def main(database, codes, config_file=None):
    config.set_trytond(database, config_file=config_file)
    do_import(codes)


def do_import(codes):
    for code in codes:
        print(code, file=sys.stderr)
        code = code.upper()
        clean(code)
        import_(fetch(code))


def run():
    parser = ArgumentParser()
    parser.add_argument('-d', '--database', dest='database', required=True)
    parser.add_argument('-c', '--config', dest='config_file',
        help='the trytond config file')
    parser.add_argument('codes', nargs='+')

    args = parser.parse_args()
    main(args.database, args.codes, args.config_file)


if __name__ == '__main__':
    run()
