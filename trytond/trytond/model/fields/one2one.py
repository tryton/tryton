#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

from trytond.model.fields.many2many import Many2Many
from trytond.transaction import Transaction
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
            res[i] = vals[0] if vals else False
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
        relation_obj = pool.get(self.relation_name)
        relation_ids = relation_obj.search([
            (self.origin, 'in', ids),
            ])
        relation_obj.delete(relation_ids)
        if value:
            for record_id in ids:
                relation_obj.create({
                    self.origin: record_id,
                    self.target: value,
                    })
