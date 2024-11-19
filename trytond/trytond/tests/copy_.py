# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
"Test for copy"
from trytond.model import ModelSQL, fields
from trytond.pool import Pool


class Copy(ModelSQL):
    __name__ = 'test.copy'
    name = fields.Char("Name")


class CopyOne2Many(ModelSQL):
    __name__ = 'test.copy.one2many'
    name = fields.Char('Name')
    one2many = fields.One2Many('test.copy.one2many.target', 'one2many',
        'One2Many')


class CopyOne2ManyTarget(ModelSQL):
    __name__ = 'test.copy.one2many.target'
    name = fields.Char('Name')
    one2many = fields.Many2One('test.copy.one2many', 'One2Many')


class CopyOne2ManyReference(ModelSQL):
    __name__ = 'test.copy.one2many_reference'
    name = fields.Char('Name')
    one2many = fields.One2Many('test.copy.one2many_reference.target',
        'one2many', 'One2Many')


class CopyOne2ManyReferenceTarget(ModelSQL):
    __name__ = 'test.copy.one2many_reference.target'
    name = fields.Char('Name')
    one2many = fields.Reference('One2Many', [
            (None, ''),
            ('test.copy.one2many_reference', 'One2Many'),
            ])


class CopyMany2Many(ModelSQL):
    __name__ = 'test.copy.many2many'
    name = fields.Char('Name')
    many2many = fields.Many2Many('test.copy.many2many.rel', 'many2many',
        'many2many_target', 'Many2Many')


class CopyMany2ManyTarget(ModelSQL):
    __name__ = 'test.copy.many2many.target'
    name = fields.Char('Name')


class CopyMany2ManyRelation(ModelSQL):
    __name__ = 'test.copy.many2many.rel'
    name = fields.Char('Name')
    many2many = fields.Many2One('test.copy.many2many', 'Many2Many')
    many2many_target = fields.Many2One('test.copy.many2many.target',
        'Many2Many Target')


class CopyMany2ManyReference(ModelSQL):
    __name__ = 'test.copy.many2many_reference'
    name = fields.Char('Name')
    many2many = fields.Many2Many('test.copy.many2many_reference.rel',
        'many2many', 'many2many_target', 'Many2Many')


class CopyMany2ManyReferenceTarget(ModelSQL):
    __name__ = 'test.copy.many2many_reference.target'
    name = fields.Char('Name')


class CopyMany2ManyReferenceRelation(ModelSQL):
    __name__ = 'test.copy.many2many_reference.rel'
    name = fields.Char('Name')
    many2many = fields.Reference('Many2Many', [
            (None, ''),
            ('test.copy.many2many_reference', 'Many2Many'),
            ])
    many2many_target = fields.Many2One('test.copy.many2many_reference.target',
        'Many2ManyReference Target')


class CopyBinary(ModelSQL):
    __name__ = 'test.copy.binary'
    binary = fields.Binary("Binary")
    binary_id = fields.Binary("Binary with ID", file_id='file_id')
    file_id = fields.Char("Binary ID")


class CopyAccess(ModelSQL):
    __name__ = 'test.copy.access'
    name = fields.Char("Name")

    @classmethod
    def default_name(cls):
        return "Default"


class CopyTranslate(ModelSQL):
    __name__ = 'test.copy.translate'
    name = fields.Char("Name", translate=True)


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
        CopyAccess,
        CopyTranslate,
        module=module, type_='model')
