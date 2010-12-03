#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelStorage


class ModelSingleton(ModelStorage):
    """
    Define a singleton model in Tryton.
    """

    def get_singleton_id(self, cursor, user, context=None):
        '''
        Return the id of the unique record if there is one.

        :param cursor: the database cursor
        :param user: the user id
        :param context: the context
        '''
        singleton_ids = super(ModelSingleton, self).search(cursor, user, [],
                limit=1, context=context)
        if singleton_ids:
            return singleton_ids[0]
        return False

    def create(self, cursor, user, values, context=None):
        singleton_id = self.get_singleton_id(cursor, user, context=context)
        if singleton_id:
            self.write(cursor, user, singleton_id, values, context=context)
        else:
            singleton_id = super(ModelSingleton, self).create(cursor,
                    user, values, context=context)
        return singleton_id

    def read(self, cursor, user, ids, fields_names=None, context=None):
        singleton_id = self.get_singleton_id(cursor, user, context=context)
        if not singleton_id:
            res = self.default_get(cursor, user, fields_names, context=context,
                    with_rec_name=False)
            if not fields_names:
                fields_names = (set(self._columns.keys()
                    + self._inherit_fields.keys()))
            for field_name in fields_names:
                if field_name not in res:
                    res[field_name] = False
            if not isinstance(ids, (int, long)):
                res['id'] = ids[0]
                res = [res]
            else:
                res['id'] = ids
            return res
        if isinstance(ids, (int, long)):
            ids2 = singleton_id
        else:
            ids2 = [singleton_id]
        res = super(ModelSingleton, self).read(cursor, user, ids2,
                fields_names=fields_names, context=context)
        if isinstance(ids, (int, long)):
            res['id'] = ids
        else:
            res[0]['id'] = ids[0]
        return res

    def write(self, cursor, user, ids, values, context=None):
        singleton_id = self.get_singleton_id(cursor, user, context=context)
        if not singleton_id:
            return self.create(cursor, user, values, context=context)
        if isinstance(ids, (int, long)):
            ids = singleton_id
        else:
            ids = [singleton_id]
        return super(ModelSingleton, self).write(cursor, user, ids, values,
                context=context)

    def delete(self, cursor, user, ids, context=None):
        singleton_id = self.get_singleton_id(cursor, user, context=context)
        if not singleton_id:
            return True
        if isinstance(ids, (int, long)):
            ids = singleton_id
        else:
            ids = [singleton_id]
        return super(ModelSingleton, self).delete(cursor, user, ids,
                context=context)

    def copy(self, cursor, user, ids, default=None, context=None):
        if default:
            self.write(cursor, user, ids, default, context=context)
        return ids

    def search(self, cursor, user, domain, offset=0, limit=None, order=None,
            context=None, count=False):
        res = super(ModelSingleton, self).search(cursor, user, domain,
                offset=offset, limit=limit, order=order, context=context,
                count=count)
        if not res:
            if count:
                return 1
            return [1]
        return res

    def default_get(self, cursor, user, fields_names, context=None,
            with_rec_name=True):
        res = super(ModelSingleton, self).default_get(cursor, user,
                fields_names, context=context, with_rec_name=with_rec_name)
        singleton_id = self.get_singleton_id(cursor, user, context=context)
        if singleton_id:
            if with_rec_name:
                fields_names = fields_names[:]
                for field in fields_names[:]:
                    if self._columns[field]._type in ('many2one',):
                        fields_names.append(field + '.rec_name')
            res = self.read(cursor, user, singleton_id,
                    fields_names=fields_names, context=context)
            for field in (x for x in res.keys() if x not in fields_names):
                del res[field]
        return res
