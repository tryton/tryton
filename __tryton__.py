{
    'name': 'Analytic Account',
    'version': '0.1',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'category': 'Accounting',
    'description': 'Financial and Accounting Module',
    'depends': [
        'ir',
        'company',
        'currency',
        'account',
        'relationship',
        'res',
    ],
    'xml': [
        'analytic_account.xml',
        'account.xml',
        'line.xml',
    ],
}
