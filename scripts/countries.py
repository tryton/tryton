#!/usr/bin/env python
#This file is part of Tryton.  The COPYRIGHT file at the top level of this repository contains the full copyright notices and license terms.

import pycountry

for country in pycountry.countries:
    print '''
        <record model="relationship.country" id="%s">
            <field name="name">%s</field>
            <field name="code">%s</field>
        </record>''' % (country.alpha2.lower(), country.name.encode('utf-8'),
                country.alpha2)

for subdivision in pycountry.subdivisions:
    if subdivision.type != 'State':
        continue
    #XXX fix for Saint Kitts and Nevis
    if subdivision.country_code in ('KN K', 'KN N'):
        subdivision.country_code = 'KN'
    print '''
        <record model="relationship.country.state" id="%s">
            <field name="name">%s</field>
            <field name="code">%s</field>
            <field name="country" ref="%s"/>
        </record>''' % (subdivision.code.lower(),
                subdivision.name.encode('utf-8'), subdivision.code,
                subdivision.country.alpha2.lower())

