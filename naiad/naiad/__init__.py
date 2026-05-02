# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
"""
A library to access Tryton's REST API
"""
import json
import threading
import time
from base64 import urlsafe_b64encode
from contextlib import contextmanager
from email.message import Message
from functools import partial, total_ordering

import httpx

from ._json import JSONDecoder, JSONEncoder

__version__ = "8.0.2"
__all__ = ['Client', 'Record', 'set_delete', 'set_remove']
_json_decoder = JSONDecoder()

_dumps = partial(json.dumps, cls=JSONEncoder, separators=(',', ':'))


class Client:
    """A client for REST API of Tryton based on httpx.Client.

    Parameters:
        - base_url: The URL to use to connect to the Tryton server including
          the database.
        - key: The Tryton application key used for user authentication.
        - usages: An optional iterable containing the usage strings.
        - context: An optional dictionary for setting the context.
        - languages: An optional iterable containing language code strings or
          combination of language code and quality.
        - timeout: An optional httpx.Timeout configuration.
        - limits: An optional httpx.Limits configuration.
        - max_retries: The maximum number of retries.
    """
    def __init__(
            self, base_url, key, usages=None, context=None, languages=None,
            timeout=httpx.Timeout(timeout=5),
            limits=httpx.Limits(
                max_connections=100, max_keepalive_connections=20),
            max_retries=5):
        self.base_url = base_url
        self.max_retries = max_retries
        headers = {
            'User-Agent': f'naiad/{__version__}',
            }
        if context:
            headers['X-Tryton-Context'] = (
                urlsafe_b64encode(_dumps(context).encode()).decode())
        if languages:
            headers['Accept-Language'] = _format_accept_language(languages)
        if usages:
            headers['X-Tryton-Usage'] = ','.join(usages)
        self.client = httpx.Client(
            base_url=self.base_url + '/rest',
            auth=Auth(key),
            headers=headers,
            timeout=timeout,
            limits=limits)

    def _request(self, method, endpoint, **kwargs):
        retries = 0
        exception = None
        while retries <= self.max_retries:
            try:
                response = self.client.request(method, endpoint, **kwargs)
                response.raise_for_status()
                if response.headers['Content-Type'] == 'application/json':
                    content = response.json(object_hook=_json_decoder)
                else:
                    content = response.content
                return response, content
            except httpx.ConnectError as e:
                retries += 1
                wait_time = 2 ** (retries - 1)
                time.sleep(wait_time)
                exception = e
        raise exception

    def search(
            self, model, domain=None, order=None, range_=None,
            limit=None, offset=0, fields=None):
        """Make a search and returns a list of Record instances.

        Parameters:
            - model: The name of the model to search on.
            - domain: An optional Tryton domain.
            - order: An optional Tryton order clause.
            - range_: An optional pair consisting of the start and end
              positions of the records to retrieve.
            - limit: An optional size limit for the number of records to
              retrieve.
            - offset: An optional offset to start retrieving records.
            - fields: An optional list of fields to read.

        Note: If range_ is set, limit and offset are ignored and the result is
        a couple containing start, end and size and the records.
        """
        assert range_ is None or (limit is None and offset == 0)
        params = {}
        if domain is not None:
            params['d'] = urlsafe_b64encode(_dumps(domain).encode()).decode()
        if order is not None:
            params['o'] = urlsafe_b64encode(_dumps(order).encode()).decode()
        headers = {}
        if range_ is not None:
            start, end = range_
            headers['Range'] = f'records={start}-{end}'
        else:
            if offset != 0:
                params['p'] = offset
            if limit is not None:
                params['s'] = limit
        if fields:
            params['f'] = fields
        response, content = self._request(
            'GET', f'/model/{model}', params=params, headers=headers)
        records = [Record(**d) for d in content]
        if range_:
            start = end = size = None
            if range_ := response.headers.get('Content-Range'):
                unit, range_ = range_.split(' ', 1)
                if unit == 'records' and '/' in range_:
                    range_, size = range_.split('/', 1)
                    try:
                        start, end = map(int, range_.split('-'))
                    except ValueError:
                        pass
                    try:
                        size = int(size)
                    except ValueError:
                        pass
            return (start, end, size), records
        return records

    def get(self, model, id, fields=None):
        """Fetch and return a record.

        Parameters:
            - model: The name of the model.
            - id: The ID of the record to fetch.
            - fields: An optional list of fields to retrieve instead of the
              defaults.
        """
        params = {}
        if fields is not None:
            params['f'] = fields
        _, content = self._request(
            'GET', f'/model/{model}/{id}', params=params)
        return Record(**content)

    def create(self, model, values, fields=None):
        """Create and return the new record.

        Parameters:
            - model: The name of the model.
            - values: A dictionary containing the values of the fields.
            - fields: An optional list of fields to retrieve instead of the
              defaults.
        """
        params = {}
        if fields is not None:
            params['f'] = fields
        content = _dumps(values)
        response, content = self._request(
            'POST', f'/model/{model}',
            headers={
                'Content-Type': 'application/json',
                },
            params=params,
            content=content)
        return Record(**content)

    def update(self, model, id, values, fields=None):
        """Update and return the updated record.

        Parameters:
            - model: The name of the model.
            - id: The ID of the record to update.
            - values: A dictionary containing the values of the fields.
            - fields: An optional list of fields to retrieve instead of the
              defaults.
        """
        params = {}
        if fields is not None:
            params['f'] = fields
        content = _dumps(values)
        response, content = self._request(
            'PUT', f'/model/{model}/{id}',
            headers={
                'Content-Type': 'application/json',
                },
            params=params,
            content=content)
        return Record(**content)

    def delete(self, model, id=None):
        """Delete a record.

        Parameters:
            - model: The name of the model or the Record instance to be
              deleted.
            - id: The ID of the record to delete.

        Note: If a Record instance is specified, the ID must not be specified.
        """
        if id is None:
            record = model
            model = record._model
            id = record.id
        self._request('DELETE', f'/model/{model}/{id}')

    def store(self, record, fields=None):
        """Store a record and return the new/updated record.

        It the record instance has no id, a new one is created otherwise it is
        updated.

        Parameters:
            - record: The Record instance to store.
            - fields: An optional list of fields to retrieve instead of the
              defaults.
        """
        if record.id is None:
            return self.create(
                record._model, record.to_values(), fields=fields)
        else:
            return self.update(
                record._model, record.id, record.to_values(), fields=fields)

    def action(self, model, name, id=None, fields=None, kwargs=None):
        """Launch an action and return the result

        Parameters:
            - model: The name of the model.
            - name: The name of the action on the model.
            - id: An optional ID for the record on which to perform the action.
            - fields: An optional list of fields to retrieve instead of the
              defaults if the action returns a Record.
            - kwargs: An optional dictionary of additional arguments to pass to
              the action.
        """
        if isinstance(model, Record):
            record = model
            model = record._model
            if id is None:
                id = record.id
        params = {}
        if fields is not None:
            params['f'] = fields
        content = _dumps(kwargs if kwargs is not None else {})
        if id is None:
            url = f'/model/{model}/{name}'
        else:
            url = f'/model/{model}/{id}/{name}'
        response, content = self._request(
            'POST', url,
            headers={
                'Content-Type': 'application/json',
                },
            params=params,
            content=content)
        if (id is not None
                and isinstance(content, dict)
                and content.get('__name__') == model):
            return Record(**content)
        return content

    def report(self, name, id=None, data=None):
        """Render a report and return the couple of file name and content.

        Parameters:
            - name: The name of the report.
            - id: An option ID for the record on which to render the report.
            - data: An optional dictionary containing additional data to be
              passed to the report.
        """
        id = int(id)
        content = _dumps(data or {})
        response, content = self._request(
            'GET', f'/report/{name}/{id}',
            headers={
                'Content-Type': 'application/json',
                },
            content=content)
        if content_disposition := response.headers['Content-Disposition']:
            msg = Message()
            msg['content-disposition'] = content_disposition
            filename = msg.get_filename()
        else:
            filename = 'data.bin'
        return filename, content


