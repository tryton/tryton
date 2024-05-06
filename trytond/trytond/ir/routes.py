# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import csv
import datetime as dt
import io
import json
from numbers import Number

from trytond.config import config
from trytond.i18n import gettext
from trytond.protocols.jsonrpc import JSONDecoder
from trytond.protocols.wrappers import (
    HTTPStatus, Response, abort, redirect, with_pool, with_transaction)
from trytond.tools import slugify
from trytond.transaction import Transaction
from trytond.wsgi import app

SOURCE = config.get(
    'html', 'src', default='https://cloud.tinymce.com/stable/tinymce.min.js')
AVATAR_TIMEOUT = config.getint(
    'web', 'avatar_timeout', default=7 * 24 * 60 * 60)


def get_token(record):
    return str((record.write_date or record.create_date).timestamp())


def get_config(names, section='html', default=None):
    names = names[:]
    while names:
        value = config.get(section, '-'.join(names))
        if value is not None:
            return value
        names = names[:-1]
    return default


@app.route('/<database_name>/ir/html/<model>/<int:record>/<field>',
    methods={'GET', 'POST'})
@app.auth_required
@with_pool
@with_transaction(
    user='request', context=dict(_check_access=True, fuzzy_translation=True))
def html_editor(request, pool, model, record, field):
    Field = pool.get('ir.model.field')
    field, = Field.search([
            ('name', '=', field),
            ('model.model', '=', model),
            ])

    transaction = Transaction()
    language = request.args.get('language', transaction.language)
    with transaction.set_context(language=language):
        Model = pool.get(model)
        record = Model(record)

        status = HTTPStatus.OK
        error = ''
        if request.method == 'POST':
            setattr(record, field.name, request.form['text'])
            if request.form['_csrf_token'] == get_token(record):
                record.save()
                return redirect(request.url)
            else:
                status = HTTPStatus.BAD_REQUEST
                error = gettext('ir.msg_html_editor_save_fail')

        csrf_token = get_token(record)
        text = getattr(record, field.name) or ''
        if isinstance(text, bytes):
            try:
                text = text.decode('utf-8')
            except UnicodeDecodeError as e:
                error = str(e).replace("'", "\\'")
                text = ''
        elif not isinstance(text, str):
            abort(HTTPStatus.BAD_REQUEST)
        title = '%(model)s "%(name)s" %(field)s - %(title)s' % {
            'model': field.model_ref.name,
            'name': record.rec_name,
            'field': field.field_description,
            'title': request.args.get('title', "Tryton"),
            }

        return Response(TEMPLATE % {
                'source': SOURCE,
                'plugins': get_config(
                    ['plugins', model, field.name], default=''),
                'css': get_config(
                    ['css', model, field.name], default='[]'),
                'class': get_config(
                    ['class', model, field.name], default="''"),
                'language': transaction.language,
                'title': title,
                'text': text,
                'csrf_token': csrf_token,
                'error': error,
                }, status, content_type='text/html')


TEMPLATE = '''<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8"/>
    <script src="%(source)s"></script>
    <script>
    tinymce.init({
        selector: '#text',
        language: '%(language)s',
        plugins: 'fullscreen autosave code %(plugins)s',
        removed_menuitems: 'newdocument',
        toolbar: 'save | undo redo | styleselect | bold italic | ' +
            'alignleft aligncenter alignright alignjustify | ' +
            'bullist numlist outdent indent | link image | close',
        extended_valid_elements:
            'py:if[test],' +
            'py:choose[test],py:when[test],py:otherwise,' +
            'py:for[each],' +
            'py:def[function],' +
            'py:match[path],' +
            'py:with[vars],' +
            'py:replace[value]',
        custom_elements:
            'py:if,' +
            'py:choose,py:when,py:otherwise,' +
            'py:for,' +
            'py:def,' +
            'py:match,' +
            'py:with,' +
            'py:replace',
        content_css: %(css)s,
        body_class: %(class)s,
        setup: function(editor) {
            editor.addMenuItem('save', {
                text: 'Save',
                icon: 'save',
                context: 'file',
                cmd: 'save',
            });
            editor.addButton('save', {
                title: 'Save',
                icon: 'save',
                cmd: 'save',
            });
            editor.addShortcut('ctrl+s', 'save', 'save');
            editor.addCommand('save', function() {
                document.form.submit();
            });
            editor.addButton('close', {
                title: 'Close',
                icon: 'remove',
                onclick: function() {
                    window.location =
                        window.location.protocol + '//_@' +
                        window.location.host +
                        window.location.pathname;
                    window.close();
                },
            });
        },
        init_instance_callback: function(editor) {
            editor.execCommand('mceFullScreen');
            var error = '%(error)s';
            if (error) {
                editor.notificationManager.open({
                    text: error,
                    type: 'error',
                });
            }
        },
    });
    </script>
    <title>%(title)s</title>
</head>
<body>
    <form name="form" method="post" style="display: block; text-align: center">
        <textarea id="text" name="text">%(text)s</textarea>
        <input name="_csrf_token" type="hidden" value="%(csrf_token)s">
    </form>
</body>
</html>'''


