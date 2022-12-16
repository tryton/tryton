#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
"""
 Fields:
      - simple
      - relations (one2many, many2one, many2many)
      - function

 Fields Attributes:
   _classic_read: is a classic sql fields
   _type   : field type
   readonly
   required
   size

 Relationals fields

 Values: ('create', { fields })         create
         ('write', ids, { fields })     modification
         ('delete', ids)                remove (delete)
         ('unlink', ids)                unlink one (target id or target of relation)
         ('add', ids)                   link
         ('unlink_all')                 unlink all
         ('set', ids)                   set a list of links
"""

import psycopg2
import warnings
import __builtin__
import sha
import inspect

def _symbol_f(symb):
    if symb is None or symb == False:
        return None
    elif isinstance(symb, str):
        return unicode(symb, 'utf-8')
    elif isinstance(symb, unicode):
        return symb
    return unicode(symb)

class Column(object):
    _classic_read = True
    _classic_write = True
    _properties = False
    _type = 'unknown'
    _obj = None
    _symbol_c = '%s'
    _symbol_f = _symbol_f
    _symbol_set = (_symbol_c, _symbol_f)
    _symbol_get = None

    def __init__(self, string='unknown', required=False, readonly=False,
            domain=None, context='', states=None, priority=0,
            change_default=False, size=None, ondelete="SET NULL",
            translate=False, select=0, on_change=None, on_change_with=None,
            **args):
        self.states = states or {}
        self.string = string
        self.readonly = readonly
        self.required = required
        self.size = size
        self.help = args.get('help', '')
        self.priority = priority
        self.change_default = change_default
        self.ondelete = ondelete
        self.translate = translate
        self._domain = domain or []
        self._context = context
        if select not in (0, 1, 2):
            raise Exception('Error', 'Select must be one of 0, 1, 2')
        self.select = select
        self.on_change = on_change
        self.on_change_with = on_change_with
        self.order_field = None
        for i in args:
            if args[i]:
                setattr(self, i, args[i])

    def set(self, cursor, obj, obj_id, name, value, user=None, context=None):
        raise Exception('undefined get method!')

    def get(self, cursor, obj, ids, name, user=None, offset=0, context=None,
            values=None):
        raise Exception('undefined get method!')

    def sql_type(self):
        raise Exception('undefined sql_type method!')


class Boolean(Column):
    _type = 'boolean'
    _symbol_c = '%s'
    _symbol_f = lambda x: x and 'True' or 'False'
    _symbol_set = (_symbol_c, _symbol_f)

    def sql_type(self):
        return ('bool', 'bool')


class Integer(Column):
    _type = 'integer'
    _symbol_c = '%s'
    _symbol_f = lambda x: int(x or 0)
    _symbol_set = (_symbol_c, _symbol_f)

    def sql_type(self):
        return ('int4', 'int4')


class BigInteger(Integer):
    _type = 'biginteger'

    def sql_type(self):
        return ('int8', 'int8')


class Reference(Column):
    _type = 'reference'
    _classic_read = False

    def __init__(self, string, selection, size=None, **args):
        Column.__init__(self, string=string, size=size, selection=selection,
                **args)

    def get(self, cursor, obj, ids, name, user=None, offset=0, context=None,
            values=None):
        if context is None:
            context = {}
        if values is None:
            values = {}
        res = {}
        for i in values:
            res[i['id']] = i[name]
        for i in ids:
            if not (i in res):
                res[i] = False
                continue
            if not res[i]:
                continue
            ref_model, ref_id = res[i].split(',', 1)
            if not ref_model:
                continue
            ref_obj = obj.pool.get(ref_model)
            if not ref_obj:
                continue
            try:
                ref_id = eval(ref_id)
            except:
                pass
            try:
                ref_id = int(ref_id)
            except:
                continue
            ctx = context.copy()
            ctx['active_test'] = False
            if ref_id \
                and not ref_obj.search(cursor, user, [
                    ('id', '=', ref_id),
                    ], context=ctx):
                ref_id = False
            if ref_id:
                ref_name = ref_obj.name_get(cursor, user, ref_id,
                        context=context)
                if ref_name:
                    ref_name = ref_name[0][1]
                else:
                    ref_name = ''
            else:
                ref_name = ''
            res[i] = ref_model + ',(' + str(ref_id) + ',"' + ref_name + '")'
        return res

    def sql_type(self):
        if self.size:
            return ('varchar', 'varchar(%d)' % (self.size,))
        else:
            return ('varchar', 'varchar')


