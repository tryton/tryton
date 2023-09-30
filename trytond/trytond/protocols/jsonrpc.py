# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import base64
import datetime
import json
from decimal import Decimal

from werkzeug.exceptions import (
    BadRequest, Conflict, Forbidden, InternalServerError, Locked,
    TooManyRequests)
from werkzeug.wrappers import Response

from trytond.exceptions import (
    ConcurrencyException, LoginException, MissingDependenciesException,
    RateLimitException, TrytonException, UserWarning)
from trytond.protocols.wrappers import Request
from trytond.tools import cached_property


class JSONDecoder(object):

    decoders = {}

    @classmethod
    def register(cls, klass, decoder):
        assert klass not in cls.decoders
        cls.decoders[klass] = decoder

    def __call__(self, dct):
        if dct.get('__class__') in self.decoders:
            return self.decoders[dct['__class__']](dct)
        return dct


JSONDecoder.register('datetime',
    lambda dct: datetime.datetime(dct['year'], dct['month'], dct['day'],
        dct['hour'], dct['minute'], dct['second'], dct['microsecond']))
JSONDecoder.register('date',
    lambda dct: datetime.date(dct['year'], dct['month'], dct['day']))
JSONDecoder.register('time',
    lambda dct: datetime.time(dct['hour'], dct['minute'], dct['second'],
        dct['microsecond']))
JSONDecoder.register('timedelta',
    lambda dct: datetime.timedelta(seconds=dct['seconds']))


def _bytes_decoder(dct):
    cast = bytearray if bytes == str else bytes
    return cast(base64.decodebytes(dct['base64'].encode('utf-8')))


JSONDecoder.register('bytes', _bytes_decoder)
JSONDecoder.register('Decimal', lambda dct: Decimal(dct['decimal']))


class JSONEncoder(json.JSONEncoder):

    serializers = {}

    @classmethod
    def register(cls, klass, encoder):
        assert klass not in cls.serializers
        cls.serializers[klass] = encoder

    def default(self, obj):
        marshaller = self.serializers.get(type(obj),
            super(JSONEncoder, self).default)
        return marshaller(obj)


JSONEncoder.register(datetime.datetime,
    lambda o: {
        '__class__': 'datetime',
        'year': o.year,
        'month': o.month,
        'day': o.day,
        'hour': o.hour,
        'minute': o.minute,
        'second': o.second,
        'microsecond': o.microsecond,
        })
JSONEncoder.register(datetime.date,
    lambda o: {
        '__class__': 'date',
        'year': o.year,
        'month': o.month,
        'day': o.day,
        })
JSONEncoder.register(datetime.time,
    lambda o: {
        '__class__': 'time',
        'hour': o.hour,
        'minute': o.minute,
        'second': o.second,
        'microsecond': o.microsecond,
        })
JSONEncoder.register(datetime.timedelta,
    lambda o: {
        '__class__': 'timedelta',
        'seconds': o.total_seconds(),
        })


def _bytes_encoder(o):
    return {
        '__class__': 'bytes',
        'base64': base64.encodebytes(o).decode('utf-8'),
        }


JSONEncoder.register(bytes, _bytes_encoder)
JSONEncoder.register(bytearray, _bytes_encoder)
JSONEncoder.register(Decimal,
    lambda o: {
        '__class__': 'Decimal',
        'decimal': str(o),
        })


class JSONRequest(Request):
    parsed_content_type = 'json'

    @cached_property
    def parsed_data(self):
        if self.parsed_content_type in self.environ.get('CONTENT_TYPE', ''):
            try:
                return json.loads(
                    self.decoded_data.decode(
                        getattr(self, 'charset', 'utf-8'),
                        getattr(self, 'encoding_errors', 'replace')),
                    object_hook=JSONDecoder())
            except Exception:
                raise BadRequest('Unable to read JSON request')
        else:
            raise BadRequest('Not a JSON request')

    @cached_property
    def rpc_method(self):
        try:
            return self.parsed_data['method']
        except Exception:
            pass

    @cached_property
    def rpc_params(self):
        try:
            return self.parsed_data['params']
        except Exception:
            pass


class JSONProtocol:
    content_type = 'json'

    @classmethod
    def request(cls, environ):
        return JSONRequest(environ)

    @classmethod
    def response(cls, data, request):
        try:
            parsed_data = request.parsed_data
        except BadRequest:
            parsed_data = {}
        if (isinstance(request, JSONRequest)
                and set(parsed_data.keys()) == {'id', 'method', 'params'}):
            response = {'id': parsed_data.get('id', 0)}
            if isinstance(data, TrytonException):
                response['error'] = data.args
            elif isinstance(data, Exception):
                # report exception back to server
                response['error'] = (str(data), data.__format_traceback__)
            else:
                response['result'] = data
        else:
            if isinstance(data, UserWarning):
                return Conflict(data)
            elif isinstance(data, LoginException):
                return Forbidden(data)
            elif isinstance(data, ConcurrencyException):
                return Locked(data)
            elif isinstance(data, RateLimitException):
                return TooManyRequests(data)
            elif isinstance(data, MissingDependenciesException):
                return InternalServerError(data)
            elif isinstance(data, TrytonException):
                return BadRequest(data)
            elif isinstance(data, Exception):
                return InternalServerError(data)
            response = data
        return Response(json.dumps(
                response, cls=JSONEncoder, separators=(',', ':')),
            content_type='application/json')
