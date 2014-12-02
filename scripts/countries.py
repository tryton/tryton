#!/usr/bin/env python
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import sys
import pycountry

sys.stdout.write(u'    <data skiptest="1" grouped="1">\n')
for country in pycountry.countries:
    record = u'''
        <record model="country.country" id="%s">
            <field name="name">%s</field>
            <field name="code">%s</field>
        </record>\n''' % (country.alpha2.lower(), country.name,
                country.alpha2)
    sys.stdout.write(record.encode('utf-8'))
sys.stdout.write(u'    </data>\n')

existing_parents = set()
while len(existing_parents) != len(pycountry.subdivisions):
    sys.stdout.write(u'    <data skiptest="1" grouped="1">\n')
    new_parents = set()
    for subdivision in pycountry.subdivisions:
        if (subdivision.code.lower() in existing_parents
                or (subdivision.parent_code
                    and subdivision.parent_code.lower() not in
                    existing_parents)):
            continue
        new_parents.add(subdivision.code.lower())
        # XXX fix for second level of regional divisions
        subdivision.country_code = subdivision.country_code.split(' ', 1)[0]
        record = u'''
        <record model="country.subdivision" id="%s">
            <field name="name">%s</field>
            <field name="code">%s</field>
            <field name="type">%s</field>\n''' % (subdivision.code.lower(),
                    subdivision.name, subdivision.code,
                    subdivision.type.lower())
        if subdivision.parent_code:
            record += u'''\
            <field name="parent" ref="%s"/>\n''' % \
                subdivision.parent.code.lower()
        record += u'''\
            <field name="country" ref="%s"/>
        </record>\n''' % subdivision.country.alpha2.lower()

        sys.stdout.write(record.encode('utf-8'))
    sys.stdout.write(u'    </data>\n')
    existing_parents |= new_parents
