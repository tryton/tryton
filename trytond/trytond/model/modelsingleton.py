#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelStorage


class ModelSingleton(ModelStorage):
    """
    Define a singleton model in Tryton.
    """

    def get_singleton_id(self):
        '''
        Return the id of the unique record if there is one.
        '''
        singleton_ids = super(ModelSingleton, self).search([], limit=1)
        if singleton_ids:
            return singleton_ids[0]
        return False

    def create(self, values):
        singleton_id = self.get_singleton_id()
        if singleton_id:
            self.write(singleton_id, values)
        else:
            singleton_id = super(ModelSingleton, self).create(values)
        return singleton_id

    def read(self, ids, fields_names=None):
        singleton_id = self.get_singleton_id()
        if not singleton_id:
            res = self.default_get(fields_names, with_rec_name=False)
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
        res = super(ModelSingleton, self).read(ids2, fields_names=fields_names)
        if isinstance(ids, (int, long)):
            res['id'] = ids
        else:
            res[0]['id'] = ids[0]
        return res

    def write(self, ids, values):
        singleton_id = self.get_singleton_id()
        if not singleton_id:
            return self.create(values)
        if isinstance(ids, (int, long)):
            ids = singleton_id
        else:
            ids = [singleton_id]
        return super(ModelSingleton, self).write(ids, values)

    def delete(self, ids):
        singleton_id = self.get_singleton_id()
        if not singleton_id:
            return True
        if isinstance(ids, (int, long)):
            ids = singleton_id
        else:
            ids = [singleton_id]
        return super(ModelSingleton, self).delete(ids)

    def copy(self, ids, default=None):
        if default:
            self.write(ids, default)
        return ids

    def search(self, domain, offset=0, limit=None, order=None, count=False):
        res = super(ModelSingleton, self).search(domain, offset=offset,
                limit=limit, order=order, count=count)
        if not res:
            if count:
                return 1
            return [1]
        return res

    def default_get(self, fields_names, with_rec_name=True):
        if '_timestamp' in fields_names:
            fields_names = list(fields_names)
            fields_names.remove('_timestamp')
        res = super(ModelSingleton, self).default_get(fields_names,
                with_rec_name=with_rec_name)
        singleton_id = self.get_singleton_id()
        if singleton_id:
            if with_rec_name:
                fields_names = fields_names[:]
                for field in fields_names[:]:
                    if self._columns[field]._type in ('many2one',):
                        fields_names.append(field + '.rec_name')
            res = self.read(singleton_id, fields_names=fields_names)
            for field in (x for x in res.keys() if x not in fields_names):
                del res[field]
        return res