class Char(Column):
    _type = 'char'

    def __init__(self, string, size=None, **args):
        Column.__init__(self, string=string, size=size, **args)

    def sql_type(self):
        if self.size:
            return ('varchar', 'varchar(%d)' % (self.size,))
        else:
            return ('varchar', 'varchar')


class Sha(Column):
    _type = 'sha'

    def __init__(self, string, **args):
        Column.__init__(self, string=string, size=40, **args)
        self._symbol_f = lambda x: x and sha.new(x).hexdigest() or ''
        self._symbol_set = (self._symbol_c, self._symbol_f)

    def sql_type(self):
        return ('varchar', 'varchar(40)')


class Text(Column):
    _type = 'text'

    def sql_type(self):
        return ('text', 'text')


class Float(Column):
    _type = 'float'
    _symbol_c = '%s'
    _symbol_f = lambda x: __builtin__.float(x or 0.0)
    _symbol_set = (_symbol_c, _symbol_f)

    def __init__(self, string='unknown', digits=None, **args):
        Column.__init__(self, string=string, **args)
        self.digits = digits

    def sql_type(self):
        return ('float8', 'float8')


class Numeric(Float):
    _type = 'numeric'

    def sql_type(self):
        return ('numeric', 'numeric')


class Date(Column):
    _type = 'date'

    def sql_type(self):
        return ('date', 'date')


class DateTime(Column):
    _type = 'datetime'

    def sql_type(self):
        return ('timestamp', 'timestamp(0)')


class Time(Column):
    _type = 'time'

    def sql_type(self):
        return ('time', 'time')


class Binary(Column):
    _type = 'binary'
    _symbol_c = '%s'
    _symbol_f = lambda symb: symb and psycopg2.Binary(symb) or None
    _symbol_set = (_symbol_c, _symbol_f)
    _symbol_get = lambda self, symb: symb and str(symb) or None

    def sql_type(self):
        return ('bytea', 'bytea')


class Selection(Column):
    _type = 'selection'

    def __init__(self, selections, string='unknown', sort=True, **args):
        """
        selections is a list of (key, string)
            or the name of the object function that return the list
        """
        self.sort = sort
        Column.__init__(self, string=string, selection=selections,
                **args)

    def sql_type(self):
        if self.size:
            return ('varchar', 'varchar(%d)' % (self.size,))
        else:
            return ('varchar', 'varchar')


class Many2One(Column):
    _classic_read = False
    _classic_write = True
    _type = 'many2one'
    _symbol_c = '%s'
    _symbol_f = lambda x: x and int(x) or None
    _symbol_set = (_symbol_c, _symbol_f)

    def __init__(self, obj, string='unknown', left=None, right=None, **args):
        Column.__init__(self, string=string, **args)
        self._obj = obj
        self.left = left
        self.right = right

    def get(self, cursor, obj, ids, name, user=None, offset=0, context=None,
            values=None):
        if values is None:
            values = {}
        res = {}
        for i in values:
            res[i['id']] = i[name]
        for i in ids:
            res.setdefault(i, '')
        obj = obj.pool.get(self._obj)
        obj_names = {}
        for obj_id, name in obj.name_get(cursor, user,
                [ x for x in res.values() if x],
                context=context):
            obj_names[obj_id] = name

        for i in res.keys():
            if res[i] and res[i] in obj_names:
                res[i] = (res[i], obj_names[res[i]])
            else:
                res[i] = False
        return res

    def set(self, cursor, obj_src, obj_id, field, values, user=None,
            context=None):
        obj = obj_src.pool.get(self._obj)
        table = obj_src.pool.get(self._obj)._table
        if type(values) == type([]):
            for act in values:
                if act[0] == 'create':
                    id_new = obj.create(cursor, user, act[2], context=context)
                    cursor.execute('UPDATE "' + obj_src._table + '" ' \
                            'SET "' + field + '" = %s ' \
                            'WHERE id = %s', (id_new, obj_id))
                elif act[0] == 'write':
                    obj.write(cursor, act[1], act[2], context=context)
                elif act[0] == 'delete':
                    obj.delete(cursor, user, act[1], context=context)
                    cursor.execute('DELETE FROM "' + table + '" ' \
                            'WHERE id = %s', (act[1],))
                elif act[0] == 'unlink' or act[0] == 'unlink_all':
                    cursor.execute('UPDATE "' + obj_src._table + '" ' \
                            'SET "' + field + '" = NULL ' \
                            'WHERE id = %s', (obj_id,))
                elif act[0] == 'add':
                    cursor.execute('UPDATE "' + obj_src._table + '" ' \
                            'SET "' + field + '" = %s ' \
                            'WHERE id = %s', (act[1], obj_id))
        else:
            if values:
                cursor.execute('UPDATE "' + obj_src._table + '" ' \
                        'SET "' + field + '" = %s ' \
                        'WHERE id = %s', (values, obj_id))
            else:
                cursor.execute('UPDATE "' + obj_src._table + '" ' \
                        'SET "' + field + '" = NULL ' \
                        'WHERE id = %s', (obj_id,))

    def sql_type(self):
        return ('int4', 'int4')


