#!/usr/bin/env python
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import sys
import pycountry

sys.stdout.write('<?xml version="1.0"?>\n')
sys.stdout.write('<tryton>\n')
sys.stdout.write('    <data skiptest="1" grouped="1">\n')

for country in pycountry.countries:
    record = '''
        <record model="country.country" id="%s">
            <field name="name">%s</field>
            <field name="code">%s</field>
            <field name="code3">%s</field>
            <field name="code_numeric">%s</field>
        </record>\n''' % (country.alpha_2.lower(), country.name,
                country.alpha_2, country.alpha_3, country.numeric)
    sys.stdout.write(record.encode('utf-8'))
sys.stdout.write('    </data>\n')

subdivision_codes = {s.code.lower() for s in pycountry.subdivisions}
existing_parents = set()
while existing_parents < subdivision_codes:
    sys.stdout.write('    <data skiptest="1" grouped="1">\n')
    new_parents = set()
    for subdivision in pycountry.subdivisions:
        if (subdivision.code.lower() in existing_parents
                or (subdivision.parent_code
                    and subdivision.parent_code.lower() not in
                    existing_parents)):
            continue
        new_parents.add(subdivision.code.lower())
        record = '''
        <record model="country.subdivision" id="%s">
            <field name="name">%s</field>
            <field name="code">%s</field>
            <field name="type">%s</field>\n''' % (subdivision.code.lower(),
                    subdivision.name, subdivision.code,
                    subdivision.type.lower())
        if subdivision.parent_code:
            record += '''\
            <field name="parent" ref="%s"/>\n''' % \
                subdivision.parent.code.lower()
        record += '''\
            <field name="country" ref="%s"/>
        </record>\n''' % subdivision.country.alpha_2.lower()

        sys.stdout.write(record.encode('utf-8'))
    sys.stdout.write('    </data>\n')
    existing_parents |= new_parents

sys.stdout.write('</tryton>\n')
