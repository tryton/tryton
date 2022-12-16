#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from decimal import Decimal
from trytond.model import ModelView, ModelSQL, fields
from trytond.transaction import Transaction
from trytond.cache import Cache
from trytond.pool import Pool


class Property(ModelSQL, ModelView):
    "Property"
    _name = 'ir.property'
    _description = __doc__
    name = fields.Char('Name')
    value = fields.Reference('Value', selection='models_get')
    res = fields.Reference('Resource', selection='models_get', select=1)
    field = fields.Many2One('ir.model.field', 'Field',
        ondelete='CASCADE', required=True, select=1)

    @Cache('ir_property.models_get')
    def models_get(self):
        cursor = Transaction().cursor
        cursor.execute('SELECT model, name FROM ir_model ORDER BY name ASC')
        res = cursor.fetchall() + [('', '')]
        return res

    def get(self, names, model, res_ids=None):
        """
        Return property value for each res_ids
        :param names: property name or a list of property names
        :param model: object name
        :param res_ids: a list of record ids
        :return: a dictionary
        """
        pool = Pool()
        model_access_obj = pool.get('ir.model.access')
        res = {}

        model_access_obj.check(model, 'read')

        names_list = True
        if not isinstance(names, list):
            names_list = False
            names = [names]
        if res_ids is None:
            res_ids = []

        model_obj = pool.get(model)
        fields = dict((name, field)
                for name, field in model_obj._columns.iteritems()
                if name in names)

        property_ids = self.search([
            ('field.name', 'in', names),
            ['OR',
                ('res', '=', False),
                ('res', 'in', ['%s,%s' % (model, x) for x in res_ids]),
                ],
            ], order=[])
        properties = self.browse(property_ids)

        default_vals = dict((x, False) for x in names)
        for property in (x for x in properties if not x.res):
            value = property.value
            val = False
            if value:
                if value.split(',')[0]:
                    try:
                        val = int(value.split(',')[1]\
                                .split(',')[0].strip('('))
                    except ValueError:
                        val = False
                else:
                    if property.field.ttype == 'numeric':
                        val = Decimal(value.split(',')[1])
                    elif property.field.ttype in ('char', 'selection'):
                        val = value.split(',')[1]
                    else:
                        raise Exception('Not implemented')
            default_vals[property.field.name] = val

        if not res_ids:
            if not names_list:
                return default_vals[names[0]]
            return default_vals

        for name in names:
            res[name] = dict((x, default_vals[name]) for x in res_ids)

        for property in (x for x in properties if x.res):
            val = False
            if property.value:
                if property.value.split(',')[0]:
                    try:
                        val = int(property.value.split(',')[1]\
                                .split(',')[0].strip('('))
                    except ValueError:
                        val = False
                else:
                    if property.field.ttype == 'numeric':
                        val = Decimal(property.value.split(',')[1])
                    elif property.field.ttype in ('char', 'selection'):
                        val = property.value.split(',')[1]
                    else:
                        raise Exception('Not implemented')
            res[property.field.name][
                    int(property.res.split(',')[1].split(',')[0].strip('('))] = val

        if not names_list:
            return res[names[0]]
        return res

    def _set_values(self, name, model, res_id, val, field_id):
        return {
            'name': name,
            'value': val,
            'res': model + ',' + str(res_id),
            'field': field_id,
        }

    def set(self, name, model, ids, val):
        """
        Set property value for ids
        :param name: property name
        :param model: object name
        :param ids: a list of ids
        :param val: the value
        :return: the id of the record created
        """
        pool = Pool()
        model_field_obj = pool.get('ir.model.field')
        model_access_obj = pool.get('ir.model.access')

        model_access_obj.check(model, 'write')

        field_id = model_field_obj.search([
            ('name', '=', name),
            ('model.model', '=', model),
            ], order=[], limit=1)[0]
        model_obj = pool.get(model)
        field = model_obj._columns[name]

        property_ids = self.search([
            ('field', '=', field_id),
            ('res', 'in', [model + ',' + str(res_id) for res_id in ids]),
            ], order=[])
        with Transaction().set_user(0, set_context=True):
            self.delete(property_ids)

        default_id = self.search([
            ('field', '=', field_id),
            ('res', '=', False),
            ], order=[], limit=1)
        default_val = False
        if default_id:
            value = self.browse(default_id[0]).value
            default_val = False
            if value:
                if value.split(',')[0]:
                    try:
                        default_val = int(value.split(',')[1]\
                                .split(',')[0].strip('('))
                    except ValueError:
                        default_val = False
                else:
                    if field._type == 'numeric':
                        default_val = Decimal(value.split(',')[1])
                    elif field._type in ('char', 'selection'):
                        default_val = value.split(',')[1]
                    else:
                        raise Exception('Not implemented')


        res = False
        if (val != default_val):
            for res_id in ids:
                vals = self._set_values(name, model, res_id, val, field_id)
                with Transaction().set_user(0, set_context=True):
                    res = self.create(vals)
        return res

Property()