class Auth(httpx.Auth):
    def __init__(self, token):
        self.token = token

    def auth_flow(self, request):
        request.headers['Authorization'] = f'bearer {self.token}'
        yield request


class _ThreadLocal:
    def __init__(self):
        self._local = threading.local()

    @property
    def deleted(self):
        if not hasattr(self._local, 'deleted'):
            self._local.deleted = set()
        return self._local.deleted

    @property
    def removed(self):
        if not hasattr(self._local, 'removed'):
            self._local.removed = set()
        return self._local.removed


_thread_local = _ThreadLocal()


@contextmanager
def set_delete(model, field):
    """Return context manager to delete the missing records from relational
    fields when storing a record.

    Parameters:
        - model: the name of the model.
        - field: the name of the field.
    """
    _thread_local.deleted.add((model, field))
    _thread_local.removed.discard((model, field))
    try:
        yield
    finally:
        _thread_local.deleted.discard((model, field))


@contextmanager
def set_remove(model, field):
    """Return context manager to remove the missing records from relational
    fields when storing a record.

    Parameters:
        - model: the name of the model.
        - field: the name of the field.
    """
    _thread_local.deleted.discard((model, field))
    _thread_local.removed.add((model, field))
    try:
        yield
    finally:
        _thread_local.removed.discard((model, field))


