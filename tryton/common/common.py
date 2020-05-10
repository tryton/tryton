# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import gtk
import gobject
import glib
import pango
import gettext
import os
import subprocess
import tempfile
import re
import logging
import unicodedata
import colorsys
import xml.etree.ElementTree as ET
from collections import defaultdict
from decimal import Decimal
try:
    from http import HTTPStatus
except ImportError:
    from http import client as HTTPStatus
from functools import partial
from tryton.config import CONFIG
from tryton.config import TRYTON_ICON, PIXMAPS_DIR
import sys
import xmlrpc.client
from functools import reduce
try:
    import hashlib
except ImportError:
    hashlib = None
    import md5
import webbrowser
import traceback
import tryton.rpc as rpc
import socket
import _thread
import urllib.request
import urllib.parse
import urllib.error
from string import Template
import shlex
try:
    import ssl
except ImportError:
    ssl = None
from threading import Lock

from gi.repository import Gtk

from tryton import __version__
from tryton.exceptions import TrytonServerError, TrytonError
from tryton.pyson import PYSONEncoder
from .underline import set_underline
from .widget_style import widget_class

_ = gettext.gettext
logger = logging.getLogger(__name__)


class IconFactory:

    batchnum = 10
    _tryton_icons = []
    _name2id = {}
    _icons = {}
    _local_icons = {}
    _pixbufs = defaultdict(dict)

    @classmethod
    def load_local_icons(cls):
        for fname in os.listdir(PIXMAPS_DIR):
            name = os.path.splitext(fname)[0]
            path = os.path.join(PIXMAPS_DIR, fname)
            cls._local_icons[name] = path

    @classmethod
    def load_icons(cls, refresh=False):
        if not refresh:
            cls._name2id.clear()
            cls._icons.clear()
        del cls._tryton_icons[:]

        try:
            icons = rpc.execute('model', 'ir.ui.icon', 'list_icons',
                rpc.CONTEXT)
        except TrytonServerError:
            icons = []
        for icon_id, icon_name in icons:
            if refresh and icon_name in cls._icons:
                continue
            cls._tryton_icons.append((icon_id, icon_name))
            cls._name2id[icon_name] = icon_id

    @classmethod
    def register_icon(cls, iconname):
        # iconname might be '' when page do not define icon
        if (not iconname
                or iconname in cls._icons
                or iconname in cls._local_icons):
            return
        if iconname not in cls._name2id:
            cls.load_icons(refresh=True)
        try:
            icon_ref = (cls._name2id[iconname], iconname)
        except KeyError:
            return
        idx = cls._tryton_icons.index(icon_ref)
        to_load = slice(max(0, idx - cls.batchnum // 2),
            idx + cls.batchnum // 2)
        ids = [e[0] for e in cls._tryton_icons[to_load]]
        try:
            icons = rpc.execute('model', 'ir.ui.icon', 'read', ids,
                ['name', 'icon'], rpc.CONTEXT)
        except TrytonServerError:
            icons = []
        for icon in icons:
            name = icon['name']
            data = icon['icon'].encode('utf-8')
            cls._icons[name] = data
            cls._tryton_icons.remove((icon['id'], icon['name']))
            del cls._name2id[icon['name']]

    @classmethod
    def get_pixbuf(cls, iconname, size=Gtk.IconSize.MENU, color=None):
        cls.register_icon(iconname)
        if iconname not in cls._pixbufs[size]:
            if iconname in cls._icons:
                data = cls._icons[iconname]
            elif iconname in cls._local_icons:
                path = cls._local_icons[iconname]
                with open(path, 'rb') as fp:
                    data = fp.read()
            else:
                logger.error("Unknown icon %s" % iconname)
                return
            if color is None:
                color = CONFIG['icon.color']
            try:
                ET.register_namespace('', 'http://www.w3.org/2000/svg')
                root = ET.fromstring(data)
                root.attrib['fill'] = color
                data = ET.tostring(root)
            except ET.ParseError:
                pass
            width = height = {
                Gtk.IconSize.MENU: 16,
                Gtk.IconSize.SMALL_TOOLBAR: 16,
                Gtk.IconSize.LARGE_TOOLBAR: 24,
                Gtk.IconSize.BUTTON: 16,
                Gtk.IconSize.DND: 12,
                Gtk.IconSize.DIALOG: 48,
                }.get(size)
            cls._pixbufs[size][iconname] = data2pixbuf(data, width, height)
        return cls._pixbufs[size][iconname]

    @classmethod
    def get_image(cls, iconname, size=Gtk.IconSize.BUTTON, color=None):
        pixbuf = cls.get_pixbuf(iconname, size, color)
        image = Gtk.Image()
        image.set_from_pixbuf(pixbuf)
        return image


IconFactory.load_local_icons()


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


def get_toplevel_window():
    from tryton.gui.main import Main
    return Main().get_active_window()


def get_sensible_widget(window):
    from tryton.gui.main import Main
    main = Main()
    if main and window == main.window:
        focus_widget = window.get_focus()
        page = main.get_page()
        if page and focus_widget and focus_widget.is_ancestor(page.widget):
            return page.widget
    return window


def selection(title, values, alwaysask=False):
    if not values or len(values) == 0:
        return None
    elif len(values) == 1 and (not alwaysask):
        key = list(values.keys())[0]
        return (key, values[key])

    parent = get_toplevel_window()
    dialog = gtk.Dialog(_('Selection'), parent,
            gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT)
    dialog.add_button(set_underline(_("Cancel")), gtk.RESPONSE_CANCEL)
    dialog.add_button(set_underline(_("OK")), gtk.RESPONSE_OK)
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
    keys = list(values.keys())
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
        buttons = (set_underline(_("Cancel")), gtk.RESPONSE_CANCEL,
            set_underline(_("Select")), gtk.RESPONSE_OK)
    else:
        buttons = (set_underline(_("Cancel")), gtk.RESPONSE_CANCEL,
            set_underline(_("Save")), gtk.RESPONSE_OK)
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

    button = win.run()
    if button != gtk.RESPONSE_OK:
        result = None
    elif not multi:
        result = win.get_filename()
    else:
        result = win.get_filenames()
    parent.present()
    win.destroy()
    return result


_slugify_strip_re = re.compile(r'[^\w\s-]')
_slugify_hyphenate_re = re.compile(r'[-\s]+')


def slugify(value):
    if not isinstance(value, str):
        value = str(value)
    value = unicodedata.normalize('NFKD', value)
    value = str(_slugify_strip_re.sub('', value).strip())
    return _slugify_hyphenate_re.sub('-', value)


def file_write(filename, data):
    if isinstance(data, str):
        data = data.encode('utf-8')
    dtemp = tempfile.mkdtemp(prefix='tryton_')
    if not isinstance(filename, str):
        name, ext = filename
    else:
        name, ext = os.path.splitext(filename)
    filename = ''.join([slugify(name), os.extsep, slugify(ext)])
    filepath = os.path.join(dtemp, filename)
    with open(filepath, 'wb') as fp:
        fp.write(data)
    return filepath


def file_open(filename, type=None, print_p=False):
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
        url += urllib.parse.quote(to.strip(), "@,")
    url += '?'
    if cc:
        url += "&cc=" + urllib.parse.quote(cc, "@,")
    if subject:
        url += "&subject=" + urllib.parse.quote(subject, "")
    if body:
        body = "\r\n".join(body.splitlines())
        url += "&body=" + urllib.parse.quote(body, "")
    if attachment:
        url += "&attachment=" + urllib.parse.quote(attachment, "")
    webbrowser.open(url, new=1)


class UniqueDialog(object):

    def __init__(self):
        self.running = False

    def build_dialog(self, *args):
        raise NotImplementedError

    def process_response(self, response):
        return response

    def __call__(self, *args, **kwargs):
        if self.running:
            return

        parent = kwargs.pop('parent', None)
        if not parent:
            parent = get_toplevel_window()
        dialog = self.build_dialog(parent, *args, **kwargs)
        dialog.set_icon(TRYTON_ICON)
        self.running = True
        dialog.show_all()
        response = dialog.run()
        response = self.process_response(response)
        if parent:
            parent.present()
        dialog.destroy()
        self.running = False
        return response


class MessageDialog(UniqueDialog):

    def build_dialog(self, parent, message, msg_type=gtk.MESSAGE_INFO,
            buttons=gtk.BUTTONS_OK, secondary=None):
        dialog = gtk.MessageDialog(parent,
            gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT, msg_type,
            buttons, message)
        if secondary:
            dialog.format_secondary_text(secondary)
        return dialog

    def __call__(self, message, *args, **kwargs):
        return super(MessageDialog, self).__call__(message, *args, **kwargs)


message = MessageDialog()


class WarningDialog(MessageDialog):

    def __call__(self, message, title, buttons=gtk.BUTTONS_OK, **kwargs):
        return super().__call__(
            title, gtk.MESSAGE_WARNING, buttons, message, **kwargs)


warning = WarningDialog()


class UserWarningDialog(WarningDialog):

    def build_dialog(self, *args, **kwargs):
        dialog = super().build_dialog(*args, **kwargs)
        self.always = Gtk.CheckButton(label=_('Always ignore this warning.'))
        alignment = Gtk.Alignment(xalign=0, yalign=0.5)
        alignment.add(self.always)
        dialog.vbox.pack_start(alignment, expand=True, fill=False, padding=0)
        label = Gtk.Label(
            label=_('Do you want to proceed?'), halign=Gtk.Align.END)
        dialog.vbox.pack_start(label, expand=True, fill=True, padding=0)
        return dialog

    def process_response(self, response):
        if response == Gtk.ResponseType.YES:
            if self.always.get_active():
                return 'always'
            return 'ok'
        return 'cancel'

    def __call__(self, message, title):
        return super().__call__(message, title, gtk.BUTTONS_YES_NO)


userwarning = UserWarningDialog()


class ConfirmationDialog(MessageDialog):

    def __call__(self, message, *args, **kwargs):
        return super().__call__(message, gtk.MESSAGE_QUESTION, *args, **kwargs)


class SurDialog(ConfirmationDialog):

    def __call__(self, message):
        response = super().__call__(message, buttons=gtk.BUTTONS_YES_NO)
        return response == gtk.RESPONSE_YES


sur = SurDialog()


class Sur3BDialog(ConfirmationDialog):

    response_mapping = {
        gtk.RESPONSE_YES: 'ok',
        gtk.RESPONSE_NO: 'ko',
        gtk.RESPONSE_CANCEL: 'cancel'
    }

    def build_dialog(self, *args, **kwargs):
        dialog = super().build_dialog(*args, **kwargs)
        dialog.add_button(set_underline(_("Cancel")), gtk.RESPONSE_CANCEL)
        dialog.add_button(set_underline(_("No")), gtk.RESPONSE_NO)
        dialog.add_button(set_underline(_("Yes")), gtk.RESPONSE_YES)
        dialog.set_default_response(gtk.RESPONSE_YES)
        return dialog

    def __call__(self, message):
        response = super().__call__(message, buttons=gtk.BUTTONS_NONE)
        return self.response_mapping.get(response, 'cancel')


sur_3b = Sur3BDialog()


class AskDialog(MessageDialog):

    def build_dialog(self, *args, **kwargs):
        visibility = kwargs.pop('visibility')
        dialog = super().build_dialog(*args, **kwargs)
        dialog.set_default_response(gtk.RESPONSE_OK)
        box = dialog.get_message_area()
        self.entry = gtk.Entry()
        self.entry.set_activates_default(True)
        self.entry.set_visibility(visibility)
        box.pack_start(self.entry)
        return dialog

    def process_response(self, response):
        if response == gtk.RESPONSE_OK:
            return self.entry.get_text()

    def __call__(self, question, visibility=True):
        return super().__call__(
            question, gtk.MESSAGE_QUESTION, buttons=gtk.BUTTONS_OK_CANCEL,
            visibility=visibility)


ask = AskDialog()


class ConcurrencyDialog(UniqueDialog):

    def build_dialog(self, parent, resource, obj_id, context):
        tooltips = Tooltips()
        dialog = gtk.MessageDialog(parent,
            gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
            gtk.MESSAGE_QUESTION, gtk.BUTTONS_NONE,
            _('Concurrency Exception'))
        dialog.format_secondary_text(
            _('This record has been modified while you were editing it.'))
        cancel_button = dialog.add_button(
            set_underline(_("Cancel")), gtk.RESPONSE_CANCEL)
        tooltips.set_tip(cancel_button, _('Cancel saving'))
        compare_button = dialog.add_button(
            set_underline(_("Compare")), gtk.RESPONSE_APPLY)
        tooltips.set_tip(compare_button, _('See the modified version'))
        write_button = dialog.add_button(
            set_underline(_("Write Anyway")), gtk.RESPONSE_OK)
        tooltips.set_tip(write_button, _('Save your current version'))
        dialog.set_default_response(gtk.RESPONSE_CANCEL)
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
        dialog = gtk.MessageDialog(parent,
            gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
            gtk.MESSAGE_ERROR, gtk.BUTTONS_NONE,
            _('Application Error'))
        dialog.set_default_size(600, 400)

        dialog.add_button(set_underline(_("Report Bug")), gtk.RESPONSE_OK)
        dialog.add_button(set_underline(_("Close")), gtk.RESPONSE_CANCEL)
        dialog.set_default_response(gtk.RESPONSE_CANCEL)

        vbox = dialog.vbox

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
        box.pack_start(textview, True, True)

        viewport.add(box)
        scrolledwindow.add(viewport)
        vbox.pack_start(scrolledwindow, expand=True, fill=True)

        button_roundup = Gtk.LinkButton.new_with_label(
            CONFIG['roundup.url'],
            _('To report bugs you must have an account on %s') %
            CONFIG['roundup.url'])
        button_roundup.set_alignment(0, 0.5)
        button_roundup.connect('activate-link',
                lambda widget: webbrowser.open(CONFIG['roundup.url'], new=2))
        vbox.pack_start(button_roundup, False, False)

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
    parent = get_toplevel_window()
    win = gtk.Dialog(_('Bug Tracker'), parent,
            gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT)
    win.add_button(set_underline(_("Cancel")), gtk.RESPONSE_CANCEL)
    win.add_button(set_underline(_("OK")), gtk.RESPONSE_OK)
    win.set_icon(TRYTON_ICON)
    win.set_default_response(gtk.RESPONSE_OK)

    hbox = gtk.HBox()
    hbox.pack_start(
        IconFactory.get_image(
            'tryton-info', gtk.ICON_SIZE_DIALOG),
        False, False)

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
    entry_user.grab_focus()

    response = win.run()
    parent.present()
    user = entry_user.get_text()
    password = entry_password.get_text()
    win.destroy()
    if response == gtk.RESPONSE_OK:
        try:
            msg = msg.encode('ascii', 'replace')
            title = title.encode('ascii', 'replace')
            protocol = 'http'
            if ssl or hasattr(socket, 'ssl'):
                protocol = 'https'
            quote = partial(urllib.parse.quote, safe="!$&'()*+,;=:")
            server = xmlrpc.client.Server(
                ('%s://%s:%s@' + CONFIG['roundup.xmlrpc'])
                % (protocol, quote(user), quote(password)), allow_none=True)
            if hashlib:
                msg_md5 = hashlib.md5(msg + b'\n' + title).hexdigest()
            else:
                msg_md5 = md5.new(msg + b'\n' + title).hexdigest()
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
        except (socket.error, xmlrpc.client.Fault) as exception:
            if (isinstance(exception, xmlrpc.client.Fault)
                    and 'roundup.cgi.exceptions.Unauthorised' in
                    exception.faultString):
                message(_('Connection error.\nBad username or password.'))
                return send_bugtracker(title, msg)
            tb_s = reduce(lambda x, y: x + y,
                    traceback.format_exception(sys.exc_info()[0],
                        sys.exc_info()[1], sys.exc_info()[2]))
            message(_('Exception:') + '\n' + tb_s, msg_type=gtk.MESSAGE_ERROR)


def check_version(box, version=__version__):
    def info_bar_response(info_bar, response, box, url):
        if response == Gtk.ResponseType.ACCEPT:
            webbrowser.open(url)
        box.remove(info_bar)

    class HeadRequest(urllib.request.Request):
        def get_method(self):
            return 'HEAD'

    version = version.split('.')
    series = '.'.join(version[:2])
    version[2] = str(int(version[2]) + 1)
    version = '.'.join(version)
    filename = 'tryton-%s.tar.gz' % version
    if hasattr(sys, 'frozen'):
        if sys.platform == 'win32':
            filename = 'tryton-%s.exe' % version
        elif sys.platform == 'darwin':
            filename = 'tryton-%s.dmg' % version
    url = list(urllib.parse.urlparse(CONFIG['download.url']))
    url[2] = '/%s/%s' % (series, filename)
    url = urllib.parse.urlunparse(url)

    logger.info(_("Check URL: %s"), url)
    try:
        urllib.request.urlopen(
            HeadRequest(url), timeout=5, cafile=rpc._CA_CERTS)
    except (urllib.error.HTTPError, socket.timeout):
        return True
    except Exception:
        logger.error(
            _("Unable to check for new version"), exc_info=True)
        return True
    else:
        if check_version(box, version):
            info_bar = Gtk.InfoBar()
            info_bar.get_content_area().pack_start(
                gtk.Label(_("A new version is available!")))
            info_bar.set_show_close_button(True)
            info_bar.add_button(_("Download"), Gtk.ResponseType.ACCEPT)
            info_bar.connect('response', info_bar_response, box, url)
            box.pack_start(info_bar)
            info_bar.show_all()
        return False


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
        elif exception.faultCode == str(int(HTTPStatus.UNAUTHORIZED)):
            from tryton.gui.main import Main
            if PLOCK.acquire(False):
                try:
                    Login()
                except TrytonError as exception:
                    if exception.faultCode == 'QueryCanceled':
                        Main().on_quit()
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
    def __init__(self, func=rpc.login):
        parameters = {}
        while True:
            try:
                func(parameters)
            except TrytonServerError as exception:
                if exception.faultCode == str(int(HTTPStatus.UNAUTHORIZED)):
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
    def get_char(cls, message):
        return ask(message)

    @classmethod
    def get_password(cls, message):
        return ask(message, visibility=False)


class Logout:
    def __init__(self):
        try:
            rpc.logout()
        except TrytonServerError:
            pass


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
        except Exception as exception:
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
            _thread.start_new_thread(self.start, ())
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
            except RPCException as exception:
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
        rpc.context_reset()
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
        if isinstance(arg, str):
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
    try:
        from dateutil.tz.win import tzwinlocal as tzlocal
    except ImportError:
        from dateutil.tz import tzlocal
    from dateutil.tz import tzutc

    lzone = tzlocal()
    szone = tzutc()
    if reverse:
        lzone, szone = szone, lzone
    return date.replace(tzinfo=szone).astimezone(lzone).replace(tzinfo=None)


def untimezoned_date(date):
    return timezoned_date(date, reverse=True)


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


def _data2pixbuf(data, width=None, height=None):
    loader = gtk.gdk.PixbufLoader()
    if width and height:
        loader.set_size(width, height)
    loader.write(data)
    loader.close()
    return loader.get_pixbuf()


def data2pixbuf(data, width=None, height=None):
    if data:
        try:
            return _data2pixbuf(data, width, height)
        except glib.GError:
            pass


def apply_label_attributes(label, readonly, required):
    if not readonly:
        widget_class(label, 'editable', True)
        widget_class(label, 'required', required)
    else:
        widget_class(label, 'editable', False)
        widget_class(label, 'required', False)


def ellipsize(string, length):
    if len(string) <= length:
        return string
    ellipsis = _('...')
    return string[:length - len(ellipsis)] + ellipsis


def date_format(format_):
    return format_ or rpc.CONTEXT.get('locale', {}).get('date', '%x')
