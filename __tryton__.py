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
        'relationship',
        'stock',
        'account',
        'product',
        'account_invoice',
        'workflow',
        'res',
        'ir',
        'currency',
    ],
    'xml': [
        'purchase.xml',
    ],
}