@total_ordering
class Record:
    """A container that stores data from a Tryton record.

    Parameters:
        - __name__: The name of the model.
        - id: An option ID of the record.
    """
    __slots__ = ('_model', 'id', '_raw', '_stored', '_modified')

    def __init__(self, __name__=None, **kwargs):
        self._model = __name__ or kwargs.pop('__name__')
        self.id = kwargs.pop('id', None)
        self._stored = {}
        self._modified = {}
        if self.id is None:
            self._raw = {}
            for name, value in kwargs.items():
                setattr(self, name, value)
        else:
            self._raw = kwargs or {}

    def __repr__(self):
        return (
            f'{self.__class__.__qualname__}'
            f'({self._model!r}, id={self.id!r})')

    def __contains__(self, name):
        return name in dir(self)

    def __int__(self):
        return self.id

    def __str__(self):
        try:
            return self.rec_name
        except AttributeError:
            return str(self.id) if self.id is not None else ''

    def __eq__(self, other):
        if isinstance(other, int):
            return self.id == other
        elif isinstance(other, Record):
            return (self._model, self.id) == (other._model, other.id)
        return NotImplemented

    def __lt__(self, other):
        if not isinstance(other, Record) or self._model != other._model:
            return NotImplemented
        return self.id < other.id

    def __ne__(self, other):
        return not self == other

    def __hash__(self):
        return hash((self._model, self.id))

    def __bool__(self):
        return True

    @classmethod
    def _convert(cls, value):
        if isinstance(value, dict) and value.get('__name__'):
            value = cls(**value)
        elif (isinstance(value, list)
                and value
                and isinstance(value[0], dict)
                and value[0].get('__name__')):
            value = tuple(cls(**v) for v in value)
        return value

    def __getattr__(self, name):
        if name.startswith('__') and name.endswith('__'):
            return super().__getattr__(name)
        elif name in self._modified:
            value = self._modified[name]
        elif name in self._stored:
            value = self._stored[name]
        else:
            try:
                value = self._convert(self._raw.pop(name))
                self._stored[name] = value
            except KeyError:
                raise AttributeError(name) from None
        return value

    def __setattr__(self, name, value):
        if name in self.__slots__:
            super().__setattr__(name, value)
        elif value != getattr(self, name, None):
            self._modified[name] = self._convert(value)

    def __dir__(self):
        return list(
            self._modified.keys() | self._stored.keys() | self._raw.keys())

    def to_dict(self):
        "Return the record as dictionary"
        result = {
            '__name__': self._model,
            'id': self.id,
            }
        for name in dir(self):
            value = getattr(self, name)
            if (isinstance(value, (list, tuple))
                    and value and isinstance(value[0], Record)):
                value = [v.to_dict() for v in value]
            elif isinstance(value, Record):
                value = value.to_dict()
            result[name] = value
        return result

    def to_values(self):
        """Return a dictionary of the modified data to be used for create or
        update."""
        result = {}
        for name in dir(self):
            value = getattr(self, name)
            stored_value = self._stored.get(name)
            if (
                    (isinstance(value, (list, tuple))
                        and value and isinstance(value[0], Record))
                    or (isinstance(stored_value, (list, tuple))
                        and stored_value
                        and isinstance(stored_value[0], Record))):
                actions = []
                to_create, to_add, to_write = [], [], []
                for record in value:
                    if record.id is None:
                        to_create.append(record.to_values())
                    else:
                        if record not in (stored_value or []):
                            to_add.append(record.id)
                        if save_value := record.to_values():
                            to_write.append(('write', [record.id], save_value))
                if stored_value:
                    to_delete, to_remove = [], []
                    for record in stored_value:
                        if record in value:
                            continue
                        if (self._model, name) in _thread_local.deleted:
                            to_delete.append(record.id)
                        elif (self._model, name) in _thread_local.removed:
                            to_remove.append(record.id)
                        else:
                            raise ValueError(
                                f'missing deleted or removed for {name}')
                    if to_delete:
                        actions.append(('delete', to_delete))
                    if to_remove:
                        actions.append(('remove', to_remove))
                if to_add:
                    actions.append(('add', to_add))
                if to_create:
                    actions.append(('create', to_create))
                if to_write:
                    actions.extend(to_write)
                value = actions
                if not value:
                    continue
            elif value != stored_value:
                if isinstance(value, Record):
                    value = value.id
            else:
                continue
            result[name] = value
        return result


def _format_accept_language(languages):
    result = []
    for value in languages:
        if isinstance(value, str):
            language, quality = value, 1
        else:
            try:
                language, quality = value
            except ValueError:
                quality = 1
        if quality != 1:
            value = f'{language};q={quality}'
        result.append(value)
    return ','.join(result)
