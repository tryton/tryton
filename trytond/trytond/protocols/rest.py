# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import mimetypes
from base64 import urlsafe_b64decode
from functools import partial, wraps

from trytond.config import config
from trytond.model.exceptions import AccessError
from trytond.pool import Pool
from trytond.tools import is_instance_method
from trytond.transaction import Transaction
from trytond.wsgi import app

from .jsonrpc import JSONDecoder, JSONEncoder, json
from .wrappers import (
    HTTPStatus, Response, abort, user_application, with_pool, with_transaction)

_rest = user_application('rest')
_json_decoder = JSONDecoder()
_request_timeout = config.getint('request', 'timeout', default=0)


def rest(func):
    @wraps(func)
    def wrapper(request, pool, *args, **kwargs):
        transaction = Transaction()
        context_header = request.headers.get('X-Tryton-Context')
        if context_header:
            context = json.loads(
                urlsafe_b64decode(context_header),
                object_hook=_json_decoder)
        else:
            context = {}
        languages = request.headers.get('Accept-Language')
        if languages:
            languages = languages.split(',')
            pairs = []
            for language in languages:
                try:
                    language, q = language.split(';', 1)
                except ValueError:
                    q = 1
                else:
                    q = float(q.split('=')[1])
                pairs.append((q, language.strip()))
            language = sorted(pairs, reverse=True)[0][1]
            context['language'] = language.replace('-', '_')
        with transaction.set_context(context=context):
            response = _rest(func)(request, pool, *args, **kwargs)
            response.headers['Content-Language'] = (
                transaction.language.replace('_', '-'))
            return response
    return wrapper


def get_usages(request):
    return set(map(
            str.strip,
            request.headers.get('X-Tryton-Usage', '').split(',')))


def _get_fields(Model, request):
    pool = Pool()
    ModelAccess = pool.get('ir.model.access')
    ModelFieldAccess = pool.get('ir.model.field.access')
    model_check = partial(
        ModelAccess.check, mode='read', raise_exception=False)
    field_check = partial(
        ModelFieldAccess.check, mode='read', raise_exception=False)

    def has_access(field):
        paths = field.split('.')
        model = Model
        while paths:
            field = paths.pop(0)
            if (not model_check(model.__name__)
                    or not field_check(model.__name__, [field])):
                return False
            if paths:
                model = getattr(model, field).get_target()
        return True

    if 'f' in request.args:
        fields = request.args.getlist('f')
        for path in list(fields):
            paths = path.split('.')[:-1]
            while paths:
                field = '.'.join(paths)
                fields.append(f'{field}.id')
                fields.append(f'{field}.__name__')
                paths.pop()
    else:
        fields = Model.__json__(get_usages(request))
    fields.extend({'id', '__name__'})
    return list(filter(has_access, set(_flatten_fields(fields))))


def _flatten_fields(fields):
    for field in fields:
        if isinstance(field, str):
            yield field
        else:
            parent, nested = field
            nested = ['id', '__name__'] + list(nested)
            for field in _flatten_fields(nested):
                yield f'{parent}.{field}'


def _read(Model, request, id):
    result = Model.read([id], _get_fields(Model, request))[0]
    return _remove_dots(result)


def _remove_dots(result):
    if not isinstance(result, dict):
        return [_remove_dots(v) for v in result]
    for key in list(result.keys()):
        if key.endswith('.'):
            value = result.pop(key)
            result[key[:-1]] = _remove_dots(value) if value else value
    return result


