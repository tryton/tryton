#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
"Default"
from trytond.model import ModelView, ModelSQL, fields
from trytond.tools import Cache, safe_eval
from trytond.pyson import Eval
from decimal import Decimal
import datetime
import time


class Default(ModelSQL, ModelView):
    "Default"
    _name = 'ir.default'
    _description = __doc__
    _rec_name = 'value'
    model = fields.Many2One('ir.model', 'Model', required=True,
       ondelete='CASCADE')
    field = fields.Many2One('ir.model.field', 'Field', required=True,
       ondelete='CASCADE', domain=[('model', '=', Eval('model'))])
    value = fields.Text('Value')
    clause = fields.Text('Clause')
    user = fields.Many2One('res.user', 'User', ondelete='CASCADE')

    def __init__(self):
        super(Default, self).__init__()
        self._rpc.update({
            'get_default': False,
            'set_default': True,
            'reset_default': True,
        })

    @Cache('ir_default.get_default')
    def get_default(self, cursor, user, model, clause, context=None):
        res = {}
        test_user = user
        test_clause = clause
        default_ids = []
        while True:
            default_ids += self.search(cursor, user, [
                ('model.model', '=', model),
                ('clause', '=', test_clause),
                ('user', '=', test_user),
                ], context=context)
            if test_user:
                test_user = False
                continue
            if test_clause:
                test_clause = False
                continue
            break
        for default in self.browse(cursor, user, default_ids, context=context):
            if default.field.name not in res:
                if default.field.ttype in ('reference', 'char', 'sha', 'text',
                        'time', 'selection'):
                    res[default.field.name] = default.value
                elif default.field.ttype in ('integer', 'biginteger'):
                    res[default.field.name] = int(default.value)
                elif default.field.ttype == 'float':
                    res[default.field.name] = float(default.value)
                elif default.field.ttype == 'numeric':
                    res[default.field.name] = Decimal(default.value)
                elif default.field.ttype == 'date':
                    res[default.field.name] = datetime.date(*time.strptime(
                        default.value, '%Y-%m-%d')[:3])
                elif default.field.ttype == 'datetime':
                    res[default.field.name] = datetime.datetime(*time.strptime(
                        default.value, '%Y-%m-%d %H:%M:%S')[:6])
                else:
                    res[default.field.name] = safe_eval(default.value)
        return res

    def set_default(self, cursor, user, model, field, clause, value,
            user_default, context=None):
        ir_model_obj = self.pool.get('ir.model')
        ir_field_obj = self.pool.get('ir.model.field')

        model_obj = self.pool.get(model)
        if field not in model_obj._columns:
            model = self.pool.get(model_obj._inherit_fields[field][0])._name

        model_id = ir_model_obj.search(cursor, user, [
            ('model', '=', model),
            ], context=context)[0]
        field_id = ir_field_obj.search(cursor, user, [
            ('name', '=', field),
            ('model', '=', model_id),
            ], context=context)[0]
        default_ids = self.search(cursor, user, [
            ('model', '=', model_id),
            ('field', '=', field_id),
            ('clause', '=', clause),
            ('user', '=', user_default),
            ], context=context)
        if default_ids:
            self.delete(cursor, user, default_ids, context=context)
        self.create(cursor, user, {
            'model': model_id,
            'field': field_id,
            'value': str(value),
            'clause': clause,
            'user': user_default,
            }, context=context)

    def reset_default(self, cursor, user, model, field, clause, value,
            user_default, context=None):
        ir_model_obj = self.pool.get('ir.model')
        ir_field_obj = self.pool.get('ir.model.field')

        model_obj = self.pool.get(model)
        if field not in model_obj._columns:
            model = self.pool.get(model_obj._inherit_fields[field][0])._name

        model_id = ir_model_obj.search(cursor, user, [
            ('model', '=', model),
            ], context=context)[0]
        field_id = ir_field_obj.search(cursor, user, [
            ('name', '=', field),
            ('model', '=', model_id),
            ], context=context)[0]
        default_ids = self.search(cursor, user, [
            ('model', '=', model_id),
            ('field', '=', field_id),
            ('clause', '=', clause),
            ('user', '=', user_default),
            ], context=context)
        if default_ids:
            self.delete(cursor, user, default_ids, context=context)

    def create(self, cursor, user, vals, context=None):
        res = super(Default, self).create(cursor, user, vals, context=context)
        # Restart the cache for get_default method
        self.get_default(cursor.dbname)
        return res

    def write(self, cursor, user, ids, vals, context=None):
        res = super(Default, self).write(cursor, user, ids, vals, context=context)
        # Restart the cache for get_default method
        self.get_default(cursor.dbname)
        return res

    def delete(self, cursor, user, ids, context=None):
        res = super(Default, self).delete(cursor, user, ids, context=context)
        # Restart the cache for get_default method
        self.get_default(cursor.dbname)
        return res

Default()
