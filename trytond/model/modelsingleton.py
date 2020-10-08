# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelStorage
from trytond.transaction import Transaction


class ModelSingleton(ModelStorage):
    """
    Define a singleton model in Tryton.
    """

    @classmethod
    def __setup__(cls):
        super().__setup__()
        # Cache disable because it is used as a read by the client
        cls.__rpc__['default_get'].cache = None

    @classmethod
    def get_singleton(cls):
        '''
        Return the instance of the unique record if there is one.
        '''
        singletons = super(ModelSingleton, cls).search([], limit=1)
        if singletons:
            return singletons[0]

    @classmethod
    def create(cls, vlist):
        assert len(vlist) == 1
        singleton = cls.get_singleton()
        if not singleton:
            return super(ModelSingleton, cls).create(vlist)
        cls.write([singleton], vlist[0])
        return [singleton]

    @classmethod
    def read(cls, ids, fields_names):
        singleton = cls.get_singleton()
        if not singleton:
            fname_no_rec_name = [f for f in fields_names if '.' not in f]
            res = cls.default_get(fname_no_rec_name,
                with_rec_name=len(fname_no_rec_name) != len(fields_names))
            for field_name in fields_names:
                if field_name not in res:
                    res[field_name] = None
            res['id'] = ids[0]
            return [res]
        res = super(ModelSingleton, cls).read([singleton.id], fields_names)
        res[0]['id'] = ids[0]
        return res

    @classmethod
    def write(cls, records, values, *args):
        singleton = cls.get_singleton()
        if not singleton:
            singleton, = cls.create([values])
        actions = (records, values) + args
        args = []
        for values in actions[1:None:2]:
            args.extend(([singleton], values))
        super(ModelSingleton, cls).write(*args)
        # Clean local cache of original records
        for record in sum(actions[0:None:2], []):
            record._local_cache.pop(record.id, None)
        # Clean transaction cache of all ids
        for cache in Transaction().cache.values():
            if cls.__name__ in cache:
                cache[cls.__name__].clear()

    @classmethod
    def delete(cls, records):
        singleton = cls.get_singleton()
        if singleton:
            super(ModelSingleton, cls).delete([singleton])
        # Clean transaction cache of all ids
        for cache in Transaction().cache.values():
            if cls.__name__ in cache:
                cache[cls.__name__].clear()

    @classmethod
    def copy(cls, records, default=None):
        if default:
            cls.write(records, default)
        return records

    @classmethod
    def search(cls, domain, offset=0, limit=None, order=None, count=False):
        res = super(ModelSingleton, cls).search(domain, offset=offset,
                limit=limit, order=order, count=count)
        if not res and not domain:
            if count:
                return 1
            return [cls(1)]
        return res

    @classmethod
    def default_get(cls, fields_names, with_rec_name=True):
        if '_timestamp' in fields_names:
            fields_names = list(fields_names)
            fields_names.remove('_timestamp')
        default = super(ModelSingleton, cls).default_get(fields_names,
                with_rec_name=with_rec_name)
        singleton = cls.get_singleton()
        if singleton:
            if with_rec_name:
                fields_names = fields_names[:]
                for field in fields_names[:]:
                    if cls._fields[field]._type in ('many2one',):
                        fields_names.append(field + '.rec_name')
            default, = cls.read([singleton.id], fields_names=fields_names)
            del default['id']
        return default
