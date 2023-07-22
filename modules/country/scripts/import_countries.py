#!/usr/bin/env python3
# PYTHON_ARGCOMPLETE_OK
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import datetime as dt
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
    from tqdm import tqdm
except ImportError:
    tqdm = None

try:
    from proteus import Model, config
except ImportError:
    prog = os.path.basename(sys.argv[0])
    sys.exit("proteus must be installed to use %s" % prog)

ORGANIZATIONS = {
    # Founding members has no from date
    'EU': {
        'AT': [(dt.date(1995, 1, 1), None)],
        'BE': [(None, None)],
        'BG': [(dt.date(2007, 1, 1), None)],
        'CY': [(dt.date(2004, 5, 1), None)],
        'CZ': [(dt.date(2004, 5, 1), None)],
        'DE': [(None, None)],
        'DK': [(dt.date(1973, 1, 1), None)],
        'EE': [(dt.date(2004, 5, 1), None)],
        'ES': [(dt.date(1986, 1, 1), None)],
        'FI': [(dt.date(1995, 1, 1), None)],
        'FR': [(None, None)],
        'GB': [(dt.date(1973, 1, 1), dt.date(2020, 1, 31))],
        'GR': [(dt.date(1981, 1, 1), None)],
        'HR': [(dt.date(2013, 7, 1), None)],
        'HU': [(dt.date(2004, 5, 1), None)],
        'IE': [(dt.date(1973, 1, 1), None)],
        'IT': [(None, None)],
        'LT': [(dt.date(2004, 5, 1), None)],
        'LU': [(None, None)],
        'LV': [(dt.date(2004, 5, 1), None)],
        'MT': [(dt.date(2004, 5, 1), None)],
        'NL': [(None, None)],
        'PL': [(dt.date(2004, 5, 1), None)],
        'PT': [(dt.date(1986, 1, 1), None)],
        'RO': [(dt.date(2007, 1, 1), None)],
        'SE': [(dt.date(1995, 1, 1), None)],
        'SI': [(dt.date(2004, 5, 1), None)],
        'SK': [(dt.date(2004, 5, 1), None)],
        },
    'Benelux': {
        'BE': [(None, None)],
        'LU': [(None, None)],
        'NL': [(None, None)],
        },
    'NAFTA': {
        'CA': [(None, None)],
        'MX': [(None, None)],
        'US': [(None, None)],
        },
    'Mercosur': {
        'AR': [(None, None)],
        'BR': [(None, None)],
        'PY': [(None, None)],
        'UY': [(None, None)],
        'VE': [(dt.date(2012, 7, 31), dt.date(2016, 12, 2))],
        },
    'CAN': {
        # days and months are default to covert the full year
        'BO': [(None, None)],
        'CL': [(dt.date(1969, 1, 1), dt.date(1976, 12, 31))],
        'CO': [(None, None)],
        'EC': [(None, None)],
        'PE': [(None, None)],
        'VE': [(dt.date(1973, 1, 1), dt.date(2006, 12, 31))],
        },
    'CARICOM': {
        'AG': [(dt.date(1974, 7, 4), None)],
        'BB': [(None, None)],
        'BS': [(dt.date(1983, 7, 4), None)],
        'BZ': [(dt.date(1974, 5, 1), None)],
        'DM': [(dt.date(1974, 5, 1), None)],
        'GD': [(dt.date(1974, 5, 1), None)],
        'GY': [(None, None)],
        'HT': [(dt.date(2002, 7, 2), None)],
        'JM': [(None, None)],
        'KN': [(dt.date(1974, 7, 26), None)],
        'LC': [(dt.date(1974, 5, 1), None)],
        'MS': [(dt.date(1974, 5, 1), None)],
        'SR': [(dt.date(1995, 7, 4), None)],
        'TT': [(None, None)],
        'VC': [(dt.date(1974, 5, 1), None)],
        },
    'APEC': {
        # days are default to covert the full month
        'AU': [(None, None)],
        'BN': [(None, None)],
        'CA': [(None, None)],
        'CL': [(dt.date(1994, 11, 1), None)],
        'CN': [(dt.date(1991, 11, 1), None)],
        'HK': [(dt.date(1991, 11, 1), None)],
        'ID': [(None, None)],
        'JP': [(None, None)],
        'KR': [(None, None)],
        'MX': [(dt.date(1993, 11, 1), None)],
        'MY': [(None, None)],
        'NZ': [(None, None)],
        'PE': [(dt.date(1998, 11, 1), None)],
        'PG': [(dt.date(1993, 11, 1), None)],
        'PH': [(None, None)],
        'RU': [(dt.date(1998, 11, 1), None)],
        'SG': [(None, None)],
        'TH': [(None, None)],
        'TW': [(dt.date(1991, 11, 1), None)],
        'US': [(None, None)],
        'VN': [(dt.date(1998, 11, 1), None)],
        },
    'ASEAN': {
        'BN': [(dt.date(1984, 1, 7), None)],
        'ID': [(None, None)],
        'KH': [(dt.date(1999, 4, 30), None)],
        'LA': [(dt.date(1997, 7, 23), None)],
        'MM': [(dt.date(1997, 7, 23), None)],
        'MY': [(None, None)],
        'PH': [(None, None)],
        'SG': [(None, None)],
        'TH': [(None, None)],
        'VN': [(dt.date(1995, 7, 28), None)],
        },
    'SAFTA': {
        'AF': [(None, None)],
        'BD': [(None, None)],
        'BT': [(None, None)],
        'IN': [(None, None)],
        'LK': [(None, None)],
        'MV': [(None, None)],
        'NP': [(None, None)],
        'PK': [(None, None)],
        },
    'GCC': {
        'AE': [(None, None)],
        'BH': [(None, None)],
        'KW': [(None, None)],
        'OM': [(None, None)],
        'QA': [(None, None)],
        'SA': [(None, None)],
        },
    'CEMAC': {
        'CF': [(None, None)],
        'CG': [(None, None)],
        'CM': [(None, None)],
        'GA': [(None, None)],
        'GQ': [(dt.date(1983, 12, 19), None)],
        'TD': [(None, None)],
        },
    'ECCAS': {
        'AO': [(None, None)],
        'BI': [(None, None)],
        'CM': [(None, None)],
        'CF': [(None, None)],
        'TD': [(None, None)],
        'CD': [(None, None)],
        'GQ': [(None, None)],
        'GA': [(None, None)],
        'CG': [(None, None)],
        'RW': [(None, dt.date(2007, 12, 31)), (dt.date(2016, 8, 17), None)],
        'ST': [(None, None)],
        },
    'ECOWAS': {
        'BF': [(None, dt.date(2022, 1, 28))],
        'BJ': [(None, None)],
        'CI': [(None, None)],
        'CV': [(dt.date(1977, 1, 1), None)],
        'GH': [(None, None)],
        'GM': [(None, None)],
        'GN': [(None, dt.date(2021, 9, 8))],
        'GW': [(None, None)],
        'LR': [(None, None)],
        'ML': [(None, dt.date(2021, 5, 30))],
        'MR': [(None, dt.date(2000, 12, 1))],
        'NE': [(None, None)],
        'NG': [(None, None)],
        'SL': [(None, None)],
        'SN': [(None, None)],
        'TG': [(None, None)],
        },
    'CEN-SAD': {
        # days and months are default to covert the full year
        'BF': [(None, None)],
        'BJ': [(dt.date(2002, 1, 1), None)],
        'CF': [(dt.date(1999, 1, 1), None)],
        'CI': [(dt.date(2004, 1, 1), None)],
        'CV': [(dt.date(2009, 1, 1), None)],
        'DJ': [(dt.date(2000, 1, 1), None)],
        'EG': [(dt.date(2001, 1, 1), None)],
        'ER': [(dt.date(1999, 1, 1), None)],
        'FN': [(dt.date(2007, 1, 1), None)],
        'GH': [(dt.date(2005, 1, 1), None)],
        'GM': [(dt.date(2000, 1, 1), None)],
        'GW': [(dt.date(2004, 1, 1), None)],
        'KE': [(dt.date(2007, 1, 1), None)],
        'KM': [(dt.date(2007, 1, 1), None)],
        'LR': [(dt.date(2004, 1, 1), None)],
        'LY': [(None, None)],
        'MA': [(dt.date(2001, 1, 1), None)],
        'ML': [(None, None)],
        'MR': [(dt.date(2007, 1, 1), None)],
        'NE': [(None, None)],
        'NG': [(dt.date(2001, 1, 1), None)],
        'SD': [(None, None)],
        'SL': [(dt.date(2005, 1, 1), None)],
        'SN': [(dt.date(2000, 1, 1), None)],
        'SO': [(dt.date(2001, 1, 1), None)],
        'ST': [(dt.date(2007, 1, 1), None)],
        'TD': [(None, None)],
        'TG': [(dt.date(2002, 1, 1), None)],
        'TN': [(dt.date(2001, 1, 1), None)],
        },
    'COMESA': {
        # days and months are default to covert the full year
        'AO': [(None, dt.date(2007, 1, 1))],
        'BI': [(dt.date(1981, 12, 21), None)],
        'CD': [(dt.date(1981, 12, 21), None)],
        'DJ': [(dt.date(1981, 12, 21), None)],
        'EG': [(dt.date(1999, 1, 6), None)],
        'ER': [(dt.date(1994, 1, 1), None)],
        'ET': [(dt.date(1981, 12, 21), None)],
        'KE': [(None, None)],
        'KM': [(dt.date(1981, 12, 21), None)],
        'LS': [(None, dt.date(1997, 1, 1))],
        'LY': [(dt.date(2005, 6, 3), None)],
        'MG': [(None, None)],
        'MU': [(None, None)],
        'MW': [(None, None)],
        'MZ': [(None, dt.date(1997, 1, 1))],
        'NA': [(None, dt.date(2004, 5, 2))],
        'RW': [(None, None)],
        'SC': [(dt.date(2001, 1, 1), None)],
        'SD': [(dt.date(1981, 12, 21), None)],
        'SO': [(dt.date(2018, 7, 19), None)],
        'SZ': [(dt.date(1981, 12, 21), None)],
        'TN': [(dt.date(2018, 7, 18), None)],
        'TZ': [(None, dt.date(2000, 9, 2))],
        'UG': [(None, None)],
        'ZM': [(None, None)],
        'ZW': [(None, None)],
        },
    'EAC': {
        # days and months are default to covert the full year
        'BI': [(dt.date(2007, 1, 1), None)],
        'CD': [(dt.date(2022, 1, 1), None)],
        'KE': [(None, None)],
        'RW': [(dt.date(2007, 1, 1), None)],
        'SS': [(dt.date(2012, 1, 1), None)],
        'TZ': [(None, None)],
        'UG': [(None, None)],
        },
    'IGAD': {
        # days and months are default to covert the full year
        'DJ': [(None, None)],
        'ER': [(dt.date(1993, 1, 1), dt.date(2007, 12, 31)),
            (dt.date(2011, 1, 1), None)],
        'ET': [(None, None)],
        'KE': [(None, None)],
        'SD': [(None, None)],
        'SO': [(None, None)],
        'SS': [(dt.date(2011, 1, 1), dt.date(2021, 12, 1))],
        'UG': [(None, None)],
        },
    'SADC': {
        'AO': [(None, None)],
        'BW': [(None, None)],
        'CD': [(dt.date(1997, 9, 8), None)],
        'KM': [(dt.date(2017, 1, 1), None)],
        'LS': [(None, None)],
        'MG': [(dt.date(2005, 8, 18), dt.date(2009, 1, 26)),
            (dt.date(2014, 1, 30), None)],
        'MU': [(dt.date(1995, 8, 28), None)],
        'MW': [(None, None)],
        'MZ': [(None, None)],
        'NA': [(dt.date(1990, 3, 21), None)],
        'SC': [(dt.date(1997, 9, 8), dt.date(2004, 7, 1)),
            (dt.date(2008, 1, 1), None)],
        'SZ': [(None, None)],
        'TZ': [(None, None)],
        'ZA': [(dt.date(1994, 8, 30), None)],
        'ZM': [(None, None)],
        'ZW': [(None, None)],
        },
    'AMU': {
        'DZ': [(None, None)],
        'LY': [(None, None)],
        'MA': [(None, None)],
        'MR': [(None, None)],
        'TN': [(None, None)],
        },
    }

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


