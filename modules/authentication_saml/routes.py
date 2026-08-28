# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import logging
import urllib.parse
from functools import wraps

try:
    from http import HTTPStatus
except ImportError:
    from http import client as HTTPStatus

import trytond.config as config
from trytond.pool import PoolMeta
from trytond.protocols.dispatcher import register_authentication_service
from trytond.protocols.wrappers import (
    Response, abort, add_auth_cookies, allow_null_origin, exceptions, redirect,
    with_pool, with_transaction)
from trytond.routing import Route, Rule
from trytond.transaction import Transaction
from trytond.url import http_host

logger = logging.getLogger(__name__)
IDENTITIES = set()
METADATA = {}
CONFIG_FILENAME = {}
LOGIN = {}

if config.has_section('authentication_saml'):
    for identity in config.options('authentication_saml'):
        IDENTITIES.add(identity)
        name = config.get('authentication_saml', identity)
        register_authentication_service(
            name, f'/r/authentication/saml/{identity}/login')
        metadata = config.get(
            f'authentication_saml {identity}', 'metadata', default=None)
        if metadata:
            with open(metadata, 'r') as file:
                METADATA[identity] = file.read()
        CONFIG_FILENAME[identity] = config.get(
            f'authentication_saml {identity}', 'config', default=None)
        LOGIN[identity] = config.get(
            f'authentication_saml {identity}', 'login', default='uid')


def log(func):
    @wraps(func)
    def wrapper(request, *args, **kwargs):
        try:
            return func(request, *args, **kwargs)
        except exceptions.HTTPException:
            logger.debug('%s', request, exc_info=True)
            raise
        except Exception as e:
            logger.error('%s', request, exc_info=True)
            abort(HTTPStatus.INTERNAL_SERVER_ERROR, e)
    return wrapper


def check_identity(func):
    @wraps(func)
    def wrapper(request, database_name, identity, *args, **kwargs):
        if identity not in IDENTITIES:
            abort(HTTPStatus.NOT_FOUND)
        return func(request, database_name, identity, *args, **kwargs)
    return wrapper


def get_url(database, identity, entrypoint):
    return http_host() + urllib.parse.quote(
        f'/{database}/r/authentication/saml/{identity}/{entrypoint}')


def get_client(database, identity):
    import saml2
    import saml2.client
    import saml2.config

    settings = {
        'entityid': get_url(database, identity, 'metadata'),
        'service': {
            'sp': {
                'endpoints': {
                    'assertion_consumer_service': [
                        (get_url(database, identity, 'acs'),
                            saml2.BINDING_HTTP_POST),
                        ]
                    },
                'allow_unsolicited': True,  # Disable built-in cache
                },
            },
        }
    if identity in METADATA:
        settings['metadata'] = {
            'inline': [METADATA[identity]],
            }
    config = saml2.config.Config()
    config.load(settings)
    if CONFIG_FILENAME.get(identity):
        config.load_file(CONFIG_FILENAME[identity])
    config.allow_unknown_attributes = True
    return saml2.client.Saml2Client(config=config)


class SAML(metaclass=PoolMeta):
    __name__ = 'authentication'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__routes__.update({
                'saml_login': Route(
                    Rule('saml/<identity>/login', methods={'GET'}),
                    decorators=[log, check_identity]),
                'saml_metadata': Route(
                    Rule('saml/<identity>/metadata', methods={'GET'}),
                    decorators=[log, check_identity]),
                'saml_acs': Route(
                    Rule('saml/<identity>/acs', methods={'POST'}),
                    decorators=[
                        allow_null_origin,
                        with_pool,
                        with_transaction(),
                        log,
                        check_identity,
                        ]),
                })

    @classmethod
    def saml_login(cls, request, database_name, identity):
        client = get_client(database_name, identity)
        redirect_url = request.args.get('next', '')
        if not (redirect_url.startswith(request.url_root)
                or redirect_url.startswith('http://localhost:')):
            redirect_url = http_host()
        reqid, info = client.prepare_for_authenticate(relay_state=redirect_url)
        headers = dict(info['headers'])
        response = redirect(headers.pop('Location'), HTTPStatus.FOUND)
        for name, value in headers.items():
            response.headers[name] = value
        response.headers['Cache-Control'] = 'no-cache, no-store'
        response.headers['Pragma'] = 'no-cache'
        return response

    @classmethod
    def saml_metadata(cls, request, database_name, identity):
        import saml2.metadata

        client = get_client(database_name, identity)
        metadata = saml2.metadata.create_metadata_string(None, client.config)
        return Response(metadata, headers={'Content-Type': 'text/xml'})

    @classmethod
    def saml_acs(cls, request, pool, identity):
        import saml2.entity

        Session = pool.get('ir.session')
        User = pool.get('res.user')
        client = get_client(pool.database_name, identity)
        authn_response = client.parse_authn_request_response(
            request.form['SAMLResponse'],
            saml2.entity.BINDING_HTTP_POST)
        if authn_response is None:
            abort(HTTPStatus.FORBIDDEN, "Unknown SAML error")
        attributes = authn_response.get_identity()
        for login in attributes[LOGIN[identity]]:
            user_id = User._get_login(login)[0]
            if user_id:
                break
        else:
            abort(HTTPStatus.FORBIDDEN, "Unknown user")
        with Transaction().set_user(user_id):
            session = Session.new()

        allow_subscribe = config.getboolean(
            'bus', 'allow_subscribe', default=False)
        bus_url_host = config.get('bus', 'url_host', default=request.host_url)
        redirect_url = request.form.get('RelayState')
        if not redirect_url:
            redirect_url = http_host()
        parts = urllib.parse.urlsplit(redirect_url)
        query = urllib.parse.parse_qsl(parts.query)
        if 'login_service' not in dict(query):
            query.append(
                ('login_service', f'/authentication/saml/{identity}/login'))
        query.append(('database', pool.database_name))
        query.append(('login', login))
        query.append(('user_id', user_id))
        tryton_client = redirect_url.startswith('http://localhost:')
        if tryton_client:
            # Add the session as a parameter
            # such that the Tryton client can retrieve it
            query.append(('session', session))
        query.append(('bus_url_host', bus_url_host if allow_subscribe else ''))
        parts = list(parts)
        parts[3] = urllib.parse.urlencode(query)
        response = redirect(urllib.parse.urlunsplit(parts))
        if not tryton_client:
            # Do not set cookies for Tryton client
            add_auth_cookies(
                response, pool.database_name, login, str(user_id), session)
        return response
