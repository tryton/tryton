#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

from trytond.model.fields.field import Field


class Selection(Field):
    '''
    Define a selection field (``str``).
    '''
    _type = 'selection'

    def __init__(self, selection, string='', sort=True,
            selection_change_with=None, translate=True, help='',
            required=False, readonly=False, domain=None, states=None,
            select=False, on_change=None, on_change_with=None, depends=None,
            order_field=None, context=None, loading='eager'):
        '''
        :param selection: A list or a function name that returns a list.
            The list must be a list of tuples. First member is the value
            to store and the second is the value to display.
        :param sort: A boolean to sort or not the selections.
        '''
        super(Selection, self).__init__(string=string, help=help,
            required=required, readonly=readonly, domain=domain, states=states,
            select=select, on_change=on_change, on_change_with=on_change_with,
            depends=depends, order_field=order_field, context=context,
            loading=loading)
        if hasattr(selection, 'copy'):
            self.selection = selection.copy()
        else:
            self.selection = selection
        self.selection_change_with = selection_change_with
        self.sort = sort
        self.translate_selection = translate
    __init__.__doc__ += Field.__init__.__doc__