class One2Many(Column):
    _classic_read = False
    _classic_write = False
    _type = 'one2many'

    def __init__(self, obj, field, string='unknown', limit=None, order=None,
            **args):
        Column.__init__(self, string=string, **args)
        self._obj = obj
        self._field = field
        self._limit = limit
        self._order = order
        #one2many can't be used as condition for defaults
        assert(self.change_default != True)

    def get(self, cursor, obj, ids, name, user=None, offset=0, context=None,
            values=None):
        res = {}
        for i in ids:
            res[i] = []
        ids2 = []
        for i in range(0, len(ids), cursor.IN_MAX):
            sub_ids = ids[i:i + cursor.IN_MAX]
            ids2 += obj.pool.get(self._obj).search(cursor, user,
                    [(self._field, 'in', sub_ids)], order=self._order,
                    context=context)
            if self._limit and len(ids2) > offset + self._limit:
                break
        if offset:
            ids2 = ids2[offset:]
        if self._limit:
            ids2 = ids2[:self._limit]
        for i in obj.pool.get(self._obj)._read_flat(cursor, user, ids2,
                [self._field], context=context, load='_classic_write'):
            res[i[self._field]].append( i['id'] )
        return res

    def set(self, cursor, obj, obj_id, field, values, user=None, context=None):
        if not values:
            return
        _table = obj.pool.get(self._obj)._table
        obj = obj.pool.get(self._obj)
        for act in values:
            if act[0] == 'create':
                act[1][self._field] = obj_id
                obj.create(cursor, user, act[1], context=context)
            elif act[0] == 'write':
                act[2][self._field] = obj_id
                obj.write(cursor, user, act[1] , act[2], context=context)
            elif act[0] == 'delete':
                obj.delete(cursor, user, act[1], context=context)
            elif act[0] == 'unlink':
                if isinstance(act[1], (int, long)):
                    ids = [act[1]]
                else:
                    ids = list(act[1])
                if not ids:
                    continue
                cursor.execute('UPDATE "' + _table + '" ' \
                        'SET "' + self._field + '" = NULL ' \
                        'WHERE id IN (' \
                            + ','.join(['%s' for x in ids]) + ') ' \
                            'AND "' + self._field + '" = %s',
                        ids + [obj_id])
            elif act[0] == 'add':
                if isinstance(act[1], (int, long)):
                    ids = [act[1]]
                else:
                    ids = list(act[1])
                if not ids:
                    continue
                cursor.execute('UPDATE "' + _table + '" ' \
                        'SET "' + self._field + '" = %s ' \
                        'WHERE id IN (' \
                            + ','.join(['%s' for x in ids]) + ')',
                        [obj_id] + ids)
            elif act[0] == 'unlink_all':
                cursor.execute('UPDATE "' + _table + '" ' \
                        'SET "' + self._field + '" = NULL ' \
                        'WHERE "' + self._field + '" = %s', (obj_id,))
            elif act[0] == 'set':
                if not act[1]:
                    ids = [0]
                else:
                    ids = list(act[1])
                cursor.execute('UPDATE "' + _table + '" ' \
                        'SET "' + self._field + '" = NULL ' \
                        'WHERE "' + self._field + '" = %s ' \
                            'AND id not IN (' + \
                                ','.join(['%s' for x in ids]) + ')',
                                [obj_id] + ids)
                if act[1]:
                    cursor.execute('UPDATE "' + _table + '" ' \
                            'SET "' + self._field + '" = %s ' \
                            'WHERE id IN (' + \
                                ','.join(['%s' for x in ids]) + ')',
                                [obj_id] + ids)
            else:
                raise Exception('Bad arguments')


