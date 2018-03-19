# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import gtk
import gobject
import glib
import pango
import gettext
import os
import subprocess
import re
import logging
import unicodedata
import colorsys
from decimal import Decimal
from functools import partial
from tryton.config import CONFIG
from tryton.config import TRYTON_ICON, PIXMAPS_DIR
import sys
import xmlrpclib
try:
    import hashlib
except ImportError:
    hashlib = None
    import md5
import webbrowser
import traceback
import tryton.rpc as rpc
import socket
import thread
import urllib
from string import Template
import shlex
try:
    import ssl
except ImportError:
    ssl = None
from threading import Lock
import dateutil.tz

from tryton.exceptions import TrytonServerError, TrytonError
from tryton.pyson import PYSONEncoder

_ = gettext.gettext


class TrytonIconFactory(gtk.IconFactory):

    batchnum = 10
    _tryton_icons = []
    _name2id = {}
    _locale_icons = set()
    _loaded_icons = set()

    def load_client_icons(self):
        for fname in os.listdir(PIXMAPS_DIR):
            name = os.path.splitext(fname)[0]
            if not name.startswith('tryton-'):
                continue
            if not os.path.isfile(os.path.join(PIXMAPS_DIR, fname)):
                continue
            try:
                pixbuf = gtk.gdk.pixbuf_new_from_file(
                        os.path.join(PIXMAPS_DIR, fname).decode('utf-8'))
            except (IOError, glib.GError):
                continue
            finally:
                self._locale_icons.add(name)
            icon_set = gtk.IconSet(pixbuf)
            self.add(name, icon_set)
        for name in ('ok', 'cancel'):
            icon_set = gtk.Style().lookup_icon_set('gtk-%s' % name)
            self.add('tryton-%s' % name, icon_set)
            self._locale_icons.add('tryton-%s' % name)

    def load_icons(self, refresh=False):
        if not refresh:
            self._name2id.clear()
            self._loaded_icons.clear()
        del self._tryton_icons[:]

        try:
            icons = rpc.execute('model', 'ir.ui.icon', 'list_icons',
                rpc.CONTEXT)
        except TrytonServerError:
            icons = []
        for icon_id, icon_name in icons:
            if refresh and icon_name in self._loaded_icons:
                continue
            self._tryton_icons.append((icon_id, icon_name))
            self._name2id[icon_name] = icon_id

    def register_icon(self, iconname):
        # iconname might be '' when page do not define icon
        if (not iconname
                or iconname in (self._loaded_icons | self._locale_icons)):
            return
        if iconname not in self._name2id:
            self.load_icons(refresh=True)
        icon_ref = (self._name2id[iconname], iconname)
        idx = self._tryton_icons.index(icon_ref)
        to_load = slice(max(0, idx - self.batchnum // 2),
            idx + self.batchnum // 2)
        ids = [e[0] for e in self._tryton_icons[to_load]]
        try:
            icons = rpc.execute('model', 'ir.ui.icon', 'read', ids,
                ['name', 'icon'], rpc.CONTEXT)
        except TrytonServerError:
            icons = []
        for icon in icons:
            pixbuf = _data2pixbuf(icon['icon'])
            self._tryton_icons.remove((icon['id'], icon['name']))
            del self._name2id[icon['name']]
            self._loaded_icons.add(icon['name'])
            iconset = gtk.IconSet(pixbuf)
            self.add(icon['name'], iconset)

ICONFACTORY = TrytonIconFactory()
ICONFACTORY.add_default()


class ModelAccess(object):

    batchnum = 100
    _access = {}
    _models = []

    def load_models(self, refresh=False):
        if not refresh:
            self._access.clear()
        del self._models[:]

        try:
            self._models = rpc.execute('model', 'ir.model', 'list_models',
                rpc.CONTEXT)
        except TrytonServerError:
            pass

    def __getitem__(self, model):
        if model in self._access:
            return self._access[model]
        if model not in self._models:
            self.load_models(refresh=True)
        idx = self._models.index(model)
        to_load = slice(max(0, idx - self.batchnum // 2),
            idx + self.batchnum // 2)
        try:
            access = rpc.execute('model', 'ir.model.access', 'get_access',
                self._models[to_load], rpc.CONTEXT)
        except TrytonServerError:
            access = {}
        self._access.update(access)
        return self._access[model]

MODELACCESS = ModelAccess()


class ModelHistory(object):
    _models = set()

    def load_history(self):
        self._models.clear()
        try:
            self._models.update(rpc.execute('model', 'ir.model',
                    'list_history', rpc.CONTEXT))
        except TrytonServerError:
            pass

    def __contains__(self, model):
        return model in self._models

MODELHISTORY = ModelHistory()


class ViewSearch(object):
    searches = {}

    def __init__(self):
        class Encoder(PYSONEncoder):
            def default(self, obj):
                if isinstance(obj, Decimal):
                    return float(obj)
                return super(Encoder, self).default(obj)
        self.encoder = Encoder()

    def load_searches(self):
        try:
            self.searches = rpc.execute('model', 'ir.ui.view_search',
                'get_search', rpc.CONTEXT)
        except TrytonServerError:
            self.searches = {}

    def __getitem__(self, model):
        return self.searches.get(model, [])

    def add(self, model, name, domain):
        try:
            id_, = RPCExecute('model', 'ir.ui.view_search',
                'create', [{
                        'model': model,
                        'name': name,
                        'domain': self.encoder.encode(domain),
                        }])
        except RPCException:
            return
        self.searches.setdefault(model, []).append((id_, name, domain))

    def remove(self, model, id_):
        try:
            RPCExecute('model', 'ir.ui.view_search', 'delete', [id_])
        except RPCException:
            return
        for i, domain in enumerate(self.searches[model]):
            if domain[0] == id_:
                del self.searches[model][i]
                break

VIEW_SEARCH = ViewSearch()


def find_in_path(name):
    if os.name == "nt":
        sep = ';'
    else:
        sep = ':'
    path = [directory for directory in os.environ['PATH'].split(sep)
            if os.path.isdir(directory)]
    for directory in path:
        val = os.path.join(directory, name)
        if os.path.isfile(val) or os.path.islink(val):
            return val
    return name


def request_server(server_widget):
    result = False
    parent = get_toplevel_window()
    dialog = gtk.Dialog(
        title=_('Tryton Connection'),
        parent=parent,
        flags=gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT |
        gtk.WIN_POS_CENTER_ON_PARENT |
        gtk.gdk.WINDOW_TYPE_HINT_DIALOG,)
    vbox = gtk.VBox()
    table = gtk.Table(2, 2, False)
    table.set_border_width(12)
    table.set_row_spacings(6)
    vbox.pack_start(table, False, True, 0)
    label_server = gtk.Label(_("Server:"))
    label_server.set_alignment(1, 0)
    label_server.set_padding(3, 0)
    table.attach(label_server, 0, 1, 0, 1, yoptions=False,
        xoptions=gtk.FILL)
    entry_port = gtk.Entry()
    entry_port.set_max_length(5)
    entry_port.set_text("8000")
    entry_port.set_activates_default(True)
    entry_port.set_width_chars(16)
    table.attach(entry_port, 1, 2, 1, 2, yoptions=False,
        xoptions=gtk.FILL)
    entry_server = gtk.Entry()
    entry_server.set_text("localhost")
    entry_server.set_activates_default(True)
    entry_server.set_width_chars(16)
    table.attach(entry_server, 1, 2, 0, 1, yoptions=False,
        xoptions=gtk.FILL | gtk.EXPAND)
    label_port = gtk.Label(_("Port:"))
    label_port.set_alignment(1, 0.5)
    label_port.set_padding(3, 3)
    table.attach(label_port, 0, 1, 1, 2, yoptions=False,
        xoptions=False)
    dialog.add_button("gtk-cancel", gtk.RESPONSE_CANCEL)
    dialog.add_button("gtk-ok", gtk.RESPONSE_OK)
    dialog.vbox.pack_start(vbox)
    dialog.set_icon(TRYTON_ICON)
    dialog.show_all()
    dialog.set_default_response(gtk.RESPONSE_OK)

    netloc = server_widget.get_text()
    entry_server.set_text(get_hostname(netloc))
    entry_port.set_text(str(get_port(netloc)))

    res = dialog.run()
    if res == gtk.RESPONSE_OK:
        host = entry_server.get_text()
        port = entry_port.get_text()
        url = '%s:%s' % (host, port)
        server_widget.set_text(url)
        result = (get_hostname(url), get_port(url))
    parent.present()
    dialog.destroy()
    return result


def get_toplevel_window():
    for window in gtk.window_list_toplevels():
        if window.is_active() and window.props.type == gtk.WINDOW_TOPLEVEL:
            return window
    from tryton.gui.main import Main
    return Main.get_main().window


def get_sensible_widget(window):
    from tryton.gui.main import Main
    main = Main.get_main()
    if main and window == main.window:
        focus_widget = window.get_focus()
        page = main.get_page()
        if page and focus_widget and focus_widget.is_ancestor(page.widget):
            return page.widget
    return window


def center_window(window, parent, sensible):
    sensible_allocation = sensible.get_allocation()
    if hasattr(sensible.get_window(), 'get_root_coords'):
        x, y = sensible.get_window().get_root_coords(
            sensible_allocation.x, sensible_allocation.y)
    else:
        x, y = sensible.get_window().get_origin()
        x += sensible_allocation.x
        y += sensible_allocation.y
    window_allocation = window.get_allocation()
    x = x + int((sensible_allocation.width - window_allocation.width) / 2)
    y = y + int((sensible_allocation.height - window_allocation.height) / 2)
    window.move(x, y)


def selection(title, values, alwaysask=False):
    if not values or len(values) == 0:
        return None
    elif len(values) == 1 and (not alwaysask):
        key = values.keys()[0]
        return (key, values[key])

    parent = get_toplevel_window()
    dialog = gtk.Dialog(_('Selection'), parent,
            gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
            (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                gtk.STOCK_OK, gtk.RESPONSE_OK))
    dialog.set_icon(TRYTON_ICON)
    dialog.set_default_response(gtk.RESPONSE_OK)
    dialog.set_default_size(400, 400)

    label = gtk.Label(title or _('Your selection:'))
    dialog.vbox.pack_start(label, False, False)
    dialog.vbox.pack_start(gtk.HSeparator(), False, True)

    scrolledwindow = gtk.ScrolledWindow()
    scrolledwindow.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
    treeview = gtk.TreeView()
    treeview.set_headers_visible(False)
    scrolledwindow.add(treeview)
    dialog.vbox.pack_start(scrolledwindow, True, True)

    treeview.get_selection().set_mode(gtk.SELECTION_SINGLE)
    cell = gtk.CellRendererText()
    column = gtk.TreeViewColumn("Widget", cell, text=0)
    treeview.append_column(column)
    treeview.set_search_column(0)

    model = gtk.ListStore(gobject.TYPE_STRING, gobject.TYPE_INT)
    keys = values.keys()
    keys.sort()
    i = 0
    for val in keys:
        model.append([str(val), i])
        i += 1

    treeview.set_model(model)
    treeview.connect('row-activated',
            lambda x, y, z: dialog.response(gtk.RESPONSE_OK) or True)

    dialog.show_all()
    response = dialog.run()
    res = None
    if response == gtk.RESPONSE_OK:
        sel = treeview.get_selection().get_selected()
        if sel:
            (model, i) = sel
            if i:
                index = model.get_value(i, 1)
                value = keys[index]
                res = (value, values[value])
    parent.present()
    dialog.destroy()
    return res


def file_selection(title, filename='',
        action=gtk.FILE_CHOOSER_ACTION_OPEN, preview=True, multi=False,
        filters=None):
    parent = get_toplevel_window()
    if action == gtk.FILE_CHOOSER_ACTION_OPEN:
        buttons = (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
            gtk.STOCK_OPEN, gtk.RESPONSE_OK)
    else:
        buttons = (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
            gtk.STOCK_SAVE, gtk.RESPONSE_OK)
    win = gtk.FileChooserDialog(title, None, action, buttons)
    win.set_transient_for(parent)
    win.set_icon(TRYTON_ICON)
    if filename:
        if action in (gtk.FILE_CHOOSER_ACTION_SAVE,
                gtk.FILE_CHOOSER_ACTION_CREATE_FOLDER):
            win.set_current_name(filename)
        else:
            win.set_filename(filename)
    if hasattr(win, 'set_do_overwrite_confirmation'):
        win.set_do_overwrite_confirmation(True)
    win.set_select_multiple(multi)
    win.set_default_response(gtk.RESPONSE_OK)
    if filters is not None:
        for filt in filters:
            win.add_filter(filt)

    def update_preview_cb(win, img):
        have_preview = False
        filename = win.get_preview_filename()
        if filename:
            try:
                pixbuf = gtk.gdk.pixbuf_new_from_file_at_size(
                    filename, 128, 128)
                img.set_from_pixbuf(pixbuf)
                have_preview = True
            except (IOError, glib.GError):
                pass
        win.set_preview_widget_active(have_preview)
        return

    if preview:
        img_preview = gtk.Image()
        win.set_preview_widget(img_preview)
        win.connect('update-preview', update_preview_cb, img_preview)

    if os.name == 'nt':
        encoding = 'utf-8'
    else:
        encoding = sys.getfilesystemencoding()
    button = win.run()
    if button != gtk.RESPONSE_OK:
        result = None
    elif not multi:
        result = win.get_filename()
        if result:
            result = unicode(result, encoding)
    else:
        result = [unicode(path, encoding) for path in win.get_filenames()]
    parent.present()
    win.destroy()
    return result


_slugify_strip_re = re.compile(r'[^\w\s-]')
_slugify_hyphenate_re = re.compile(r'[-\s]+')


def slugify(value):
    if not isinstance(value, unicode):
        value = unicode(value)
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore')
    value = unicode(_slugify_strip_re.sub('', value).strip().lower())
    return _slugify_hyphenate_re.sub('-', value)


def file_open(filename, type, print_p=False):
    def save():
        save_name = file_selection(_('Save As...'),
                action=gtk.FILE_CHOOSER_ACTION_SAVE)
        if save_name:
            file_p = open(filename, 'rb')
            save_p = open(save_name, 'wb+')
            save_p.write(file_p.read())
            save_p.close()
            file_p.close()

    if os.name == 'nt':
        operation = 'open'
        if print_p:
            operation = 'print'
        try:
            os.startfile(os.path.normpath(filename), operation)
        except WindowsError:
            save()
    elif sys.platform == 'darwin':
        try:
            subprocess.Popen(['/usr/bin/open', filename])
        except OSError:
            save()
    else:
        try:
            subprocess.Popen(['xdg-open', filename])
        except OSError:
            save()


def mailto(to=None, cc=None, subject=None, body=None, attachment=None):
    if CONFIG['client.email']:
        cmd = Template(CONFIG['client.email']).substitute(
                to=to or '',
                cc=cc or '',
                subject=subject or '',
                body=body or '',
                attachment=attachment or '',
                )
        args = shlex.split(str(cmd))
        subprocess.Popen(args)
        return
    if os.name != 'nt' and sys.platform != 'darwin':
        args = ['xdg-email', '--utf8']
        if cc:
            args.extend(['--cc', cc])
        if subject:
            args.extend(['--subject', subject])
        if body:
            args.extend(['--body', body])
        if attachment:
            args.extend(['--attach', attachment])
        if to:
            args.append(to)
        try:
            subprocess.Popen(args)
            return
        except OSError:
            pass
    # http://www.faqs.org/rfcs/rfc2368.html
    url = "mailto:"
    if to:
        if isinstance(to, unicode):
            to = to.encode('utf-8')
        url += urllib.quote(to.strip(), "@,")
    url += '?'
    if cc:
        if isinstance(cc, unicode):
            cc = cc.encode('utf-8')
        url += "&cc=" + urllib.quote(cc, "@,")
    if subject:
        if isinstance(subject, unicode):
            subject = subject.encode('utf-8')
        url += "&subject=" + urllib.quote(subject, "")
    if body:
        if isinstance(body, unicode):
            body = body.encode('utf-8')
        body = "\r\n".join(body.splitlines())
        url += "&body=" + urllib.quote(body, "")
    if attachment:
        if isinstance(attachment, unicode):
            attachment = attachment.encode('utf-8')
        url += "&attachment=" + urllib.quote(attachment, "")
    webbrowser.open(url, new=1)


class UniqueDialog(object):

    def __init__(self):
        self.running = False

    def build_dialog(self, *args):
        raise NotImplementedError

    def __call__(self, *args):
        if self.running:
            return

        parent = get_toplevel_window()
        dialog = self.build_dialog(parent, *args)
        dialog.set_icon(TRYTON_ICON)
        self.running = True
        dialog.show_all()
        response = dialog.run()
        parent.present()
        dialog.destroy()
        self.running = False
        return response


class MessageDialog(UniqueDialog):

    def build_dialog(self, parent, message, msg_type):
        dialog = gtk.MessageDialog(parent,
            gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT, msg_type,
            gtk.BUTTONS_OK, message)
        return dialog

    def __call__(self, message, msg_type=gtk.MESSAGE_INFO):
        super(MessageDialog, self).__call__(message, msg_type)

message = MessageDialog()


class WarningDialog(UniqueDialog):

    def build_dialog(self, parent, message, title, buttons=gtk.BUTTONS_OK):
        dialog = gtk.MessageDialog(parent, gtk.DIALOG_DESTROY_WITH_PARENT,
            gtk.MESSAGE_WARNING, buttons)
        dialog.set_markup('<b>%s</b>' % (to_xml(title)))
        dialog.format_secondary_markup(to_xml(message))
        return dialog

warning = WarningDialog()


class UserWarningDialog(WarningDialog):

    def __init__(self):
        super(UserWarningDialog, self).__init__()
        self.always = False

    def _set_always(self, toggle):
        self.always = toggle.get_active()

    def build_dialog(self, parent, message, title):
        dialog = super(UserWarningDialog, self).build_dialog(parent, message,
            title, gtk.BUTTONS_YES_NO)
        check = gtk.CheckButton(_('Always ignore this warning.'))
        check.connect_after('toggled', self._set_always)
        alignment = gtk.Alignment(0, 0.5)
        alignment.add(check)
        dialog.vbox.pack_start(alignment, True, False)
        label = gtk.Label(_('Do you want to proceed?'))
        label.set_alignment(1, 0.5)
        dialog.vbox.pack_start(label, True, True)
        return dialog

    def __call__(self, message, title):
        response = super(UserWarningDialog, self).__call__(message, title)
        if response == gtk.RESPONSE_YES:
            if self.always:
                return 'always'
            return 'ok'
        return 'cancel'

userwarning = UserWarningDialog()


class ConfirmationDialog(UniqueDialog):

    def build_dialog(self, parent, message):
        dialog = gtk.Dialog(_('Confirmation'), parent, gtk.DIALOG_MODAL
                | gtk.DIALOG_DESTROY_WITH_PARENT | gtk.WIN_POS_CENTER_ON_PARENT
                | gtk.gdk.WINDOW_TYPE_HINT_DIALOG)
        hbox = gtk.HBox()
        image = gtk.Image()
        image.set_from_stock('tryton-dialog-information',
                gtk.ICON_SIZE_DIALOG)
        image.set_padding(15, 15)
        hbox.pack_start(image, False, False)
        label = gtk.Label('%s' % (to_xml(message)))
        hbox.pack_start(label, True, True)
        dialog.vbox.pack_start(hbox)
        return dialog


class SurDialog(ConfirmationDialog):

    def build_dialog(self, parent, message):
        dialog = super(SurDialog, self).build_dialog(parent, message)
        dialog.add_button("gtk-cancel", gtk.RESPONSE_CANCEL)
        dialog.set_default(dialog.add_button("gtk-ok", gtk.RESPONSE_OK))
        dialog.set_default_response(gtk.RESPONSE_OK)
        return dialog

    def __call__(self, message):
        response = super(SurDialog, self).__call__(message)
        return response == gtk.RESPONSE_OK

sur = SurDialog()


class Sur3BDialog(ConfirmationDialog):

    response_mapping = {
        gtk.RESPONSE_YES: 'ok',
        gtk.RESPONSE_NO: 'ko',
        gtk.RESPONSE_CANCEL: 'cancel'
    }

    def build_dialog(self, parent, message):
        dialog = super(Sur3BDialog, self).build_dialog(parent, message)
        dialog.add_button("gtk-cancel", gtk.RESPONSE_CANCEL)
        dialog.add_button("gtk-no", gtk.RESPONSE_NO)
        dialog.set_default(dialog.add_button("gtk-yes", gtk.RESPONSE_YES))
        dialog.set_default_response(gtk.RESPONSE_YES)
        return dialog

    def __call__(self, message):
        response = super(Sur3BDialog, self).__call__(message)
        return self.response_mapping.get(response, 'cancel')

sur_3b = Sur3BDialog()


class AskDialog(UniqueDialog):

    def build_dialog(self, parent, question, visibility):
        win = gtk.Dialog(CONFIG['client.title'], parent,
                gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                    gtk.STOCK_OK, gtk.RESPONSE_OK))
        win.set_default_response(gtk.RESPONSE_OK)

        hbox = gtk.HBox()
        image = gtk.Image()
        image.set_from_stock('tryton-dialog-information',
                gtk.ICON_SIZE_DIALOG)
        hbox.pack_start(image)
        vbox = gtk.VBox()
        vbox.pack_start(gtk.Label(question))
        self.entry = gtk.Entry()
        self.entry.set_activates_default(True)
        self.entry.set_visibility(visibility)
        vbox.pack_start(self.entry)
        hbox.pack_start(vbox)
        win.vbox.pack_start(hbox)
        return win

    def __call__(self, question, visibility=True):
        if self.running:
            return

        parent = get_toplevel_window()
        dialog = self.build_dialog(parent, question, visibility=visibility)
        dialog.set_icon(TRYTON_ICON)
        self.running = True
        dialog.show_all()
        response = dialog.run()
        result = None
        if response == gtk.RESPONSE_OK:
            result = self.entry.get_text()
        parent.present()
        dialog.destroy()
        self.running = False
        return result

ask = AskDialog()


class ConcurrencyDialog(UniqueDialog):

    def build_dialog(self, parent, resource, obj_id, context):
        dialog = gtk.Dialog(_('Concurrency Exception'), parent,
            gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT |
            gtk.WIN_POS_CENTER_ON_PARENT | gtk.gdk.WINDOW_TYPE_HINT_DIALOG)
        dialog.set_default_response(gtk.RESPONSE_CANCEL)
        hbox = gtk.HBox()
        image = gtk.Image()
        image.set_from_stock('tryton-dialog-information',
                gtk.ICON_SIZE_DIALOG)
        image.set_padding(15, 15)
        hbox.pack_start(image, False, False)
        label = gtk.Label()
        label.set_padding(15, 15)
        label.set_use_markup(True)
        label.set_markup(_('<b>Write Concurrency Warning:</b>\n\n'
            'This record has been modified while you were editing it.\n'
            ' Choose:\n'
            '    - "Cancel" to cancel saving;\n'
            '    - "Compare" to see the modified version;\n'
            '    - "Write Anyway" to save your current version.'))
        hbox.pack_start(label, True, True)
        dialog.vbox.pack_start(hbox)
        dialog.add_button('gtk-cancel', gtk.RESPONSE_CANCEL)
        compare_button = gtk.Button(_('Compare'))
        image = gtk.Image()
        image.set_from_stock('tryton-find-replace', gtk.ICON_SIZE_BUTTON)
        compare_button.set_image(image)
        dialog.add_action_widget(compare_button, gtk.RESPONSE_APPLY)
        write_button = gtk.Button(_('Write Anyway'))
        image = gtk.Image()
        image.set_from_stock('tryton-save', gtk.ICON_SIZE_BUTTON)
        write_button.set_image(image)
        dialog.add_action_widget(write_button, gtk.RESPONSE_OK)
        return dialog

    def __call__(self, resource, obj_id, context):
        res = super(ConcurrencyDialog, self).__call__(resource, obj_id,
            context)

        if res == gtk.RESPONSE_OK:
            return True
        if res == gtk.RESPONSE_APPLY:
            from tryton.gui.window import Window
            Window.create(resource,
                res_id=obj_id,
                domain=[('id', '=', obj_id)],
                context=context,
                mode=['form', 'tree'])
        return False

concurrency = ConcurrencyDialog()


class ErrorDialog(UniqueDialog):

    def build_dialog(self, parent, title, details):
        dialog = gtk.Dialog(_('Error'), parent,
            gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT)

        but_send = gtk.Button(_('Report Bug'))
        dialog.add_action_widget(but_send, gtk.RESPONSE_OK)
        dialog.add_button("gtk-close", gtk.RESPONSE_CANCEL)
        dialog.set_default_response(gtk.RESPONSE_CANCEL)

        vbox = gtk.VBox()
        label_title = gtk.Label()
        label_title.set_markup('<b>' + _('Application Error.') + '</b>')
        label_title.set_padding(-1, 5)
        vbox.pack_start(label_title, False, False)
        vbox.pack_start(gtk.HSeparator(), False, False)

        hbox = gtk.HBox()
        image = gtk.Image()
        image.set_from_stock('tryton-dialog-error', gtk.ICON_SIZE_DIALOG)
        hbox.pack_start(image, False, False)

        scrolledwindow = gtk.ScrolledWindow()
        scrolledwindow.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scrolledwindow.set_shadow_type(gtk.SHADOW_NONE)

        viewport = gtk.Viewport()
        viewport.set_shadow_type(gtk.SHADOW_NONE)

        box = gtk.VBox()
        label_error = gtk.Label()
        label_error.set_markup('')
        label_error.set_alignment(0, 0.5)
        label_error.set_padding(-1, 14)
        label_error.modify_font(pango.FontDescription("monospace"))
        label_error.set_markup('<b>' + _('Error: ') + '</b>' + to_xml(title))
        box.pack_start(label_error, False, False)
        textview = gtk.TextView()
        buf = gtk.TextBuffer()
        buf.set_text(details)
        textview.set_buffer(buf)
        textview.set_editable(False)
        textview.set_sensitive(True)
        textview.modify_font(pango.FontDescription("monospace"))
        box.pack_start(textview, False, False)

        viewport.add(box)
        scrolledwindow.add(viewport)
        hbox.pack_start(scrolledwindow)

        vbox.pack_start(hbox)

        button_roundup = gtk.Button()
        button_roundup.set_relief(gtk.RELIEF_NONE)
        label_roundup = gtk.Label()
        label_roundup.set_markup(_('To report bugs you must have an account'
            ' on <u>%s</u>') % CONFIG['roundup.url'])
        label_roundup.set_alignment(1, 0.5)
        label_roundup.set_padding(20, 5)

        button_roundup.connect('clicked',
                lambda widget: webbrowser.open(CONFIG['roundup.url'], new=2))
        button_roundup.add(label_roundup)
        vbox.pack_start(button_roundup, False, False)

        dialog.vbox.pack_start(vbox)
        dialog.set_default_size(600, 400)
        return dialog

    def __call__(self, title, details):
        if title == details:
            title = ''
        log = logging.getLogger(__name__)
        log.error(details + '\n' + title)

        response = super(ErrorDialog, self).__call__(title, details)
        if response == gtk.RESPONSE_OK:
            send_bugtracker(title, details)

error = ErrorDialog()


def send_bugtracker(title, msg):
    from tryton import rpc
    parent = get_toplevel_window()
    win = gtk.Dialog(_('Bug Tracker'), parent,
            gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
            (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                gtk.STOCK_OK, gtk.RESPONSE_OK))
    win.set_icon(TRYTON_ICON)
    win.set_default_response(gtk.RESPONSE_OK)

    hbox = gtk.HBox()
    image = gtk.Image()
    image.set_from_stock('tryton-dialog-information',
            gtk.ICON_SIZE_DIALOG)
    hbox.pack_start(image, False, False)

    table = gtk.Table(2, 2)
    table.set_col_spacings(3)
    table.set_row_spacings(3)
    table.set_border_width(1)
    label_user = gtk.Label(_('User:'))
    label_user.set_alignment(1.0, 0.5)
    table.attach(label_user, 0, 1, 0, 1, yoptions=False,
            xoptions=gtk.FILL)
    entry_user = gtk.Entry()
    entry_user.set_activates_default(True)
    table.attach(entry_user, 1, 2, 0, 1, yoptions=False,
            xoptions=gtk.FILL)
    label_password = gtk.Label(_('Password:'))
    label_password.set_alignment(1.0, 0.5)
    table.attach(label_password, 0, 1, 1, 2, yoptions=False,
            xoptions=gtk.FILL)
    entry_password = gtk.Entry()
    entry_password.set_activates_default(True)
    entry_password.set_visibility(False)
    table.attach(entry_password, 1, 2, 1, 2, yoptions=False,
            xoptions=gtk.FILL)
    hbox.pack_start(table)

    win.vbox.pack_start(hbox)
    win.show_all()
    if rpc._USERNAME:
        entry_user.set_text(rpc._USERNAME)
        entry_password.grab_focus()
    else:
        entry_user.grab_focus()

    response = win.run()
    parent.present()
    user = entry_user.get_text()
    password = entry_password.get_text()
    win.destroy()
    if response == gtk.RESPONSE_OK:
        try:
            msg = msg.encode('ascii', 'replace')
            protocol = 'http'
            if ssl or hasattr(socket, 'ssl'):
                protocol = 'https'
            quote = partial(urllib.quote, safe="!$&'()*+,;=:")
            server = xmlrpclib.Server(
                ('%s://%s:%s@' + CONFIG['roundup.xmlrpc'])
                % (protocol, quote(user), quote(password)), allow_none=True)
            if hashlib:
                msg_md5 = hashlib.md5(msg + '\n' + title).hexdigest()
            else:
                msg_md5 = md5.new(msg + '\n' + title).hexdigest()
            if not title:
                title = '[no title]'
            issue_id = None
            msg_ids = server.filter('msg', None, {'summary': str(msg_md5)})
            for msg_id in msg_ids:
                summary = server.display(
                    'msg%s' % msg_id, 'summary')['summary']
                if summary == msg_md5:
                    issue_ids = server.filter(
                        'issue', None, {'messages': msg_id})
                    if issue_ids:
                        issue_id = issue_ids[0]
                        break
            if issue_id:
                # issue to same message already exists, add user to nosy-list
                server.set('issue' + str(issue_id), *['nosy=+' + user])
                message(
                    _('The same bug was already reported by another user.\n'
                        'To keep you informed your username is added '
                        'to the nosy-list of this issue') + '%s' % issue_id)
            else:
                # create a new issue for this error-message
                # first create message
                msg_id = server.create('msg', *['content=' + msg,
                    'author=' + user, 'summary=' + msg_md5])
                # second create issue with this message
                issue_id = server.create('issue', *['messages=' + str(msg_id),
                    'nosy=' + user, 'title=' + title, 'priority=bug'])
                message(_('Created new bug with ID ')
                    + 'issue%s' % issue_id)
            webbrowser.open(CONFIG['roundup.url'] + 'issue%s' % issue_id,
                new=2)
        except (socket.error, xmlrpclib.Fault), exception:
            if (isinstance(exception, xmlrpclib.Fault)
                    and 'roundup.cgi.exceptions.Unauthorised' in
                    exception.faultString):
                message(_('Connection error.\nBad username or password.'))
                return send_bugtracker(title, msg)
            tb_s = reduce(lambda x, y: x + y,
                    traceback.format_exception(sys.exc_type,
                        sys.exc_value, sys.exc_traceback))
            message(_('Exception:') + '\n' + tb_s, msg_type=gtk.MESSAGE_ERROR)


def to_xml(string):
    return string.replace('&', '&amp;'
        ).replace('<', '&lt;').replace('>', '&gt;')

PLOCK = Lock()


def process_exception(exception, *args, **kwargs):

    rpc_execute = kwargs.get('rpc_execute', rpc.execute)

    if isinstance(exception, TrytonServerError):
        if exception.faultCode == 'UserWarning':
            name, msg, description = exception.args
            res = userwarning(description, msg)
            if res in ('always', 'ok'):
                RPCExecute('model', 'res.user.warning', 'create', [{
                            'user': rpc._USER,
                            'name': name,
                            'always': (res == 'always'),
                            }],
                    process_exception=False)
                return rpc_execute(*args)
        elif exception.faultCode == 'UserError':
            msg, description = exception.args
            warning(description, msg)
        elif exception.faultCode == 'ConcurrencyException':
            if len(args) >= 6:
                if concurrency(args[1], args[3][0], args[5]):
                    if '_timestamp' in args[5]:
                        del args[5]['_timestamp']
                    return rpc_execute(*args)
            else:
                message(_('Concurrency Exception'), msg_type=gtk.MESSAGE_ERROR)
        elif (exception.faultCode.startswith('403')
                or exception.faultCode.startswith('401')):
            from tryton.gui.main import Main
            if PLOCK.acquire(False):
                language = CONFIG['client.lang']
                func = lambda parameters: rpc.login(
                    rpc._HOST, rpc._PORT, rpc._DATABASE, rpc._USERNAME,
                    parameters, language)
                try:
                    Login(func)
                except TrytonError, exception:
                    if exception.faultCode == 'QueryCanceled':
                        Main.get_main().sig_quit()
                    raise
                finally:
                    PLOCK.release()
                if args:
                    return rpc_execute(*args)
        else:
            error(exception.faultCode, exception.faultString)
    else:
        error(str(exception), traceback.format_exc())
    raise RPCException(exception)


class Login(object):
    def __init__(self, func):
        parameters = {}
        while True:
            try:
                func(parameters)
            except TrytonServerError, exception:
                if exception.faultCode.startswith('403'):
                    parameters.clear()
                    continue
                if exception.faultCode != 'LoginException':
                    raise
                name, message, type = exception.args
                value = getattr(self, 'get_%s' % type)(message)
                if value is None:
                    raise TrytonError('QueryCanceled')
                parameters[name] = value
                continue
            else:
                return

    @classmethod
    def get_char(self, message):
        return ask(message)

    @classmethod
    def get_password(self, message):
        return ask(message, visibility=False)


def node_attributes(node):
    result = {}
    attrs = node.attributes
    if attrs is None:
        return {}
    for i in range(attrs.length):
        result[str(attrs.item(i).localName)] = str(attrs.item(i).nodeValue)
    return result


def hex2rgb(hexstring, digits=2):
    """
    Converts a hexstring color to a rgb tuple.
    Example: #ff0000 -> (1.0, 0.0, 0.0)
    digits is an integer number telling how many characters should be
    interpreted for each component in the hexstring.
    """
    if isinstance(hexstring, (tuple, list)):
        return hexstring
    top = float(int(digits * 'f', 16))
    r = int(hexstring[1:digits + 1], 16)
    g = int(hexstring[digits + 1:digits * 2 + 1], 16)
    b = int(hexstring[digits * 2 + 1:digits * 3 + 1], 16)
    return r / top, g / top, b / top


def highlight_rgb(r, g, b, amount=0.1):
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    return colorsys.hsv_to_rgb(h, s, (v + amount) % 1)


def generateColorscheme(masterColor, keys, light=0.1):
    """
    Generates a dictionary where the keys match the keys argument and
    the values are colors derivated from the masterColor.
    Each color has a value higher then the previous of `light`.
    Each color has a hue separated from the previous by the golden angle.
    The masterColor is given in a hex string format.
    """
    r, g, b = hex2rgb(COLOR_SCHEMES.get(masterColor, masterColor))
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    if keys:
        light = min(light, (1. - v) / len(keys))
    golden_angle = 0.618033988749895
    return {key: colorsys.hsv_to_rgb((h + golden_angle * i) % 1,
            s, (v + light * i) % 1) for i, key in enumerate(keys)}


class RPCException(Exception):

    def __init__(self, exception):
        super(RPCException, self).__init__(exception)
        self.exception = exception


class RPCProgress(object):

    def __init__(self, method, args):
        self.method = method
        self.args = args
        self.parent = None
        self.res = None
        self.error = False
        self.exception = None

    def start(self):
        try:
            self.res = getattr(rpc, self.method)(*self.args)
        except Exception, exception:
            self.error = True
            self.res = False
            self.exception = exception
        else:
            if not self.res:
                self.error = True
        if self.callback:
            # Post to GTK queue to be run by the main thread
            gobject.idle_add(self.process)
        return True

    def run(self, process_exception_p=True, callback=None):
        self.process_exception_p = process_exception_p
        self.callback = callback

        if callback:
            # Parent is only useful if it is asynchronous
            # otherwise the cursor is not updated.
            self.parent = get_toplevel_window()
            if self.parent.get_window():
                watch = gtk.gdk.Cursor(gtk.gdk.WATCH)
                self.parent.get_window().set_cursor(watch)
            thread.start_new_thread(self.start, ())
            return
        else:
            self.start()
            return self.process()

    def process(self):
        if self.parent and self.parent.get_window():
            self.parent.get_window().set_cursor(None)

        if self.exception and self.process_exception_p:
            def rpc_execute(*args):
                return RPCProgress('execute', args).run(
                    self.process_exception_p, self.callback)
            try:
                return process_exception(
                    self.exception, *self.args, rpc_execute=rpc_execute)
            except RPCException, exception:
                self.exception = exception

        def return_():
            if self.exception:
                raise self.exception
            else:
                return self.res

        if self.callback:
            self.callback(return_)
        else:
            return return_()


def RPCExecute(*args, **kwargs):
    rpc_context = rpc.CONTEXT.copy()
    if kwargs.get('context'):
        rpc_context.update(kwargs['context'])
    args = args + (rpc_context,)
    process_exception = kwargs.get('process_exception', True)
    callback = kwargs.get('callback')
    return RPCProgress('execute', args).run(process_exception, callback)


def RPCContextReload(callback=None):
    def update(context):
        rpc.CONTEXT.clear()
        try:
            rpc.CONTEXT.update(context())
        except RPCException:
            pass
        if callback:
            callback()
    # Use RPCProgress to not send rpc.CONTEXT
    RPCProgress('execute', ('model', 'res.user', 'get_preferences', True, {})
        ).run(True, update)


class Tooltips(object):
    _tooltips = None

    def set_tip(self, widget, tip_text):
        if hasattr(widget, 'set_tooltip_text'):
            return widget.set_tooltip_text(tip_text)
        if not self._tooltips:
            self._tooltips = gtk.Tooltips()
        return self._tooltips.set_tip(widget, tip_text)

    def enable(self):
        if self._tooltips:
            self._tooltips.enable()

    def disable(self):
        if self._tooltips:
            self._tooltips.disable()

COLOR_SCHEMES = {
    'red': '#cf1d1d',
    'green': '#3fb41b',
    'blue': '#224565',
    'grey': '#444444',
    'black': '#000000',
    'darkcyan': '#305755',
}


def filter_domain(domain):
    '''
    Return the biggest subset of domain with only AND operator
    '''
    res = []
    for arg in domain:
        if isinstance(arg, basestring):
            if arg == 'OR':
                res = []
                break
            continue
        if isinstance(arg, tuple):
            res.append(arg)
        elif isinstance(arg, list):
            res.extend(filter_domain(arg))
    return res


def timezoned_date(date, reverse=False):
    lzone = dateutil.tz.tzlocal()
    szone = dateutil.tz.tzutc()
    if reverse:
        lzone, szone = szone, lzone
    return date.replace(tzinfo=szone).astimezone(lzone).replace(tzinfo=None)


def untimezoned_date(date):
    return timezoned_date(date, reverse=True).replace(tzinfo=None)


def humanize(size):
    for x in ('bytes', 'KB', 'MB', 'GB', 'TB', 'PB'):
        if size < 1000:
            return '%3.1f%s' % (size, x)
        size /= 1000.0


def get_hostname(netloc):
    if '[' in netloc and ']' in netloc:
        hostname = netloc.split(']')[0][1:]
    elif ':' in netloc:
        hostname = netloc.split(':')[0]
    else:
        hostname = netloc
    return hostname.strip()


def get_port(netloc):
    netloc = netloc.split(']')[-1]
    if ':' in netloc:
        try:
            return int(netloc.split(':')[1])
        except ValueError:
            pass
    return 8000


def resize_pixbuf(pixbuf, width, height):
    img_height = pixbuf.get_height()
    height = min(img_height, height) if height != -1 else img_height
    img_width = pixbuf.get_width()
    width = min(img_width, width) if width != -1 else img_width

    if img_width / width < img_height / height:
        width = float(img_width) / float(img_height) * float(height)
    else:
        height = float(img_height) / float(img_width) * float(width)
    return pixbuf.scale_simple(int(width), int(height),
        gtk.gdk.INTERP_BILINEAR)


def _data2pixbuf(data):
    loader = gtk.gdk.PixbufLoader()
    loader.write(bytes(data))
    loader.close()
    return loader.get_pixbuf()

BIG_IMAGE_SIZE = 10 ** 6
with open(os.path.join(PIXMAPS_DIR, 'tryton-noimage.png'), 'rb') as no_image:
    NO_IMG_PIXBUF = _data2pixbuf(no_image.read())


def data2pixbuf(data):
    pixbuf = NO_IMG_PIXBUF
    if data:
        try:
            pixbuf = _data2pixbuf(data)
        except glib.GError:
            pass
    return pixbuf


def get_label_attributes(readonly, required):
    "Return the pango attributes applied to a label according to its state"
    if readonly:
        style = pango.STYLE_NORMAL
        weight = pango.WEIGHT_NORMAL
    else:
        style = pango.STYLE_ITALIC
        if required:
            weight = pango.WEIGHT_BOLD
        else:
            weight = pango.WEIGHT_NORMAL
    attrlist = pango.AttrList()
    if hasattr(pango, 'AttrWeight'):
        attrlist.change(pango.AttrWeight(weight, 0, -1))
    if hasattr(pango, 'AttrStyle'):
        attrlist.change(pango.AttrStyle(style, 0, -1))
    return attrlist


def ellipsize(string, length):
    if len(string) <= length:
        return string
    ellipsis = _('...')
    return string[:length - len(ellipsis)] + ellipsis
