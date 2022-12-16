# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import os
import pprint
import time

from lxml import etree

from . import locale


def locale_strftime(lang):
    time_locale = {
        '%a': [],
        '%A': [],
        '%b': [None],
        '%B': [None],
        '%p': [],
    }
    locale.setlocale(locale.LC_ALL, locale.normalize(lang + '.UTF_8'))
    t = list(time.gmtime())
    for i in range(12):
        t[1] = i + 1
        for format in ('%b', '%B'):
            time_locale[format].append(time.strftime(format,
                t).decode('utf-8'))
    for i in range(7):
        t[6] = i
        for format in ('%a', '%A'):
            time_locale[format].append(time.strftime(format,
                t).decode('utf-8'))
    t[3] = 0
    time_locale['%p'].append(time.strftime('%p', t).decode('utf-8'))
    t[3] = 23
    time_locale['%p'].append(time.strftime('%p', t).decode('utf-8'))
    return time_locale


if __name__ == '__main__':
    base = os.path.dirname(__file__)
    # Add en as it is not defined in lang.xml
    time_locale = {
        'en': locale_strftime('en'),
        }
    with open(os.path.join(base, 'lang.xml'), 'rb') as fp:
        lang_xml = etree.parse(fp)
        for el in lang_xml.xpath('//field[@name="code"]'):
            lang = el.text[:2]
            time_locale[lang] = locale_strftime(lang)
    with open(os.path.join(base, 'time_locale.py'), 'w') as fp:
        fp.write('''# -*- coding: utf-8 -*-
# This file is part of Tryton.  The COPYRIGHT file at the top level of')
# this repository contains the full copyright notices and license terms.')
''')
        fp.write('TIME_LOCALE = \\\n')
        pp = pprint.PrettyPrinter(stream=fp)
        pp.pprint(time_locale)