class Many2Many(Column):
    _classic_read = False
    _classic_write = False
    _type = 'many2many'

    def __init__(self, obj, rel, origin, target, string='unknown', limit=None,
            order=None, ondelete_origin='CASCADE', ondelete_target='RESTRICT',
            **args):
        Column.__init__(self, string=string, **args)
        self._obj = obj
        self._rel = rel
        self.origin = origin
        self.ondelete_origin = ondelete_origin
        self.target = target
        self.ondelete_target = ondelete_target
        self._limit = limit
        self._order = order

    def get(self, cursor, obj, ids, name, user=None, offset=0, context=None,
            values=None):
        if values is None:
            values = {}
        res = {}
        if not ids:
            return res
        for i in ids:
            res[i] = []
        ids_s = ','.join([str(x) for x in ids])
        limit_str = self._limit is not None and ' limit %s' % self._limit or ''
        obj = obj.pool.get(self._obj)

        domain1, domain2 = obj.pool.get('ir.rule').domain_get(cursor,
                user, obj._name, context=context)
        if domain1:
            domain1 = ' and '+domain1

        #TODO fix order: can have many fields
        cursor.execute('SELECT ' + self._rel + '.' + self.target + ', ' + \
                    self._rel + '.' + self.origin + ' ' \
                'FROM "' + self._rel + '" , "' + obj._table + '" ' \
                'WHERE ' + \
                    self._rel + '.' + self.origin + ' IN (' + ids_s + ') ' \
                    'AND ' + self._rel + '.' + self.target + ' = ' + \
                        obj._table + '.id ' + domain1 + \
                limit_str + ' ORDER BY ' + \
                ','.join([obj._table + '.' + x[0] + ' ' + x[1] \
                for x in (self._order or obj._order)]) + \
                ' OFFSET %s', domain2 + [offset])
        for i in cursor.fetchall():
            res[i[1]].append(i[0])
        return res

    def set(self, cursor, obj, obj_id, name, values, user=None, context=None):
        if not values:
            return
        obj = obj.pool.get(self._obj)
        for act in values:
            if act[0] == 'create':
                idnew = obj.create(cursor, user, act[1], context=context)
                cursor.execute('INSERT INTO "' + self._rel + '" ' \
                        '(' + self.origin + ', ' + self.target + ') ' \
                        'VALUES (%s, %s)', (obj_id, idnew))
            elif act[0] == 'write':
                obj.write(cursor, user, act[1] , act[2], context=context)
            elif act[0] == 'delete':
                obj.delete(cursor, user, act[1], context=context)
            elif act[0] == 'unlink':
                if isinstance(act[1], (int, long)):
                    ids = [act[1]]
                else:
                    ids = list(act[1])
                if not ids:
                    continue
                cursor.execute('DELETE FROM "' + self._rel + '" ' \
                        'WHERE "' + self.origin + '" = %s ' \
                            'AND "'+ self.target + '" IN (' \
                                + ','.join(['%s' for x in ids]) + ')',
                        [obj_id] + ids)
            elif act[0] == 'add':
                if isinstance(act[1], (int, long)):
                    ids = [act[1]]
                else:
                    ids = list(act[1])
                if not ids:
                    continue
                cursor.execute('SELECT "' + self.target + '" ' \
                        'FROM "' + self._rel + '" ' \
                        'WHERE "' + self.origin + '" = %s ' \
                            'AND "' + self.target + '" IN (' + \
                                ','.join(['%s' for x in ids]) + ')',
                        [obj_id] + ids)
                existing_ids = []
                for row in cursor.fetchall():
                    existing_ids.append(row[0])
                new_ids = [x for x in ids if x not in existing_ids]
                for new_id in new_ids:
                    cursor.execute('INSERT INTO "' + self._rel + '" ' \
                            '("' + self.origin + '", "' + self.target + '") ' \
                            'VALUES (%s, %s)', (obj_id, new_id))
            elif act[0] == 'unlink_all':
                cursor.execute('UPDATE "' + self._rel + '" ' \
                        'SET "' + self.target + '" = NULL ' \
                        'WHERE "' + self.target + '" = %s', (obj_id,))
            elif act[0] == 'set':
                if not act[1]:
                    ids = []
                else:
                    ids = list(act[1])
                domain1, domain2 = obj.pool.get('ir.rule').domain_get(cursor,
                        user, obj._name, context=context)
                if domain1:
                    domain1 = ' AND ' + domain1
                cursor.execute('DELETE FROM "' + self._rel + '" ' \
                        'WHERE "' + self.origin + '" = %s ' \
                            'AND "' + self.target + '" IN (' \
                            'SELECT ' + self._rel + '.' + self.target + ' ' \
                            'FROM "' + self._rel + '", "' + obj._table + '" ' \
                            'WHERE ' + self._rel + '.' + self.origin + ' = %s ' \
                                'AND ' + self._rel + '.' + self.target + ' = ' + \
                                obj._table + '.id ' + domain1 + ')',
                                [obj_id, obj_id] + domain2)

                for new_id in ids:
                    cursor.execute('INSERT INTO "' + self._rel + '" ' \
                            '("' + self.origin + '", "' + self.target + '") ' \
                            'VALUES (%s, %s)', (obj_id, new_id))
            else:
                raise Exception('Bad arguments')


