#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
"Properties"
from trytond.model import ModelView, ModelSQL, fields
from decimal import Decimal


class Property(ModelSQL, ModelView):
    "Property"
    _name = 'ir.property'
    _description = __doc__
    name = fields.Char('Name')
    value = fields.Reference('Value', selection='models_get')
    res = fields.Reference('Resource', selection='models_get', select=1)
    field = fields.Many2One('ir.model.field', 'Field',
        ondelete='CASCADE', required=True, select=1)

    def models_get(self, cursor, user, context=None):
        cursor.execute('SELECT model, name FROM ir_model ORDER BY name ASC')
        res = cursor.fetchall() + [('', '')]
        return res

    def get(self, cursor, user, names, model, res_ids=None, context=None):
        """
        Return property value for each res_ids
        :param cursor: the database cursor
        :param user: the user id
        :param names: property name or a list of property names
        :param model: object name
        :param res_ids: a list of record ids
        :param context: the context
        :return: a dictionary
        """
        model_field_obj = self.pool.get('ir.model.field')
        model_access_obj = self.pool.get('ir.model.access')
        res = {}

        model_access_obj.check(cursor, user, model, 'read', context=context)

        names_list = True
        if not isinstance(names, list):
            names_list = False
            names = [names]

        field_ids = model_field_obj.search(cursor, user, [
            ('name', 'in', names),
            ('model.model', '=', model),
            ], order=[], context=context)
        fields = model_field_obj.browse(cursor, user, field_ids, context=context)

        default_ids = self.search(cursor, user, [
            ('field', 'in', field_ids),
            ('res', '=', False),
            ], order=[], context=context)
        default_vals = dict((x, False) for x in names)
        if default_ids:
            for property in self.browse(cursor, user, default_ids,
                    context=context):
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

        id_found = {}

        if not res_ids:
            for field in fields:
                if field.ttype == 'many2one':
                    obj = self.pool.get(field.relation)
                    id_found.setdefault(field.relation, set())
                    if default_vals[field.name] not in id_found[field.relation]\
                            and not obj.search(cursor, user, [
                                ('id', '=', default_vals[field.name]),
                                ], order=[], context=context):
                        default_vals[field.name] = False
                    if default_vals[field.name]:
                        id_found[field.relation].add(default_vals[field.name])
            if not names_list:
                return default_vals[names[0]]
            return default_vals

        for name in names:
            res[name] = dict((x, default_vals[name]) for x in res_ids)

        property_ids = self.search(cursor, user, [
            ('field', 'in', field_ids),
            ('res', 'in', [model + ',' + str(obj_id) \
                    for obj_id in  res_ids]),
            ], order=[], context=context)
        for property in self.browse(cursor, user, property_ids,
                context=context):
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

        for field in fields:
            if field.ttype == 'many2one':
                obj = self.pool.get(field.relation)
                id_found.setdefault(field.relation, set())
                if set(res[field.name].values()).issubset(
                        id_found[field.relation]):
                    continue
                obj_ids = obj.search(cursor, user, [
                    ('id', 'in', res[field.name].values()),
                    ], order=[], context=context)
                id_found[field.relation].update(obj_ids)
                for res_id in res[field.name]:
                    if res[field.name][res_id] not in obj_ids:
                        res[field.name][res_id] = False
        if not names_list:
            return res[names[0]]
        return res

    def _set_values(self, cursor, user, name, model, res_id, val, field_id,
            context=None):
        return {
            'name': name,
            'value': val,
            'res': model + ',' + str(res_id),
            'field': field_id,
        }

    def set(self, cursor, user, name, model, ids, val, context=None):
        """
        Set property value for ids
        :param cursor: the database cursor
        :param user: the user id
        :param names: property name
        :param model: object name
        :param ids: a list of ids
        :param val: the value
        :param context: the context
        :return: the id of the record created
        """
        model_field_obj = self.pool.get('ir.model.field')
        model_access_obj = self.pool.get('ir.model.access')

        model_access_obj.check(cursor, user, model, 'write', context=context)

        if context is None:
            context = {}
        ctx = context.copy()
        ctx['user'] = user

        field_id = model_field_obj.search(cursor, user, [
            ('name', '=', name),
            ('model.model', '=', model),
            ], order=[], limit=1, context=context)[0]
        field = model_field_obj.browse(cursor, user, field_id, context=context)

        property_ids = self.search(cursor, user, [
            ('field', '=', field_id),
            ('res', 'in', [model + ',' + str(res_id) for res_id in ids]),
            ], order=[], context=context)
        self.delete(cursor, 0, property_ids, context=ctx)

        default_id = self.search(cursor, user, [
            ('field', '=', field_id),
            ('res', '=', False),
            ], order=[], limit=1, context=context)
        default_val = False
        if default_id:
            value = self.browse(cursor, user, default_id[0],
                    context=context).value
            default_val = False
            if value:
                if value.split(',')[0]:
                    try:
                        default_val = int(value.split(',')[1]\
                                .split(',')[0].strip('('))
                    except ValueError:
                        default_val = False
                else:
                    if field.ttype == 'numeric':
                        default_val = Decimal(value.split(',')[1])
                    elif field.ttype in ('char', 'selection'):
                        default_val = value.split(',')[1]
                    else:
                        raise Exception('Not implemented')


        res = False
        if (val != default_val):
            for res_id in ids:
                vals = self._set_values(cursor, user, name, model, res_id, val,
                        field_id, context=context)
                res = self.create(cursor, 0, vals, context=ctx)
        return res

Property()
