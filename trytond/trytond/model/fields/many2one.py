#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from types import NoneType

from trytond.model.fields.field import Field
from trytond.pool import Pool


class Many2One(Field):
    '''
    Define many2one field (``int``).
    '''
    _type = 'many2one'

    def __init__(self, model_name, string='', left=None, right=None,
            ondelete='SET NULL', datetime_field=None, help='', required=False,
            readonly=False, domain=None, states=None, select=False,
            on_change=None, on_change_with=None, depends=None,
            order_field=None, context=None, loading='eager'):
        '''
        :param model_name: The name of the target model.
        :param left: The name of the field to store the left value for
            Modified Preorder Tree Traversal.
            See http://en.wikipedia.org/wiki/Tree_traversal
        :param right: The name of the field to store the right value. See left
        :param ondelete: Define the behavior of the record when the target
            record is deleted. (``CASCADE``, ``RESTRICT``, ``SET NULL``)
            ``SET NULL`` will be changed into ``RESTRICT`` if required is set.
        :param datetime_field: The name of the field that contains the datetime
            value to read the target record.
        '''
        self.__required = required
        if ondelete not in ('CASCADE', 'RESTRICT', 'SET NULL'):
            raise Exception('Bad arguments')
        self.ondelete = ondelete
        if datetime_field:
            if depends:
                depends.append(datetime_field)
            else:
                depends = [datetime_field]
        super(Many2One, self).__init__(string=string, help=help,
            required=required, readonly=readonly, domain=domain, states=states,
            select=select, on_change=on_change, on_change_with=on_change_with,
            depends=depends, order_field=order_field, context=context,
            loading=loading)
        self.model_name = model_name
        self.left = left
        self.right = right
        self.datetime_field = datetime_field
    __init__.__doc__ += Field.__init__.__doc__

    def __get_required(self):
        return self.__required

    def __set_required(self, value):
        self.__required = value
        if value and self.ondelete == 'SET NULL':
            self.ondelete = 'RESTRICT'

    required = property(__get_required, __set_required)

    def get_target(self):
        'Return the target Model'
        return Pool().get(self.model_name)

    def __set__(self, inst, value):
        Target = self.get_target()
        if isinstance(value, dict):
            value = Target(**value)
        elif isinstance(value, (int, long)):
            value = Target(value)
        assert isinstance(value, (Target, NoneType))
        super(Many2One, self).__set__(inst, value)
