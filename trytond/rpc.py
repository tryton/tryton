# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import copy

from trytond.transaction import Transaction

__all__ = ['RPC']


class RPC(object):
    '''Define RPC behavior

    readonly: The transaction mode
    instantiate: The position or the slice of the arguments to be instanciated
    result: The function to transform the result
    check_access: If access right must be checked
    fresh_session: If a fresh session is required
    unique: Check instances are unique
    '''

    __slots__ = ('readonly', 'instantiate', 'result', 'check_access',
        'fresh_session', 'unique')

    def __init__(self, readonly=True, instantiate=None, result=None,
            check_access=True, fresh_session=False, unique=True):
        self.readonly = readonly
        self.instantiate = instantiate
        if result is None:
            result = lambda r: r
        self.result = result
        self.check_access = check_access
        self.fresh_session = fresh_session
        self.unique = unique

    def convert(self, obj, *args, **kwargs):
        args = list(args)
        kwargs = kwargs.copy()
        if 'context' in kwargs:
            context = kwargs.pop('context')
        else:
            context = args.pop()
        context = copy.deepcopy(context)
        timestamp = None
        for key in list(context.keys()):
            if key == '_timestamp':
                timestamp = context[key]
            # Remove all private keyword but _datetime for history
            if key.startswith('_') and key != '_datetime':
                del context[key]
        if self.instantiate is not None:

            def instance(data):
                with Transaction().set_context(context):
                    if isinstance(data, int):
                        return obj(data)
                    elif isinstance(data, dict):
                        return obj(**data)
                    else:
                        if self.unique and len(data) != len(set(data)):
                            raise ValueError("Duplicate ids")
                        return obj.browse(data)
            if isinstance(self.instantiate, slice):
                for i, data in enumerate(args[self.instantiate]):
                    start, _, step = self.instantiate.indices(len(args))
                    i = i * step + start
                    args[i] = instance(data)
            else:
                data = args[self.instantiate]
                args[self.instantiate] = instance(data)
        if self.check_access:
            context['_check_access'] = True
        return args, kwargs, context, timestamp
