{
    'name': 'Stock Management',
    'version': '0.1',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'category': 'Generic Modules',
    'description': 'Stock Management and Inventory Control',
    'depends': [
        'ir',
        'workflow',
        'relationship',
        'product',
        'company',
        'currency',
    ],
    'xml': [
        'product.xml',
        'location.xml',
        'packing.xml',
        'move.xml',
        'inventory.xml',
    ],
}
