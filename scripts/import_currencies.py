#!/usr/bin/env python3
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import gettext
import os
import sys
from argparse import ArgumentParser

import pycountry
from forex_python.converter import CurrencyCodes

try:
    from progressbar import ETA, Bar, ProgressBar, SimpleProgress
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


def _remove_forbidden_chars(name):
    from trytond.tools import remove_forbidden_chars
    return remove_forbidden_chars(name)


def get_currencies():
    Currency = Model.get('currency.currency')
    return {c.code: c for c in Currency.find([])}


def update_currencies(currencies):
    print("Update currencies", file=sys.stderr)
    Currency = Model.get('currency.currency')
    codes = CurrencyCodes()

    records = []
    for currency in _progress(pycountry.currencies):
        code = currency.alpha_3
        if code in currencies:
            record = currencies[code]
        else:
            record = Currency(code=code)
        record.name = _remove_forbidden_chars(currency.name)
        record.numeric_code = currency.numeric
        record.symbol = codes.get_symbol(currency.alpha_3) or currency.alpha_3
        records.append(record)

    Currency.save(records)
    return {c.code: c for c in records}


def translate_currencies(currencies):
    Currency = Model.get('currency.currency')

    current_config = config.get_config()
    for code in _get_language_codes():
        try:
            gnutranslation = gettext.translation(
                'iso4217', pycountry.LOCALES_DIR, languages=[code])
        except IOError:
            continue
        print("Update currencies %s" % code, file=sys.stderr)
        with current_config.set_context(language=code):
            records = []
            for currency in _progress(pycountry.currencies):
                record = Currency(currencies[currency.alpha_3].id)
                record.name = _remove_forbidden_chars(
                    gnutranslation.gettext(currency.name))
                records.append(record)
            Currency.save(records)


def main(database, config_file=None):
    config.set_trytond(database, config_file=config_file)
    with config.get_config().set_context(active_test=False):
        do_import()


def do_import():
    currencies = get_currencies()
    currencies = update_currencies(currencies)
    translate_currencies(currencies)


def run():
    parser = ArgumentParser()
    parser.add_argument('-d', '--database', dest='database', required=True)
    parser.add_argument('-c', '--config', dest='config_file',
        help='the trytond config file')

    args = parser.parse_args()
    main(args.database, args.config_file)


if __name__ == '__main__':
    run()
