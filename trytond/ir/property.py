# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal
from ..model import ModelView, ModelSQL, fields
from ..transaction import Transaction
from ..cache import Cache
from ..pool import Pool

__all__ = [
    'Property',
    ]

_CAST = {
    'numeric': Decimal,
    'integer': int,
    'float': float,
    }


class Property(ModelSQL, ModelView):
    "Property"
    __name__ = 'ir.property'
    _rec_name = 'field'
    value = fields.Reference('Value', selection='models_get')
    res = fields.Reference('Resource', selection='models_get', select=True)
    field = fields.Many2One('ir.model.field', 'Field',
        ondelete='CASCADE', required=True, select=True)
    _models_get_cache = Cache('ir_property.models_get', context=False)

    @classmethod
    def models_get(cls):
        pool = Pool()
        Model = pool.get('ir.model')
        models = cls._models_get_cache.get(None)
        if models:
            return models
        cursor = Transaction().cursor
        model = Model.__table__()
        cursor.execute(*model.select(model.model, model.name,
                order_by=model.name.asc))
        models = cursor.fetchall() + [('', '')]
        cls._models_get_cache.set(None, models)
        return models

    @classmethod
    def get(cls, names, model, res_ids=None):
        """
        Return named property values for each res_ids of model
        """
        pool = Pool()
        ModelAccess = pool.get('ir.model.access')
        res = {}

        ModelAccess.check(model, 'read')

        names_list = True
        if not isinstance(names, list):
            names_list = False
            names = [names]
        if res_ids is None:
            res_ids = []

        properties = cls.search([
            ('field.name', 'in', names),
            ['OR',
                ('res', '=', None),
                ('res', 'in', ['%s,%s' % (model, x) for x in res_ids]),
                ],
            ], order=[])

        default_vals = dict((x, None) for x in names)
        for property_ in (x for x in properties if not x.res):
            value = property_.value
            val = None
            if value is not None:
                if not isinstance(value, basestring):
                    val = int(value)
                else:
                    if property_.field.ttype in _CAST:
                        cast = _CAST[property_.field.ttype]
                        val = cast(value.split(',')[1])
                    elif property_.field.ttype in ('char', 'selection'):
                        val = value.split(',')[1]
                    else:
                        raise Exception('Not implemented')
            default_vals[property_.field.name] = val

        if not res_ids:
            if not names_list:
                return default_vals[names[0]]
            return default_vals

        for name in names:
            res[name] = dict((x, default_vals[name]) for x in res_ids)

        for property_ in (x for x in properties if x.res):
            val = None
            if property_.value is not None:
                if not isinstance(property_.value, basestring):
                    val = int(property_.value)
                else:
                    if property_.field.ttype in _CAST:
                        cast = _CAST[property_.field.ttype]
                        val = cast(property_.value.split(',')[1])
                    elif property_.field.ttype in ('char', 'selection'):
                        val = property_.value.split(',')[1]
                    else:
                        raise Exception('Not implemented')
            res[property_.field.name][int(property_.res)] = val

        if not names_list:
            return res[names[0]]
        return res

    @staticmethod
    def _set_values(model, res_id, val, field_id):
        return {
            'value': val,
            'res': model + ',' + str(res_id),
            'field': field_id,
        }

    @classmethod
    def set(cls, name, model, ids, val):
        """
        Set named property value for ids of model
        Return the id of the record created
        """
        pool = Pool()
        ModelField = pool.get('ir.model.field')
        ModelAccess = pool.get('ir.model.access')

        ModelAccess.check(model, 'write')

        model_field, = ModelField.search([
            ('name', '=', name),
            ('model.model', '=', model),
            ], order=[], limit=1)
        Model = pool.get(model)
        field = Model._fields[name]

        properties = cls.search([
            ('field', '=', model_field.id),
            ('res', 'in', [model + ',' + str(res_id) for res_id in ids]),
            ], order=[])
        cls.delete(properties)

        defaults = cls.search([
            ('field', '=', model_field.id),
            ('res', '=', None),
            ], order=[], limit=1)
        default_val = None
        if defaults:
            value = cls(defaults[0].id).value
            default_val = None
            if value is not None:
                if not isinstance(value, basestring):
                    default_val = int(value)
                else:
                    if field._type in _CAST:
                        cast = _CAST[field._type]
                        default_val = cast(value.split(',')[1])
                    elif field._type in ('char', 'selection'):
                        default_val = value.split(',')[1]
                    else:
                        raise Exception('Not implemented')

        if (val != default_val):
            for res_id in ids:
                vals = cls._set_values(model, res_id, val, model_field.id)
                cls.create([vals])
