{
    'name': 'Project Revenue',
    'version': '0.1',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'category': 'Project',
    'description': 'Project Revenue Module',
    'depends': [
        'ir',
        'project',
        'company',
        'product',
    ],
    'xml': [
        'service.xml',
        'timesheet.xml',
    ],
}
