# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model.fields.field import Field
from trytond.model.fields.many2many import Many2Many
from trytond.pool import Pool


class One2One(Many2Many):
    '''
    Define one2one field (``int``).
    '''
    _type = 'one2one'

    def get(self, ids, model, name, values=None):
        '''
        Return target record.

        :param ids: a list of ids
        :param model: a string with the name of the model
        :param name: a string with the name of the field
        :param values: a dictionary with the read values
        :return: a dictionary with ids as key and target id as value
        '''
        res = super(One2One, self).get(ids, model, name, values=values)
        for i, vals in res.items():
            res[i] = vals[0] if vals else None
        return res

    def set(self, Model, name, ids, value, *args):
        '''
        Set the values.
        '''
        pool = Pool()
        Relation = pool.get(self.relation_name)
        to_delete = []
        to_create = []
        args = iter((ids, value) + args)
        for ids, value in zip(args, args):
            relations = Relation.search([
                    (self.origin, 'in', ids),
                    ])
            to_delete.extend(relations)
            if value:
                for record_id in ids:
                    to_create.append({
                            self.origin: record_id,
                            self.target: value,
                            })
        # Ordered operations to avoid uniqueness/overlapping constraints
        if to_delete:
            Relation.delete(to_delete)
        if to_create:
            Relation.create(to_create)

    def __set__(self, inst, value):
        Target = self.get_target()
        if isinstance(value, dict):
            value = Target(*value)
        elif isinstance(value, int):
            value = Target(value)
        assert isinstance(value, (Target, type(None)))
        Field.__set__(self, inst, value)
