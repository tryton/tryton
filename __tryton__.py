# -*- coding: utf-8 -*-
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name' : 'Party Siret',
    'version' : '0.0.1',
    'author' : 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': 'Add SIRET/SIREN number on party',
    'depends' : [
        'ir',
        'party',
    ],
    'xml' : [
        'party.xml',
        'address.xml',
    ],
    'translation': [
    ],
}
