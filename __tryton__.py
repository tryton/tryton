{
    'name': 'Account',
    'version': '0.1',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'category': 'Generic Modules',
    'description': 'Financial and Accounting Module',
    'depends': [
        'ir',
        'res',
        'company',
        'partner',
    ],
    'xml': [
        'account.xml',
        'currency.xml',
        'fiscalyear.xml',
        'period.xml',
        'journal.xml',
        'move.xml',
        'tax.xml',
    ],
}