def _progress(iterable, **kwargs):
    if tqdm:
        return tqdm(iterable, disable=None, **kwargs)
    else:
        return iterable


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


def get_organizations():
    Organization = Model.get('country.organization')
    return {o.code: o for o in Organization.find([])}


def update_countries(countries):
    print("Update countries", file=sys.stderr)
    Region = Model.get('country.region')
    Country = Model.get('country.country')
    Member = Model.get('country.organization.member')

    organizations = get_organizations()

    code2region = {a.code_numeric: a for a in Region.find([])}

    records = []
    for country in _progress(pycountry.countries):
        code = country.alpha_2
        if code in countries:
            record = countries[code]
        else:
            record = Country(code=code, members=[])
        record.name = _remove_forbidden_chars(country.name)
        record.code3 = country.alpha_3
        record.code_numeric = country.numeric
        record.region = code2region.get(REGION2PARENT.get(country.numeric))
        for organization_code, members in ORGANIZATIONS.items():
            if organization_code in organizations and code in members:
                organization = organizations[organization_code]
                dates = members[code].copy()
                for member in list(record.members):
                    if member.organization == organization:
                        if dates:
                            member.from_date, member.to_date = dates.pop()
                        else:
                            record.members.remove(member)
                for from_date, to_date in dates:
                    record.members.append(Member(
                            organization=organization,
                            from_date=from_date,
                            to_date=to_date))
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
