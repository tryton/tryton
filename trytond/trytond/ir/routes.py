# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
try:
    from http import HTTPStatus
except ImportError:
    from http import client as HTTPStatus

from werkzeug.exceptions import abort
from werkzeug.utils import redirect
from werkzeug.wrappers import Response

from trytond.i18n import gettext
from trytond.config import config
from trytond.wsgi import app
from trytond.protocols.wrappers import with_pool, with_transaction
from trytond.transaction import Transaction

SOURCE = config.get(
    'html', 'src', default='https://cloud.tinymce.com/stable/tinymce.min.js')


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
            'model': field.model.name,
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
        plugins: 'fullscreen autosave %(plugins)s',
        removed_menuitems: 'newdocument',
        toolbar: 'save | undo redo | styleselect | bold italic | ' +
            'alignleft aligncenter alignright alignjustify | ' +
            'bullist numlist outdent indent | link image | close',
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
