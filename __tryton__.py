{
    'name': 'Purchase',
    'version': '0.1',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'category': 'Generic Modules',
    'description': 'Purchase Management',
    'depends': [
        'company',
        'partner',
        'stock',
        'account',
        'product',
        'account_invoice',
        'workflow',
        'res',
        'ir',
    ],
    'xml': [
        'purchase.xml',
    ],
}
