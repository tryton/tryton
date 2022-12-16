#!/usr/bin/env python
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

import pycountry

for country in pycountry.countries:
    print '''
        <record model="country.country" id="%s">
            <field name="name">%s</field>
            <field name="code">%s</field>
        </record>''' % (country.alpha2.lower(), country.name.encode('utf-8'),
                country.alpha2)

for subdivision in pycountry.subdivisions:
    #XXX fix for second level of regional divisions
    subdivision.country_code = subdivision.country_code.split(' ', 1)[0]
    print '''
        <record model="country.subdivision" id="%s">
            <field name="name">%s</field>
            <field name="code">%s</field>
            <field name="type">%s</field>''' % (subdivision.code.lower(),
                subdivision.name.encode('utf-8'), subdivision.code,
                subdivision.type.lower())
    if subdivision.parent_code:
        print '''\
                <field name="parent" ref="%s"/>''' % \
                subdivision.parent.code.lower()
    print '''\
            <field name="country" ref="%s"/>
        </record>''' % subdivision.country.alpha2.lower()
