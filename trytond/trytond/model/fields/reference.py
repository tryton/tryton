#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

from trytond.model.fields.field import Field
from trytond.tools import safe_eval


class Reference(Field):
    '''
    Define a reference field (``str``).
    '''
    _type = 'reference'

    def __init__(self, string='', selection=None, help='', required=False,
            readonly=False, domain=None, states=None, priority=0,
            change_default=False, select=0, on_change=None,
            on_change_with=None, depends=None, order_field=None, context=None):
        '''
        :param selection: A list or a function name that returns a list.
            The list must be a list of tuples. First member is an internal name
            of model and the second is the user name of model.
        '''
        super(Reference, self).__init__(string=string, help=help,
                required=required, readonly=readonly, domain=domain,
                states=states, priority=priority,
                change_default=change_default, select=select,
                on_change=on_change, on_change_with=on_change_with,
                depends=depends, order_field=order_field, context=context)
        self.selection = selection or None

    __init__.__doc__ += Field.__init__.__doc__

    def get(self, cursor, user, ids, model, name, values=None, context=None):
        '''
        Replace removed reference id by False.

        :param cursor: the database cursor
        :param user: the user id
        :param ids: a list of ids
        :param model: a string with the name of the model
        :param name: a string with the name of the field
        :param values: a dictionary with the read values
        :param context: the context
        :return: a dictionary with ids as key and values as value
        '''
        if context is None:
            context = {}
        if values is None:
            values = {}
        res = {}
        for i in values:
            res[i['id']] = i[name]
        ref_id_found = {}
        for i in ids:
            if not (i in res):
                res[i] = False
                continue
            if not res[i]:
                continue
            ref_model, ref_id = res[i].split(',', 1)
            if not ref_model:
                continue
            if ref_model not in model.pool.object_name_list():
                continue
            ref_obj = model.pool.get(ref_model)
            ref_id_found.setdefault(ref_model, set())
            try:
                ref_id = safe_eval(ref_id)
            except:
                pass
            try:
                ref_id = int(ref_id)
            except:
                continue
            ctx = context.copy()
            ctx['active_test'] = False
            if ref_id \
                and ref_id not in ref_id_found[ref_model] \
                and not ref_obj.search(cursor, user, [
                    ('id', '=', ref_id),
                    ], order=[], context=ctx):
                ref_id = False
            if ref_id:
                ref_id_found[ref_model].add(ref_id)
            res[i] = ref_model + ',' + str(ref_id)
        return res
