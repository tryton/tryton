# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import copy
import datetime as dt
from collections.abc import Sized

from trytond.exceptions import TrytonException
from trytond.protocols.wrappers import HTTPStatus, abort
from trytond.transaction import Transaction


class RPC(object):
    '''Define RPC behavior

    readonly: The transaction mode
    instantiate: The position or the slice of the arguments to be instanciated
    decorator: A function to decorate the procedure with
    result: The function to transform the result
    check_access: If access right must be checked
    fresh_session: If a fresh session is required
    unique: Check instances are unique
    timeout: The timeout in second
    size_limits: A dictionary with size limits
    '''

    __slots__ = (
        'readonly', 'instantiate', 'decorator', 'result',
        'check_access', 'fresh_session', 'unique', 'cache', 'timeout',
        'size_limits')

    def __init__(
            self, readonly=True, instantiate=None, decorator=None, result=None,
            check_access=True, fresh_session=False, unique=True, cache=None,
            timeout=None, size_limits=None):
        self.readonly = readonly
        self.instantiate = instantiate
        self.decorator = decorator
        if result is None:
            def result(r):
                return r
        self.result = result
        self.check_access = check_access
        self.fresh_session = fresh_session
        self.unique = unique
        if cache:
            if not isinstance(cache, RPCCache):
                cache = RPCCache(**cache)
        self.cache = cache
        self.timeout = timeout
        self.size_limits = size_limits

    def convert(self, obj, *args, **kwargs):
        args = list(args)
        kwargs = kwargs.copy()
        if 'context' in kwargs:
            context = kwargs.pop('context')
            if not isinstance(context, dict):
                abort(
                    HTTPStatus.UNPROCESSABLE_ENTITY,
                    "context must be a dictionary")
        else:
            try:
                context = args.pop()
            except IndexError:
                context = None
            if not isinstance(context, dict):
                abort(
                    HTTPStatus.UNPROCESSABLE_ENTITY,
                    "Missing context argument")
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
                            abort(
                                HTTPStatus.UNPROCESSABLE_ENTITY,
                                "Duplicate records")
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
        self._check_size_limits(args, kwargs)
        return args, kwargs, context, timestamp

    def _check_size_limits(self, args, kwargs):
        if not self.size_limits:
            return
        for arg_spec, limit in self.size_limits.items():
            if not limit:
                continue
            if isinstance(arg_spec, int):
                try:
                    selection = [args[arg_spec]]
                except IndexError:
                    continue
            else:
                selection = args[slice(*arg_spec)]
            test = 0
            for arg in selection:
                if isinstance(arg, Sized):
                    test += len(arg)
                else:
                    try:
                        test += arg
                    except TypeError:
                        pass
            if test > limit:
                abort(HTTPStatus.REQUEST_ENTITY_TOO_LARGE)

    def decorate(self, func):
        if self.decorator:
            func = self.decorator(func)
        return func


class RPCCache:
    __slots__ = ('duration',)

    def __init__(self, days=0, seconds=0):
        self.duration = dt.timedelta(days=days, seconds=seconds)

    def headers(self):
        return {
            'X-Tryton-Cache': int(self.duration.total_seconds()),
            }


class RPCReturnException(TrytonException):
    "Exception to return response instead of being raised"

    def result(self):
        pass
