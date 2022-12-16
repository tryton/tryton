#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import contextlib
from trytond.model.fields.field import Field
from trytond.transaction import Transaction
from trytond.pool import Pool


class Reference(Field):
    '''
    Define a reference field (``str``).
    '''
    _type = 'reference'

    def __init__(self, string='', selection=None, help='', required=False,
            readonly=False, domain=None, states=None, change_default=False,
            select=False, on_change=None, on_change_with=None, depends=None,
            order_field=None, context=None, loading='eager'):
        '''
        :param selection: A list or a function name that returns a list.
            The list must be a list of tuples. First member is an internal name
            of model and the second is the user name of model.
        '''
        super(Reference, self).__init__(string=string, help=help,
                required=required, readonly=readonly, domain=domain,
                states=states, change_default=change_default, select=select,
                on_change=on_change, on_change_with=on_change_with,
                depends=depends, order_field=order_field, context=context,
                loading=loading)
        self.selection = selection or None

    __init__.__doc__ += Field.__init__.__doc__

    def get(self, ids, model, name, values=None):
        '''
        Replace removed reference id by False.

        :param ids: a list of ids
        :param model: a string with the name of the model
        :param name: a string with the name of the field
        :param values: a dictionary with the read values
        :return: a dictionary with ids as key and values as value
        '''
        pool = Pool()
        if values is None:
            values = {}
        res = {}
        for i in values:
            res[i['id']] = i[name]
        ref_to_check = {}
        for i in ids:
            if not (i in res):
                res[i] = False
                continue
            if not res[i]:
                continue
            ref_model, ref_id = res[i].split(',', 1)
            if not ref_model:
                continue
            try:
                ref_id = int(ref_id)
            except Exception:
                continue
            if ref_id < 0:
                continue
            res[i] = ref_model + ',' + str(ref_id)
            ref_to_check.setdefault(ref_model, (set(), []))
            ref_to_check[ref_model][0].add(ref_id)
            ref_to_check[ref_model][1].append(i)

        # Check if reference ids still exist
        with contextlib.nested(Transaction().set_context(active_test=False),
                Transaction().set_user(0)):
            for ref_model, (ref_ids, ids) in ref_to_check.iteritems():
                if ref_model not in pool.object_name_list():
                    res.update(dict((i, False) for i in ids))
                    continue
                ref_obj = pool.get(ref_model)
                ref_ids = ref_obj.search([
                    ('id', 'in', list(ref_ids)),
                    ], order=[])
                refs = [ref_model + ',' + str(ref_id) for ref_id in ref_ids]
                for i in ids:
                    if res[i] not in refs:
                        res[i] = False
        return res
