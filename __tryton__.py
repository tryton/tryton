{
    'name': 'Bank Statement',
    'version': '0.1',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'category': 'Accounting',
    'description': 'Bank Statement Module',
    'depends': [
        'account',
        'company',
        'currency',
        'relationship',
        ],
    'xml': [
        'statement.xml',
        'journal.xml',
        ],
    }
