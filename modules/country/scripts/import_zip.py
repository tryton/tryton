#!/usr/bin/env python
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from __future__ import print_function
import csv
import os
import sys
try:
    from urllib.request import urlopen
except ImportError:
    from urllib2 import urlopen
import zipfile

from argparse import ArgumentParser
from io import BytesIO, StringIO

try:
    from progressbar import ProgressBar, Bar, ETA, SimpleProgress
except ImportError:
    ProgressBar = None

try:
    from proteus import Model, config
except ImportError:
    prog = os.path.basename(sys.argv[0])
    sys.exit("proteus must be installed to use %s" % prog)


def clean(code):
    sys.stderr.write('Cleaning')
    Zip = Model.get('country.zip')
    Zip._proxy.delete(
        [z.id for z in Zip.find([('country.code', '=', code)])], {})
    print('.', file=sys.stderr)


def fetch(code):
    sys.stderr.write('Fetching')
    url = 'https://download.geonames.org/export/zip/%s.zip' % code
    responce = urlopen(url)
    data = responce.read()
    with zipfile.ZipFile(BytesIO(data)) as zf:
        data = zf.read('%s.txt' % code)
    print('.', file=sys.stderr)
    return data


def import_(data):
    Zip = Model.get('country.zip')
    Country = Model.get('country.country')
    Subdivision = Model.get('country.subdivision')
    print('Importing', file=sys.stderr)

    def get_country(code):
        country = countries.get(code)
        if not country:
            country, = Country.find([('code', '=', code)])
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
    f = StringIO(data.decode('utf-8'))
    zips = []
    for row in pbar(list(csv.DictReader(
                    f, fieldnames=_fieldnames, delimiter='\t'))):
        country = get_country(row['country'])
        for code in ['code1', 'code2', 'code3']:
            subdivision = get_subdivision(row['country'], row[code])
            if code == 'code1' or subdivision:
                zips.append(
                    Zip(country=country, subdivision=subdivision,
                        zip=row['postal'], city=row['place']))
    Zip.save(zips)


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
    parser.add_argument('-d', '--database', dest='database')
    parser.add_argument('-c', '--config', dest='config_file',
        help='the trytond config file')
    parser.add_argument('codes', nargs='+')

    args = parser.parse_args()
    if not args.database:
        parser.error('Missing database')
    main(args.database, args.codes, args.config_file)


if __name__ == '__main__':
    run()
