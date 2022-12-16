#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
"Test for copy"
from trytond.model import ModelSQL, fields

__all__ = [
    'CopyOne2Many', 'CopyOne2ManyTarget',
    'CopyOne2ManyReference', 'CopyOne2ManyReferenceTarget',
    ]


class CopyOne2Many(ModelSQL):
    "Copy One2Many"
    __name__ = 'test.copy.one2many'
    name = fields.Char('Name')
    one2many = fields.One2Many('test.copy.one2many.target', 'one2many',
        'One2Many')


class CopyOne2ManyTarget(ModelSQL):
    "Copy One2Many Target"
    __name__ = 'test.copy.one2many.target'
    name = fields.Char('Name')
    one2many = fields.Many2One('test.copy.one2many', 'One2Many')


class CopyOne2ManyReference(ModelSQL):
    "Copy One2Many Reference"
    __name__ = 'test.copy.one2many_reference'
    name = fields.Char('Name')
    one2many = fields.One2Many('test.copy.one2many_reference.target',
        'one2many', 'One2Many')


class CopyOne2ManyReferenceTarget(ModelSQL):
    "Copy One2Many ReferenceTarget"
    __name__ = 'test.copy.one2many_reference.target'
    name = fields.Char('Name')
    one2many = fields.Reference('One2Many', [
            (None, ''),
            ('test.copy.one2many_reference', 'One2Many'),
            ])