class Function(Column):
    _classic_read = False
    _classic_write = False
    _properties = True

    def __init__(self, fnct, arg=None, fnct_inv='', fnct_inv_arg=None,
            type='float', fnct_search='', obj=None, **args):
        Column.__init__(self, **args)
        self._obj = obj
        self._fnct = fnct
        self._fnct_inv = fnct_inv
        self._arg = arg
        self._field = ''
        self._obj = ''
        if 'relation' in args:
            self._obj = args['relation']
        self._fnct_inv_arg = fnct_inv_arg
        if not fnct_inv:
            self.readonly = 1
        self._type = type
        self._fnct_search = fnct_search
        self._symbol_c = _TYPE2CLASS[self._type]._symbol_c
        self._symbol_f = _TYPE2CLASS[self._type]._symbol_f
        self._symbol_set = (self._symbol_c, self._symbol_f)

    def search(self, cursor, user, obj, name, args, context=None):
        if not self._fnct_search:
            return []
        return getattr(obj, self._fnct_search)(cursor, user, name, args,
                context=context)

    def get(self, cursor, obj, ids, name, user=None, offset=0, context=None,
            values=None):
        if isinstance(name, list):
            names = name
            # Test is the function works with a list of names
            if 'names' in inspect.getargspec(getattr(obj, self._fnct))[0]:
                return getattr(obj, self._fnct)(cursor, user, ids, names,
                        self._arg, context=context)
            res = {}
            for name in names:
                res[name] = getattr(obj, self._fnct)(cursor, user, ids, name,
                        self._arg, context=context)
            return res
        else:
            # Test is the function works with a list of names
            if 'names' in inspect.getargspec(getattr(obj, self._fnct))[0]:
                name = [name]
            return getattr(obj, self._fnct)(cursor, user, ids, name, self._arg,
                    context=context)

    def set(self, cursor, obj, obj_id, name, value, user=None, context=None):
        if self._fnct_inv:
            getattr(obj, self._fnct_inv)(cursor, user, obj_id, name, value,
                    self._fnct_inv_arg, context=context)


class Property(Function):

    def _fnct_write(self, obj, cursor, user, obj_id, prop, id_val, val,
            context=None):
        property_obj = obj.pool.get('ir.property')
        return property_obj.set(cursor, user, prop, obj._name, obj_id,
                (id_val and val + ',' + str(id_val)) or False, context=context)

    def _fnct_read(self, obj, cursor, user, ids, prop, arg, context=None):
        property_obj = obj.pool.get('ir.property')
        res = property_obj.get(cursor, user, prop, obj._name, ids,
                context=context)

        if self._obj:
            obj = obj.pool.get(self._obj)
            obj_names = {}
            for obj_id, obj_name in obj.name_get(cursor, user,
                    [x for x in res.values() if x], context=context):
                obj_names[obj_id] = obj_name
            for i in ids:
                if res.get(i) and res[i] in obj_names:
                    res[i] = (res[i], obj_names[res[i]])
                else:
                    res[i] = False
        return res

    def __init__(self, **args):
        super(Property, self).__init__('', None, self._fnct_write, None, **args)

    def get(self, cursor, obj, ids, name, user=None, offset=0, context=None,
            values=None):
        return self._fnct_read(obj, cursor, user, ids, name, self._arg,
                context=context)

    def set(self, cursor, obj, obj_id, name, value, user=None, context=None):
        self._fnct_write(obj, cursor, user, obj_id, name, value,
                    self._obj, context=context)

_TYPE2CLASS = {
}

for klass in (Boolean, Integer, BigInteger, Reference, Char, Sha, Text, Float,
        Numeric, Date, DateTime, Time, Binary, Selection, Many2One, One2Many,
        Many2Many):
    _TYPE2CLASS[klass._type] = klass
