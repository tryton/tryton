#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Company',
    'version': '0.0.1',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'category': 'Generic',
    'description': '''Define company and employee.
Add main and current company on users preferences.
Add company on properties.
Define new report parser for report with company header.
Add letter template on party.
Make the cron run on each companies.
''',
    'depends': [
        'ir',
        'res',
        'party',
        'currency',
    ],
    'xml': [
        'company.xml',
        'cron.xml',
    ],
    'translation': [
        'fr_FR.csv',
        'de_DE.csv',
        'es_ES.csv',
    ]
}
