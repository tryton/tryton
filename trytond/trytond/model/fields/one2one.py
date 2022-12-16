#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from types import NoneType

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
        for i, vals in res.iteritems():
            res[i] = vals[0] if vals else None
        return res

    def set(self, ids, model, name, value):
        '''
        Set the values.

        :param ids: A list of ids
        :param model: A string with the name of the model
        :param name: A string with the name of the field
        :param value: The id to link
        '''
        pool = Pool()
        Relation = pool.get(self.relation_name)
        relations = Relation.search([
                (self.origin, 'in', ids),
                ])
        Relation.delete(relations)
        if value:
            to_create = []
            for record_id in ids:
                to_create.append({
                        self.origin: record_id,
                        self.target: value,
                        })
            if to_create:
                Relation.create(to_create)

    def __set__(self, inst, value):
        Target = self.get_target()
        if isinstance(value, dict):
            value = Target(*value)
        elif isinstance(value, (int, long)):
            value = Target(value)
        assert isinstance(value, (Target, NoneType))
        Field.__set__(self, inst, value)