@app.route('/<database_name>/rest/model/<name>', methods={'GET'})
@with_pool
@with_transaction(timeout=_request_timeout)
@rest
def search(request, pool, name):
    Model = pool.get(name)
    if 'd' in request.args:
        domain = json.loads(
            urlsafe_b64decode(request.args['d']).decode(),
            object_hook=_json_decoder)
    else:
        domain = []
    offset, limit = 0, None
    if range_ := request.headers.get('Range'):
        if ',' in range_:
            range_ = None
        else:
            unit, range_ = range_.split('=', 1)
            start, end = range_.split('-', 1)
            if start and not end:
                offset = int(start)
            elif start and end:
                offset = int(start)
                limit = int(end) - offset
            else:
                range_ = None
    else:
        if 's' in request.args:
            limit = int(request.args['s'])
        offset = int(request.args.get('p', 0))
    if 'o' in request.args:
        order = json.loads(urlsafe_b64decode(request.args['o']).decode())
    else:
        order = None
    result = Model.search_read(
        domain, limit=limit, offset=offset, order=order,
        fields_names=_get_fields(Model, request))
    result = _remove_dots(result)
    if range_:
        if not result and offset:
            abort(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
        if limit is None:
            limit = len(result)
        if len(result) >= limit:
            count_limit = 10 * (limit + offset)
            count = Model.search(
                domain, order=[], limit=count_limit, count=True)
            if count >= count_limit:
                count = '*'
        else:
            count = offset + len(result)
        response = Response(
            json.dumps(result, cls=JSONEncoder),
            content_type='application/json')
        response.headers['Accept-Ranges'] = 'records'
        response.headers['Content-Range'] = (
            f'records {offset}-{offset + len(result)}/{count}')
        return response
    else:
        return result


@app.route('/<database_name>/rest/model/<name>/<int:id>', methods={'GET'})
@with_pool
@with_transaction(timeout=_request_timeout)
@rest
def get(request, pool, name, id):
    Model = pool.get(name)
    try:
        return _read(Model, request, id)
    except AccessError:
        abort(HTTPStatus.NOT_FOUND)


@app.route('/<database_name>/rest/model/<name>', methods={'POST'})
@with_pool
@with_transaction()
@rest
def create(request, pool, name):
    Model = pool.get(name)
    data = request.parsed_data
    record, = Model.create([data])
    try:
        return _read(Model, request, record.id)
    except AccessError:
        return Response(status=HTTPStatus.NO_CONTENT)


@app.route('/<database_name>/rest/model/<name>/<int:id>', methods={'PUT'})
@with_pool
@with_transaction()
@rest
def update(request, pool, name, id):
    Model = pool.get(name)
    data = request.parsed_data
    try:
        record, = Model.search([('id', '=', id)])
    except ValueError:
        abort(HTTPStatus.NOT_FOUND)
    Model.write([record], data)
    try:
        return _read(Model, request, record.id)
    except AccessError:
        return Response(status=HTTPStatus.NO_CONTENT)


@app.route('/<database_name>/rest/model/<name>/<int:id>', methods={'DELETE'})
@with_pool
@with_transaction()
@rest
def delete(request, pool, name, id):
    Model = pool.get(name)
    try:
        record, = Model.search([('id', '=', id)])
    except ValueError:
        abort(HTTPStatus.NOT_FOUND)
    Model.delete([record])
    return Response(status=HTTPStatus.NO_CONTENT)


@app.route(
    '/<database_name>/rest/model/<name>/<int:id>/<action>', methods={'POST'})
@app.route(
    '/<database_name>/rest/model/<name>/<action>', methods={'POST'})
@with_pool
def action(request, pool, name, action, id=None):
    Model = pool.get(name)
    data = request.parsed_data or {}
    rpc = Model.__rpc__.get(action)
    if not rpc:
        abort(HTTPStatus.FORBIDDEN)

    @with_transaction(readonly=rpc.readonly)
    @rest
    def _action(request, pool, name, action, id):
        try:
            if id is not None:
                try:
                    record, = Model.search([('id', '=', id)])
                except ValueError:
                    abort(HTTPStatus.NOT_FOUND)
                if is_instance_method(Model, action):
                    result = getattr(Model, action)(record, **data)
                else:
                    result = getattr(Model, action)([record], **data)
            else:
                result = getattr(Model, action)(**data)
        except AccessError:
            abort(HTTPStatus.FORBIDDEN)
        result = rpc.result(result)
        if id is not None and result is None:
            return _read(Model, request, id)
        elif result is not None:
            return result
        else:
            return Response(status=HTTPStatus.NO_CONTENT)
    return _action(request, pool, name, action, id)


@app.route('/<database_name>/rest/report/<name>/<int:id>', methods={'GET'})
@with_pool
@with_transaction()
@rest
def report(request, pool, name, id):
    Report = pool.get(name, type='report')
    data = request.parsed_data or {}
    ext, content, _, filename = Report.execute([id], data)
    filename = f'{filename}.{ext}'
    mimetype, _ = mimetypes.guess_type(filename)
    return Response(content,
        mimetype=mimetype,
        headers={
            'Content-Disposition': f'attachment; filename="{filename}"',
            })
