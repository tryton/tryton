#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Project',
    'version': '0.0.1',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'category': 'Project',
    'description': 'Project Module',
    'depends': [
        'ir',
        'timesheet',
        'party',
    ],
    'xml': [
        'project.xml',
        'work.xml',
    ],
    'translation': [
        'de_DE.csv',
        'es_ES.csv',
    ],
}
