# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
"Test for copy"
from trytond.model import ModelSQL, fields
from trytond.pool import Pool


class Copy(ModelSQL):
    "Copy"
    __name__ = 'test.copy'
    name = fields.Char("Name")


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


class CopyMany2Many(ModelSQL):
    "Copy Many2Many"
    __name__ = 'test.copy.many2many'
    name = fields.Char('Name')
    many2many = fields.Many2Many('test.copy.many2many.rel', 'many2many',
        'many2many_target', 'Many2Many')


class CopyMany2ManyTarget(ModelSQL):
    "Copy Many2Many Target"
    __name__ = 'test.copy.many2many.target'
    name = fields.Char('Name')


class CopyMany2ManyRelation(ModelSQL):
    "Copy Many2Many Relation"
    __name__ = 'test.copy.many2many.rel'
    name = fields.Char('Name')
    many2many = fields.Many2One('test.copy.many2many', 'Many2Many')
    many2many_target = fields.Many2One('test.copy.many2many.target',
        'Many2Many Target')


class CopyMany2ManyReference(ModelSQL):
    "Copy Many2ManyReference"
    __name__ = 'test.copy.many2many_reference'
    name = fields.Char('Name')
    many2many = fields.Many2Many('test.copy.many2many_reference.rel',
        'many2many', 'many2many_target', 'Many2Many')


class CopyMany2ManyReferenceTarget(ModelSQL):
    "Copy Many2ManyReference Target"
    __name__ = 'test.copy.many2many_reference.target'
    name = fields.Char('Name')


class CopyMany2ManyReferenceRelation(ModelSQL):
    "Copy Many2ManyReference Relation"
    __name__ = 'test.copy.many2many_reference.rel'
    name = fields.Char('Name')
    many2many = fields.Reference('Many2Many', [
            (None, ''),
            ('test.copy.many2many_reference', 'Many2Many'),
            ])
    many2many_target = fields.Many2One('test.copy.many2many_reference.target',
        'Many2ManyReference Target')


class CopyBinary(ModelSQL):
    "Copy Binary"
    __name__ = 'test.copy.binary'
    binary = fields.Binary("Binary")
    binary_id = fields.Binary("Binary with ID", file_id='file_id')
    file_id = fields.Char("Binary ID")


def register(module):
    Pool.register(
        Copy,
        CopyOne2Many,
        CopyOne2ManyTarget,
        CopyOne2ManyReference,
        CopyOne2ManyReferenceTarget,
        CopyMany2Many,
        CopyMany2ManyTarget,
        CopyMany2ManyRelation,
        CopyMany2ManyReference,
        CopyMany2ManyReferenceTarget,
        CopyMany2ManyReferenceRelation,
        CopyBinary,
        module=module, type_='model')
