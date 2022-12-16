#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
"Test for Tree"
from trytond.model import ModelView, ModelSQL, fields

__all__ = [
    'MPTT',
    ]


class MPTT(ModelSQL, ModelView):
    'Modified Preorder Tree Traversal'
    __name__ = 'test.mptt'
    name = fields.Char('Name', required=True)
    sequence = fields.Integer('Sequence',
        order_field='(%(table)s.sequence IS NULL) %(order)s, '
        '%(table)s.sequence %(order)s')
    parent = fields.Many2One('test.mptt', "Parent", select=True,
            left="left", right="right")
    left = fields.Integer('Left', required=True, select=True)
    right = fields.Integer('Right', required=True, select=True)
    childs = fields.One2Many('test.mptt', 'parent', 'Children')
    active = fields.Boolean('Active')

    @classmethod
    def __setup__(cls):
        super(MPTT, cls).__setup__()
        cls._order.insert(0, ('sequence', 'ASC'))

    @classmethod
    def validate(cls, record):
        super(MPTT, cls).validate(record)
        cls.check_recursion(record)

    @staticmethod
    def default_active():
        return True

    @staticmethod
    def default_left():
        return 0

    @staticmethod
    def default_right():
        return 0
