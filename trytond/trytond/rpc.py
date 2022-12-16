#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

__all__ = ['RPC']


class RPC(object):
    '''Define RPC behavior

    readonly: The transaction mode
    instantiate: The position of the argument to be instanciated
    result: The function to transform the result
    '''

    __slots__ = ('readonly', 'instantiate', 'result')

    def __init__(self, readonly=True, instantiate=None, result=None):
        self.readonly = readonly
        self.instantiate = instantiate
        if result is None:
            result = lambda r: r
        self.result = result

    def convert(self, obj, *args, **kwargs):
        args = list(args)
        kwargs = kwargs.copy()
        if 'context' in kwargs:
            context = kwargs.pop('context')
        else:
            context = args.pop()
        timestamp = None
        if '_timestamp' in context:
            timestamp = context['_timestamp']
            del context['_timestamp']
        if self.instantiate is not None:

            def instance(data):
                if isinstance(data, (int, long)):
                    return obj(data)
                elif isinstance(data, dict):
                    return obj(**data)
                else:
                    return obj.browse(data)
            data = args[self.instantiate]
            args[self.instantiate] = instance(data)
        return args, kwargs, context, timestamp
