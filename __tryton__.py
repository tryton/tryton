{
    'name': 'Timesheet',
    'version': '0.1',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'category': 'Human Resources',
    'description': 'Timesheet Module',
    'depends': [
        'ir',
        'res',
        'company',
    ],
    'xml': [
        'timesheet.xml',
        'work.xml',
        'line.xml',
    ],
}
