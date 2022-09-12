#!/usr/bin/env python3
# PYTHON_ARGCOMPLETE_OK
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import gettext
import os
import sys
from argparse import ArgumentParser

import pycountry

try:
    import argcomplete
except ImportError:
    argcomplete = None

try:
    from progressbar import ETA, Bar, ProgressBar, SimpleProgress
except ImportError:
    ProgressBar = None

try:
    from proteus import Model, config
except ImportError:
    prog = os.path.basename(sys.argv[0])
    sys.exit("proteus must be installed to use %s" % prog)

SUBREGIONS = {
    '001': ['002', '009', '010', '019', '142', '150'],
    '002': ['015', '202'],
    '015': ['012', '434', '504', '729', '732', '788', '818'],
    '202': ['011', '014', '017', '018'],
    '011': [
        '132', '204', '270', '288', '324', '384', '430', '466', '478', '562',
        '566', '624', '654', '686', '694', '768', '854'],
    '014': [
        '086', '108', '174', '175', '231', '232', '260', '262', '404', '450',
        '454', '480', '508', '638', '646', '690', '706', '716', '728', '800',
        '834', '894'],
    '017': ['024', '120', '140', '148', '178', '180', '226', '266', '678'],
    '018': ['072', '426', '516', '710', '748'],
    '010': [],
    '019': ['003', '419'],
    '003': ['013', '021', '029'],
    '021': ['060', '124', '304', '666', '840'],
    '419': ['005', '013', '029'],
    '005': [
        '032', '068', '074', '076', '152', '170', '218', '238', '239', '254',
        '328', '600', '604', '740', '858', '862'],
    '013': ['084', '188', '222', '320', '340', '484', '558', '591'],
    '029': [
        '028', '044', '052', '092', '136', '192', '212', '214', '308', '312',
        '332', '388', '474', '500', '531', '533', '534', '535', '630', '652',
        '659', '660', '662', '663', '670', '780', '796', '850'],
    '142': ['030', '034', '035', '143', '145'],
    '030': ['156', '344', '392', '408', '410', '446', '496'] + ['158'],
    '034': ['004', '050', '064', '144', '356', '364', '462', ' 524', '586'],
    '035': [
        '096', '104', '116', '360', '418', '458', '608', '626', '702', '704',
        '764'],
    '143': ['398', '417', '762', '795', '860'],
    '145': [
        '031', '051', '048', '196', '268', '275', '368', '376', '400', '414',
        '422', '512', '634', '682', '760', '792', '784', '887'],
    '150': ['039', '151', '154', '155'],
    '039': [
        '008', '020', '070', '191', '292', '300', '336', '380', '470', '499',
        '620', '674', '688', '705', '724', '807'],
    '151': [
        '100', '112', '203', '348', '498', '616', '642', '643', '703', '804'],
    '154': [
        '208', '233', '234', '246', '248', '352', '372', '428', '440', '578',
        '744', '752', '826', '833', '830'],
    '830': ['831', '832', '680'],
    '155': ['040', '056', '250', '276', '438', '442', '492', '528', '756'],
    '009': ['053', '054', '057', '061'],
    '053': ['036', '162', '166', '334', '554', '574'],
    '054': ['090', '242', '540', '548', '598'],
    '057': ['296', '316', '520', '580', '581', '583', '584', '585'],
    '061': [
        '016', '184', '258', '570', '612', '772', '776', '798', '876', '882'],
    }
REGION2PARENT = {c: p for p, r in SUBREGIONS.items() for c in r}


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


def _remove_forbidden_chars(name):
    from trytond.tools import remove_forbidden_chars
    return remove_forbidden_chars(name)


def get_countries():
    Country = Model.get('country.country')
    return {c.code: c for c in Country.find([])}


def update_countries(countries):
    print("Update countries", file=sys.stderr)
    Region = Model.get('country.region')
    Country = Model.get('country.country')

    code2region = {a.code_numeric: a for a in Region.find([])}

    records = []
    for country in _progress(pycountry.countries):
        code = country.alpha_2
        if code in countries:
            record = countries[code]
        else:
            record = Country(code=code)
        record.name = _remove_forbidden_chars(country.name)
        record.code3 = country.alpha_3
        record.code_numeric = country.numeric
        record.region = code2region.get(REGION2PARENT.get(country.numeric))
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
                record.name = _remove_forbidden_chars(
                    gnutranslation.gettext(country.name))
                records.append(record)
            Country.save(records)


def get_subdivisions():
    Subdivision = Model.get('country.subdivision')
    return {(s.country.code, s.code): s for s in Subdivision.find([])}


def update_subdivisions(countries, subdivisions):
    print("Update subdivisions", file=sys.stderr)
    Subdivision = Model.get('country.subdivision')

    types = dict(Subdivision._fields['type']['selection'])
    unknown_types = set()
    records = []
    for subdivision in _progress(pycountry.subdivisions):
        code = subdivision.code
        country_code = subdivision.country_code
        if (country_code, code) in subdivisions:
            record = subdivisions[(country_code, code)]
        else:
            record = Subdivision(code=code, country=countries[country_code])
        record.name = _remove_forbidden_chars(subdivision.name)
        type_ = subdivision.type.lower()
        if type_ in types:
            record.type = subdivision.type.lower()
        else:
            record.type = None
            if type_ not in unknown_types:
                print(
                    "Unknown subdivision type: %s" % subdivision.type,
                    file=sys.stderr)
                unknown_types.add(type_)
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
                record.name = _remove_forbidden_chars(
                    gnutranslation.gettext(subdivision.name))
                records.append(record)
            Subdivision.save(records)


def main(database, config_file=None):
    config.set_trytond(database, config_file=config_file)
    with config.get_config().set_context(active_test=False):
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
    parser.add_argument('-d', '--database', dest='database', required=True)
    parser.add_argument('-c', '--config', dest='config_file',
        help='the trytond config file')
    if argcomplete:
        argcomplete.autocomplete(parser)

    args = parser.parse_args()
    main(args.database, args.config_file)


if __name__ == '__main__':
    run()
