#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Sales Leads and Opportunities',
    'version': '0.0.1',
    'author': 'Sharoon Thomas, Openlabs',
    'email': 'info@openlabs.co.in',
    'website': 'http://www.openlabs.co.in/',
    'description': '''Provides:
    - Leads
    - Leads to Opportunities conversion
    - Conversion Management
    - Record of lost leads
    - Opportunities to sale orders
''',
    'depends': [
        'party',
        'company',
        'product',
        'sale',
        'account',
        'stock',
        'currency',
    ],
    'xml': [
        'opportunity.xml',
        'party.xml',
    ],
    'translation': [
    ],
}
