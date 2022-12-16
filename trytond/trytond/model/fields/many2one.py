#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

from trytond.model.fields.field import Field


class Many2One(Field):
    '''
    Define many2one field (``int``).
    '''
    _type = 'many2one'

    def __init__(self, model_name, string='', left=None, right=None,
            ondelete='SET NULL', datetime_field=None, help='', required=False,
            readonly=False, domain=None, states=None, priority=0,
            change_default=False, translate=False, select=0, on_change=None,
            on_change_with=None, depends=None, order_field=None, context=None):
        '''
        :param model_name: The name of the targeted model.
        :param left: The name of the field to store the left value for
            Modified Preorder Tree Traversal.
            See http://en.wikipedia.org/wiki/Tree_traversal
        :param right: The name of the field to store the right value. See left
        :param ondelete: Define the behavior of the record when the target
            record is deleted. (``CASCADE``, ``RESTRICT``, ``SET NULL``)
        :param datetime_field: The name of the field that contains the datetime
            value to read the target record.
        '''
        if datetime_field:
            if depends:
                depends.append(datetime_field)
            else:
                depends = [datetime_field]
        super(Many2One, self).__init__(string=string, help=help,
                required=required, readonly=readonly, domain=domain,
                states=states, priority=priority, change_default=change_default,
                translate=translate, select=select, on_change=on_change,
                on_change_with=on_change_with, depends=depends,
                order_field=order_field, context=context)
        self.model_name = model_name
        self.left = left
        self.right = right
        if ondelete not in ('CASCADE', 'RESTRICT', 'SET NULL'):
            raise Exception('Bad arguments')
        self.ondelete = ondelete
        self.datetime_field = datetime_field
    __init__.__doc__ += Field.__init__.__doc__
