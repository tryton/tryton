# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import base64
import gzip
from io import BytesIO

from werkzeug.wrappers import Request as _Request
from werkzeug.utils import cached_property
from werkzeug.http import wsgi_to_bytes, bytes_to_wsgi
from werkzeug.datastructures import Authorization
from werkzeug.exceptions import abort

from trytond import security


class Request(_Request):

    view_args = None

    @property
    def decoded_data(self):
        if self.content_encoding == 'gzip':
            zipfile = gzip.GzipFile(fileobj=BytesIO(self.data), mode='rb')
            return zipfile.read()
        else:
            return self.data

    @property
    def parsed_data(self):
        return self.data

    @property
    def method(self):
        return

    @property
    def params(self):
        return

    @cached_property
    def authorization(self):
        authorization = super(Request, self).authorization
        if authorization is None:
            header = self.environ.get('HTTP_AUTHORIZATION')
            return parse_authorization_header(header)
        return authorization

    @cached_property
    def user_id(self):
        database_name = self.view_args['database_name']
        auth = self.authorization
        if not auth:
            abort(401)
        if auth.type == 'session':
            user_id = security.check(
                database_name, auth.get('userid'), auth.get('session'))
            if not user_id:
                abort(403)
        else:
            user_id = security.login(
                database_name, auth.username, auth.password, cache=False)
            if not user_id:
                abort(401)
        return user_id


def parse_authorization_header(value):
    if not value:
        return
    value = wsgi_to_bytes(value)
    try:
        auth_type, auth_info = value.split(None, 1)
        auth_type = auth_type.lower()
    except ValueError:
        return
    if auth_type == b'session':
        try:
            username, userid, session = base64.b64decode(auth_info).split(
                b':', 3)
            userid = int(userid)
        except Exception:
            return
        return Authorization('session', {
                'username': bytes_to_wsgi(username),
                'userid': userid,
                'session': bytes_to_wsgi(session),
                })
