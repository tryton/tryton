{
    'name': 'Account Invoice',
    'version': '0.1',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'category': 'Accounting',
    'description': 'Invoice',
    'depends': [
        'account',
        'company',
        'relationship',
        'product',
        'res',
        'workflow',
        'currency',
    ],
    'xml': [
        'invoice.xml',
    ],
}
