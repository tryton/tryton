#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

from trytond.model.fields.field import Field


class Float(Field):
    '''
    Define a float field (``float``).
    '''
    _type = 'float'

    def __init__(self, string='', digits=None,  help='', required=False,
            readonly=False, domain=None, states=None, priority=0,
            change_default=False, translate=False, select=0, on_change=None,
            on_change_with=None, depends=None, order_field=None, context=None):
        '''
        :param digits: a list of two integers defining the total
            of digits and the number of decimals of the float.
        '''
        super(Float, self).__init__(string=string, help=help, required=required,
                readonly=readonly, domain=domain, states=states,
                priority=priority, change_default=change_default,
                translate=translate, select=select, on_change=on_change,
                on_change_with=on_change_with, depends=depends,
                order_field=order_field, context=context)
        self.digits = digits
    __init__.__doc__ += Field.__init__.__doc__
