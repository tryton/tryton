#!/usr/bin/env python3
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import gettext
import os
import sys
from argparse import ArgumentParser

import pycountry

try:
    from progressbar import ProgressBar, Bar, ETA, SimpleProgress
except ImportError:
    ProgressBar = None

try:
    from proteus import Model, config
except ImportError:
    prog = os.path.basename(sys.argv[0])
    sys.exit("proteus must be installed to use %s" % prog)


def _progress(iterable):
    if ProgressBar:
        pbar = ProgressBar(
            widgets=[SimpleProgress(), Bar(), ETA()])
    else:
        pbar = iter
    return pbar(iterable)


def _get_language_codes():
    Language = Model.get('ir.lang')
    languages = Language.find([('translatable', '=', True)])
    for l in languages:
        yield l.code


def get_countries():
    Country = Model.get('country.country')

    with config.get_config().set_context(active_test=False):
        return {c.code: c for c in Country.find([])}


def update_countries(countries):
    print("Update countries", file=sys.stderr)
    Country = Model.get('country.country')

    records = []
    for country in _progress(pycountry.countries):
        code = country.alpha_2
        if code in countries:
            record = countries[code]
        else:
            record = Country(code=code)
        record.name = country.name
        record.code3 = country.alpha_3
        record.code_numeric = country.numeric
        records.append(record)

    Country.save(records)
    return {c.code: c for c in records}


def translate_countries(countries):
    Country = Model.get('country.country')

    current_config = config.get_config()
    for code in _get_language_codes():
        try:
            gnutranslation = gettext.translation(
                'iso3166', pycountry.LOCALES_DIR, languages=[code])
        except IOError:
            continue
        print("Update countries %s" % code, file=sys.stderr)
        with current_config.set_context(language=code):
            records = []
            for country in _progress(pycountry.countries):
                record = Country(countries[country.alpha_2].id)
                record.name = gnutranslation.gettext(country.name)
                records.append(record)
            Country.save(records)


def get_subdivisions():
    Subdivision = Model.get('country.subdivision')

    with config.get_config().set_context(active_test=False):
        return {(s.country.code, s.code): s for s in Subdivision.find([])}


def update_subdivisions(countries, subdivisions):
    print("Update subdivisions", file=sys.stderr)
    Subdivision = Model.get('country.subdivision')

    records = []
    for subdivision in _progress(pycountry.subdivisions):
        code = subdivision.code
        country_code = subdivision.country_code
        if (country_code, code) in subdivisions:
            record = subdivisions[(country_code, code)]
        else:
            record = Subdivision(code=code, country=countries[country_code])
        record.name = subdivision.name
        record.type = subdivision.type.lower()
        records.append(record)

    Subdivision.save(records)
    return {(s.country.code, s.code): s for s in records}


def update_subdivisions_parent(subdivisions):
    print("Update subdivisions parent", file=sys.stderr)
    Subdivision = Model.get('country.subdivision')

    records = []
    for subdivision in _progress(pycountry.subdivisions):
        code = subdivision.code
        country_code = subdivision.country_code
        record = subdivisions[(country_code, code)]
        if subdivision.parent:
            record.parent = subdivisions[
                (country_code, subdivision.parent.code)]
        else:
            record.parent = None
        records.append(record)
    Subdivision.save(records)


def translate_subdivisions(subdivisions):
    Subdivision = Model.get('country.subdivision')

    current_config = config.get_config()
    for code in _get_language_codes():
        try:
            gnutranslation = gettext.translation(
                'iso3166-2', pycountry.LOCALES_DIR, languages=[code])
        except IOError:
            continue
        print("Update subdivisions %s" % code, file=sys.stderr)
        with current_config.set_context(language=code):
            records = []
            for subdivision in _progress(pycountry.subdivisions):
                record = Subdivision(subdivisions[
                        (subdivision.country_code, subdivision.code)].id)
                record.name = gnutranslation.gettext(subdivision.name)
                records.append(record)
            Subdivision.save(records)


def main(database, config_file=None):
    config.set_trytond(database, config_file=config_file)
    do_import()


def do_import():
    countries = get_countries()
    countries = update_countries(countries)
    translate_countries(countries)
    subdivisions = get_subdivisions()
    subdivisions = update_subdivisions(countries, subdivisions)
    update_subdivisions_parent(subdivisions)
    translate_subdivisions(subdivisions)


def run():
    parser = ArgumentParser()
    parser.add_argument('-d', '--database', dest='database')
    parser.add_argument('-c', '--config', dest='config_file',
        help='the trytond config file')

    args = parser.parse_args()
    if not args.database:
        parser.error('Missing database')
    main(args.database, args.config_file)


if __name__ == '__main__':
    run()
