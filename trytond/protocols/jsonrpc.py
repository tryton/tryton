# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
from decimal import Decimal
try:
    import simplejson as json
except ImportError:
    import json
import base64

from werkzeug.wrappers import Response
from werkzeug.utils import cached_property
from werkzeug.exceptions import BadRequest

from trytond.protocols.wrappers import Request
from trytond.exceptions import TrytonException


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
    return cast(base64.decodestring(dct['base64'].encode('utf-8')))
JSONDecoder.register('bytes', _bytes_decoder)
JSONDecoder.register('Decimal', lambda dct: Decimal(dct['decimal']))


class JSONEncoder(json.JSONEncoder):

    serializers = {}

    def __init__(self, *args, **kwargs):
        super(JSONEncoder, self).__init__(*args, **kwargs)
        # Force to use our custom decimal with simplejson
        self.use_decimal = False

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
_bytes_encoder = lambda o: {
    '__class__': 'bytes',
    'base64': base64.encodestring(o).decode('utf-8'),
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
                        self.charset, self.encoding_errors),
                    object_hook=JSONDecoder())
            except Exception:
                raise BadRequest('Unable to read JSON request')
        else:
            raise BadRequest('Not a JSON request')

    @cached_property
    def method(self):
        return self.parsed_data['method']

    @cached_property
    def params(self):
        return self.parsed_data['params']


class JSONProtocol:
    content_type = 'json'

    @classmethod
    def request(cls, environ):
        return JSONRequest(environ)

    @classmethod
    def response(cls, data, request):
        if isinstance(request, JSONRequest):
            response = {'id': request.parsed_data.get('id', 0)}
        else:
            response = {}
        if isinstance(data, TrytonException):
            response['error'] = data.args
        elif isinstance(data, Exception):
            # report exception back to server
            response['error'] = (str(data), data.__format_traceback__)
        else:
            response['result'] = data
        return Response(json.dumps(response, cls=JSONEncoder),
            content_type='application/json')