@app.route('/<database_name>/data/<model>', methods={'GET'})
@app.auth_required
@with_pool
@with_transaction(user='request', context=dict(_check_access=True))
def data(request, pool, model):
    User = pool.get('res.user')
    Lang = pool.get('ir.lang')
    try:
        Model = pool.get(model)
    except KeyError:
        abort(HTTPStatus.NOT_FOUND)
    transaction = Transaction()
    context = User(transaction.user).get_preferences(context_only=True)
    language = request.args.get('l')
    if language:
        context['language'] = language
    try:
        domain = json.loads(
            request.args.get('d', '[]'), object_hook=JSONDecoder())
    except json.JSONDecodeError:
        abort(HTTPStatus.BAD_REQUEST)
    try:
        ctx = json.loads(
            request.args.get('c', '{}'), object_hook=JSONDecoder())
    except json.JSONDecoder:
        abort(HTTPStatus.BAD_REQUEST)
    for key in list(ctx.keys()):
        if key.startswith('_') and key != '_datetime':
            del ctx[key]
    context.update(ctx)
    limit = None
    offset = 0
    if 's' in request.args:
        try:
            limit = int(request.args.get('s'))
            if 'p' in request.args:
                offset = int(request.args.get('p')) * limit
        except ValueError:
            abort(HTTPStatus.BAD_REQUEST)
    if 'o' in request.args:
        order = [(o.split(',', 1) + [''])[:2]
            for o in request.args.getlist('o')]
    else:
        order = None
    fields_names = request.args.getlist('f')
    encoding = request.args.get('enc', 'UTF-8')
    delimiter = request.args.get('dl', ',')
    quotechar = request.args.get('qc', '"')
    try:
        header = bool(int(request.args.get('h', True)))
        locale_format = bool(int(request.args.get('loc', False)))
    except ValueError:
        abort(HTTPStatus.BAD_REQUEST)

    with transaction.set_context(**context):
        lang = Lang.get(transaction.language)

        def format_(row):
            for i, value in enumerate(row):
                if locale_format:
                    if isinstance(value, Number):
                        value = lang.format('%.12g', value)
                    elif isinstance(value, (dt.date, dt.datetime)):
                        value = lang.strftime(value)
                elif isinstance(value, bool):
                    value = int(value)
                row[i] = value
            return row

        try:
            if domain and isinstance(domain[0], (int, float)):
                rows = Model.export_data(
                    Model.browse(domain), fields_names, header)
            else:
                rows = Model.export_data_domain(
                    domain, fields_names,
                    limit=limit, offset=offset, order=order, header=header)
        except (ValueError, KeyError):
            abort(HTTPStatus.BAD_REQUEST)
        data = io.StringIO(newline='')
        writer = csv.writer(data, delimiter=delimiter, quotechar=quotechar)
        for row in rows:
            writer.writerow(format_(row))
        data = data.getvalue().encode(encoding)
        filename = slugify(Model.__names__()['model']) + '.csv'
        filename = filename.encode('latin-1', 'ignore')
        response = Response(data, mimetype='text/csv; charset=' + encoding)
        response.headers.add(
            'Content-Disposition', 'attachment', filename=filename)
        response.headers.add('Content-Length', len(data))
        return response


@app.route('/avatar/<base64:database_name>/<uuid>', methods={'GET'})
@with_pool
@with_transaction()
def avatar(request, pool, uuid):
    Avatar = pool.get('ir.avatar')

    try:
        avatar, = Avatar.search([
                ('uuid', '=', uuid),
                ])
    except ValueError:
        abort(HTTPStatus.NOT_FOUND)
    try:
        size = int(request.args.get('s', 64))
    except ValueError:
        abort(HTTPStatus.BAD_REQUEST)
    response = Response(avatar.get(size), mimetype='image/jpeg')
    response.headers['Cache-Control'] = (
        'max-age=%s, public' % AVATAR_TIMEOUT)
    response.add_etag()
    return response
