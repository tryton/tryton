#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

import gtk
import gobject
import glib
import pango
import gettext
import os
import re
import logging
from tryton.config import CONFIG
from tryton.config import TRYTON_ICON, PIXMAPS_DIR, DATA_DIR
import time
import sys
import xmlrpclib
try:
    import hashlib
except ImportError:
    hashlib = None
    import md5
import webbrowser
import traceback
import threading
import tryton.rpc as rpc
import locale
import socket
import tempfile
from tryton.version import VERSION
import thread
import urllib
from string import Template
import shlex
try:
    import ssl
except ImportError:
    ssl = None
import dis
from threading import Lock, Semaphore
try:
    import pytz
except ImportError:
    pytz = None

from tryton.exceptions import (TrytonServerError, TrytonError,
    TrytonServerUnavailable)

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
            except IOError:
                continue
            icon_set = gtk.IconSet(pixbuf)
            self.add(name, icon_set)
            self._locale_icons.add(name)
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
            # svg file cannot be loaded from data into a pixbuf
            fileno, path = tempfile.mkstemp()
            with os.fdopen(fileno, 'w') as svgfile:
                svgfile.write(icon['icon'])
            pixbuf = gtk.gdk.pixbuf_new_from_file(path.decode(
                sys.getfilesystemencoding().encode('utf-8')))
            os.remove(path)
            iconset = gtk.IconSet(pixbuf)
            self.add(icon['name'], iconset)
            self._tryton_icons.remove((icon['id'], icon['name']))
            del self._name2id[icon['name']]
            self._loaded_icons.add(icon['name'])

ICONFACTORY = TrytonIconFactory()
ICONFACTORY.add_default()

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

def test_server_version(host, port):
    version = rpc.server_version(host, port)
    if not version:
        return False
    return version.split('.')[:2] == VERSION.split('.')[:2]

def refresh_dblist(host, port):
    '''
    Return the number of database available
        or None if it is impossible to connect
        or -1 if the server version doesn't match the client version
    '''
    rpc.logout()
    if not test_server_version(host, port):
        return -1
    return rpc.db_list(host, port)

def refresh_langlist(lang_widget, host, port):
    liststore = lang_widget.get_model()
    liststore.clear()
    try:
        lang_list = rpc.db_exec(host, port, 'list_lang')
    except socket.error:
        return []
    from tryton.gui.main import Main
    Main.get_main().refresh_ssl()
    index = -1
    i = 0
    lang = locale.getdefaultlocale()[0]
    for key, val in lang_list:
        liststore.insert(i, (val, key))
        if key == lang:
            index = i
        if key == 'en_US' and index < 0 :
            index = i
        i += 1
    lang_widget.set_active(index)
    return lang_list

def request_server(server_widget):
    result = False
    parent = get_toplevel_window()
    dialog = gtk.Dialog(
        title= _('Tryton Connection'),
        parent=parent,
        flags=gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT |
            gtk.WIN_POS_CENTER_ON_PARENT |
            gtk.gdk.WINDOW_TYPE_HINT_DIALOG,)
    dialog.set_has_separator(True)
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
    table.attach(entry_server, 1, 2, 0, 1,yoptions=False,
        xoptions=gtk.FILL | gtk.EXPAND)
    label_port = gtk.Label(_("Port:"))
    label_port.set_alignment(1, 0.5)
    label_port.set_padding(3, 3)
    table.attach(label_port, 0, 1, 1, 2, yoptions=False,
        xoptions=False)
    dialog.add_button("gtk-cancel", gtk.RESPONSE_CANCEL | gtk.CAN_DEFAULT)
    dialog.add_button("gtk-ok", gtk.RESPONSE_OK)
    dialog.vbox.pack_start(vbox)
    dialog.set_icon(TRYTON_ICON)
    dialog.show_all()
    dialog.set_default_response(gtk.RESPONSE_OK)

    url_m = re.match('^([\w.-]+):(\d{1,5})',
        server_widget.get_text())
    if url_m:
        entry_server.set_text(url_m.group(1))
        entry_port.set_text(url_m.group(2))

    res = dialog.run()
    if res == gtk.RESPONSE_OK:
        host = entry_server.get_text()
        port = int(entry_port.get_text())
        url = '%s:%d' % (host, port)
        server_widget.set_text(url)
        result = (host, port)
    parent.present()
    dialog.destroy()
    return result

def get_toplevel_window():
    windows = [x for x in gtk.window_list_toplevels()
        if x.window and x.props.visible
        and x.props.type == gtk.WINDOW_TOPLEVEL]
    trans2windows = dict((x.get_transient_for(), x) for x in windows)
    for window in set(windows) - set(trans2windows.iterkeys()):
        return window
    return trans2windows[None]

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
    parent_x, parent_y = parent.window.get_origin()
    window_allocation = window.get_allocation()
    sensible_allocation = sensible.get_allocation()
    x = (parent_x + sensible_allocation.x +
        int((sensible_allocation.width - window_allocation.width) / 2))
    y = (parent_y + sensible_allocation.y +
        int((sensible_allocation.height - window_allocation.height) / 2))
    window.move(x, y)

def selection(title, values, alwaysask=False):
    if not values or len(values)==0:
        return None
    elif len(values)==1 and (not alwaysask):
        key = values.keys()[0]
        return (key, values[key])

    parent = get_toplevel_window()
    dialog = gtk.Dialog(_('Selection'), parent,
            gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
            (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                gtk.STOCK_OK, gtk.RESPONSE_OK))
    dialog.set_icon(TRYTON_ICON)
    dialog.set_has_separator(True)
    dialog.set_default_response(gtk.RESPONSE_OK)
    dialog.set_size_request(400, 400)

    label = gtk.Label(title or _('Your selection:'))
    dialog.vbox.pack_start(label, False, False)
    dialog.vbox.pack_start(gtk.HSeparator(), False, True)

    scrolledwindow = gtk.ScrolledWindow()
    scrolledwindow.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
    treeview = gtk.TreeView()
    treeview.set_headers_visible(False)
    scrolledwindow.add(treeview)
    dialog.vbox.pack_start(scrolledwindow, True, True)

    treeview.get_selection().set_mode('single')
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
            gtk.STOCK_OPEN,gtk.RESPONSE_OK)
    else:
        buttons = (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
            gtk.STOCK_SAVE, gtk.RESPONSE_OK)
    win = gtk.FileChooserDialog(title, None, action, buttons)
    win.set_transient_for(parent)
    win.set_icon(TRYTON_ICON)
    win.set_current_folder(CONFIG['client.default_path'])
    if filename:
        win.set_current_name(filename)
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
                pixbuf = gtk.gdk.pixbuf_new_from_file_at_size(filename.decode(
                        sys.getfilesystemencoding().encode('utf-8')), 128, 128)
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
        parent.present()
        win.destroy()
        return False
    if not multi:
        filepath = win.get_filename()
        if filepath:
            filepath = filepath.decode('utf-8')
            try:
                CONFIG['client.default_path'] = \
                        os.path.dirname(filepath)
                CONFIG.save()
            except IOError:
                pass
        parent.present()
        win.destroy()
        return filepath
    else:
        filenames = win.get_filenames()
        if filenames:
            filenames = [x.decode('utf-8') for x in filenames]
            try:
                CONFIG['client.default_path'] = \
                        os.path.dirname(filenames[0])
            except IOError:
                pass
        parent.present()
        win.destroy()
        return filenames

def file_open(filename, type, print_p=False):
    if os.name == 'nt':
        operation = 'open'
        if print_p:
            operation = 'print'
        try:
            os.startfile(os.path.normpath(filename), operation)
        except WindowsError:
            save_name = file_selection(_('Save As...'),
                    action=gtk.FILE_CHOOSER_ACTION_SAVE)
            if save_name:
                file_p = open(filename, 'rb')
                save_p = open(save_name, 'wb+')
                save_p.write(file_p.read())
                save_p.close()
                file_p.close()
        return
    elif sys.platform == 'darwin':
        pid = os.fork()
        if not pid:
            pid = os.fork()
            if not pid:
                try:
                    os.execv('/usr/bin/open', ['/usr/bin/open', filename])
                except OSError:
                    sys.exit(0)
            time.sleep(0.1)
            sys.exit(0)
        os.waitpid(pid, 0)
        return
    cmd = ''
    if isinstance(CONFIG['client.actions'], basestring):
        CONFIG['client.actions'] = safe_eval(CONFIG['client.actions'])
    if type in CONFIG['client.actions']:
        if print_p:
            cmd = CONFIG['client.actions'][type][1]
        else:
            cmd = CONFIG['client.actions'][type][0]
    if not cmd:
        #TODO add dialog box
        pass
    if not cmd:
        save_name = file_selection(_('Save As...'),
                action=gtk.FILE_CHOOSER_ACTION_SAVE)
        if save_name:
            file_p = open(filename, 'rb')
            save_p = open(save_name, 'wb+')
            save_p.write(file_p.read())
            save_p.close()
            file_p.close()
        return
    cmd = cmd % filename
    args = shlex.split(str(cmd))
    prog = find_in_path(args[0])
    args[0] = os.path.basename(args[0])
    if print_p:
        os.spawnv(os.P_WAIT, prog, args)
        return
    pid = os.fork()
    if not pid:
        pid = os.fork()
        if not pid:
            try:
                os.execv(prog, args)
            except OSError:
                sys.exit(0)
        time.sleep(0.1)
        sys.exit(0)
    os.waitpid(pid, 0)

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
        prog = find_in_path(args[0])
        args[0] = os.path.basename(args[0])
        if os.name == 'nt':
            os.spawnv(os.P_NOWAIT, prog, args)
            return
        pid = os.fork()
        if not pid:
            pid = os.fork()
            if not pid:
                try:
                    os.execv(prog, args)
                except OSError:
                    sys.exit(0)
            time.sleep(0.1)
            sys.exit(0)
        os.waitpid(pid, 0)
        return
    #http://www.faqs.org/rfcs/rfc2368.html
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
            gtk.DIALOG_MODAL|gtk.DIALOG_DESTROY_WITH_PARENT, msg_type,
            gtk.BUTTONS_OK, message)
        return dialog

    def __call__(self, message, msg_type=gtk.MESSAGE_INFO):
        super(MessageDialog, self).__call__(message, msg_type)

message = MessageDialog()


class WarningDialog(UniqueDialog):

    def build_dialog(self, parent, message, title, buttons=gtk.BUTTONS_OK):
        dialog = gtk.MessageDialog(parent, gtk.DIALOG_DESTROY_WITH_PARENT,
            gtk.MESSAGE_WARNING, buttons)
        if hasattr(dialog, 'format_secondary_markup'):
            dialog.set_markup('<b>%s</b>' % (to_xml(title)))
            dialog.format_secondary_markup(to_xml(message))
        else:
            dialog.set_markup('<b>%s</b>\n%s' % (to_xml(title), to_xml(message)))
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
            title, gtk.BUTTONS_OK_CANCEL)
        check = gtk.CheckButton(_('Always ignore this warning.'))
        check.connect_after('toggled', self._set_always)
        alignment = gtk.Alignment(1, 0.5)
        alignment.add(check)
        dialog.vbox.pack_end(alignment, True, False)
        return dialog

    def __call__(self, message, title):
        response = super(UserWarningDialog, self).__call__(message, title)
        if response == gtk.RESPONSE_OK:
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
        dialog.set_has_separator(True)
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
        dialog.add_button("gtk-ok", gtk.RESPONSE_OK | gtk.CAN_DEFAULT
                | gtk.HAS_DEFAULT)
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
        dialog.add_button("gtk-yes", gtk.RESPONSE_YES | gtk.CAN_DEFAULT
                | gtk.HAS_DEFAULT)
        dialog.set_default_response(gtk.RESPONSE_YES)
        return dialog

    def __call__(self, message):
        response = super(Sur3BDialog, self).__call__(message)
        return self.response_mapping.get(response, 'cancel')

sur_3b = Sur3BDialog()


class AskDialog(UniqueDialog):

    def build_dialog(self, parent, question, visibility):
        win = gtk.Dialog('Tryton', parent,
                gtk.DIALOG_MODAL|gtk.DIALOG_DESTROY_WITH_PARENT,
                (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                    gtk.STOCK_OK, gtk.RESPONSE_OK))
        win.set_has_separator(True)
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
        dialog = gtk.Dialog(_('Concurrency Exception'), parent, gtk.DIALOG_MODAL
                | gtk.DIALOG_DESTROY_WITH_PARENT | gtk.WIN_POS_CENTER_ON_PARENT
                | gtk.gdk.WINDOW_TYPE_HINT_DIALOG)
        dialog.set_has_separator(True)
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
            Window.create(False, resource, res_id=obj_id,
                domain=[('id', '=', obj_id)],
                context=context, mode=['form', 'tree'])
        return False

concurrency = ConcurrencyDialog()


class ErrorDialog(UniqueDialog):

    def build_dialog(self, parent, title, details):
        dialog = gtk.Dialog(_('Error'), parent,
            gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT)
        dialog.set_has_separator(True)

        but_send = gtk.Button(_('Report Bug'))
        dialog.add_action_widget(but_send, gtk.RESPONSE_OK)
        dialog.add_button("gtk-close", gtk.RESPONSE_CANCEL)
        dialog.set_default_response(gtk.RESPONSE_CANCEL)

        vbox = gtk.VBox()
        label_title = gtk.Label()
        label_title.set_markup('<b>' + _('Application Error!') + '</b>')
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
        dialog.set_size_request(600, 400)
        return dialog

    def __call__(self, title, details):
        if title == details:
            title = ''
        log = logging.getLogger('common.message')
        log.error(details)

        response = super(ErrorDialog, self).__call__(title, details)
        if response == gtk.RESPONSE_OK:
            send_bugtracker(details)

error = ErrorDialog()

def send_bugtracker(msg):
    from tryton import rpc
    parent = get_toplevel_window()
    win = gtk.Dialog(_('Bug Tracker'), parent,
            gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
            (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                gtk.STOCK_OK, gtk.RESPONSE_OK))
    win.set_icon(TRYTON_ICON)
    win.set_default_response(gtk.RESPONSE_OK)
    win.set_has_separator(True)

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
            server = xmlrpclib.Server(('%s://%s:%s@' + CONFIG['roundup.xmlrpc'])
                    % (protocol, user, password), allow_none=True)
            if hashlib:
                msg_md5 = hashlib.md5(msg).hexdigest()
            else:
                msg_md5 = md5.new(msg).hexdigest()
            # use the last line of the message as title
            title = '[no title]'
            for line in msg.splitlines():
                #don't use empty line nor ^ from sql error
                if line and '^' != line.strip():
                    if len(line) > 128:
                        title = line[:128] + '...'
                    else:
                        title = line
            issue_id = None
            msg_ids = server.filter('msg', None, {'summary': str(msg_md5)})
            if msg_ids:
                issue_ids = server.filter('issue', None, {'messages': msg_ids})
                if issue_ids:
                    issue_id = issue_ids[0]
            if issue_id:
                # issue to same message already exists, add user to nosy-list
                server.set('issue' + str(issue_id), *['nosy=+' + user])
                message(_('The same bug was already reported by another user.\n' \
                        'To keep you informed your username is added to the nosy-list of this issue') + \
                        '%s' % issue_id)
            else:
                # create a new issue for this error-message
                # first create message
                msg_id = server.create('msg', *['content=' + msg,
                    'author=' + user, 'summary=' + msg_md5])
                # second create issue with this message
                issue_id = server.create('issue', *['messages=' + str(msg_id),
                    'nosy=' + user, 'title=' + title, 'priority=bug'])
                message(_('Created new bug with ID ') + \
                        'issue%s' % issue_id)
            webbrowser.open(CONFIG['roundup.url'] + 'issue%s' % issue_id, new=2)
        except (socket.error, xmlrpclib.Fault), exception:
            if (isinstance(exception, xmlrpclib.Fault)
                    and 'roundup.cgi.exceptions.Unauthorised' in
                    exception.faultString):
                message(_('Connection error!\nBad username or password!'))
                return send_bugtracker(msg)
            tb_s = reduce(lambda x, y: x + y,
                    traceback.format_exception(sys.exc_type,
                        sys.exc_value, sys.exc_traceback))
            message(_('Exception:') + '\n' + tb_s, msg_type=gtk.MESSAGE_ERROR)

def to_xml(string):
    return string.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')

PLOCK = Lock()

def process_exception(exception, *args, **kwargs):

    if isinstance(exception, TrytonError):
        if exception.faultCode == 'BadFingerprint':
            warning(
                _('The server fingerprint has changed since last connection!\n'
                'The application will stop connecting to this server '
                'until its fingerprint is fixed.'), _('Security risk!'))
            from tryton.gui.main import Main
            Main.sig_quit()
            sys.exit()
        elif exception.faultCode == 'NotLogged':
            if rpc.CONNECTION is None:
                message(_('Connection error!\n' \
                        'Unable to connect to the server!'))
                return False
    elif isinstance(exception, TrytonServerError):
        if exception.faultCode == 'UserWarning':
            name, msg, description = exception.args
            res = userwarning(description, msg)
            if res in ('always', 'ok'):
                args2 = ('model', 'res.user.warning', 'create', {
                        'user': rpc._USER,
                        'name': name,
                        'always': (res == 'always'),
                        }, rpc.CONTEXT)
                try:
                    rpc.execute(*args2)
                except TrytonServerError, exception:
                    process_exception(exception, *args2)
                if args:
                    try:
                        return rpc.execute(*args)
                    except TrytonServerError, exception:
                        return process_exception(exception, *args)
                return True
            return False
        elif exception.faultCode == 'UserError':
            msg, description = exception.args
            warning(description, msg)
            return False
        elif exception.faultCode == 'ConcurrencyException':
            if len(args) >= 6:
                if concurrency(args[1], args[3][0], args[5]):
                    if '_timestamp' in args[5]:
                        del args[5]['_timestamp']
                    try:
                        return rpc.execute(*args)
                    except TrytonServerError, exception:
                        return process_exception(exception, *args)
                return False
            else:
                message(_('Concurrency Exception'), msg_type=gtk.MESSAGE_ERROR)
                return False
        elif exception.faultCode == 'NotLogged':
            from tryton.gui.main import Main
            if not PLOCK.acquire(False):
                return False
            hostname = rpc._HOST
            port = rpc._PORT
            try:
                while True:
                    password = ask(_('Password:'), visibility=False)
                    if password is None:
                        Main.get_main().sig_logout()
                        raise TrytonError('NotLogged')
                    res = rpc.login(rpc._USERNAME, password, hostname, port,
                            rpc._DATABASE)
                    Main.get_main().refresh_ssl()
                    if res == -1:
                        message(_('Connection error!\n' \
                                'Unable to connect to the server!'))
                        return False
                    if res < 0:
                        continue
                    if args:
                        try:
                            return rpc.execute(*args)
                        except TrytonServerError, exception:
                            return process_exception(exception, *args)
                    return True
            finally:
                PLOCK.release()
    elif isinstance(exception, (socket.error, TrytonServerUnavailable)):
        warning(str(exception), _('Network Error!'))
        return False

    if isinstance(exception, TrytonServerError):
        error_title, error_detail = exception.faultCode, exception.faultString
    else:
        error_title = str(exception)
        if 'tb' in kwargs:
            error_detail = kwargs['tb']
        else:
            error_detail = traceback.format_exc()
    error(error_title, error_detail)
    return False

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
    r = int(hexstring[1:digits+1], 16)
    g = int(hexstring[digits+1:digits*2+1], 16)
    b = int(hexstring[digits*2+1:digits*3+1], 16)
    return r / top, g / top, b / top

def clamp(minValue, maxValue, value):
    """Make sure value is between minValue and maxValue"""
    if value < minValue:
                return minValue
    if value > maxValue:
                return maxValue
    return value

def lighten(r, g, b, amount):
    """Return a lighter version of the color (r, g, b)"""
    return (clamp(0.0, 1.0, r + amount),
            clamp(0.0, 1.0, g + amount),
            clamp(0.0, 1.0, b + amount))

def generateColorscheme(masterColor, keys, light=0.06):
    """
    Generates a dictionary where the keys match the keys argument and
    the values are colors derivated from the masterColor.
    Each color is a lighter version of masterColor separated by a difference
    given by the light argument.
    The masterColor is given in a hex string format.
    """
    r, g, b = hex2rgb(COLOR_SCHEMES.get(masterColor, masterColor))
    return dict([(key, lighten(r, g, b, light * i))
        for i, key in enumerate(keys)])


class DBProgress(object):

    def __init__(self, host, port):
        self.dbs, self.createdb = None, None
        self.host, self.port = host, port
        self.updated = threading.Event()
        self.db_info = None

    def start(self):
        dbs, createdb = None, False
        try:
            dbs = refresh_dblist(self.host, self.port)
            createdb = True
        except Exception:
            pass
        finally:
            self.db_info = (dbs, createdb)
            self.updated.set()

    def update(self, combo, progressbar, callback, dbname=''):
        self.db_info = None
        thread = threading.Thread(target=self.start).start()
        gobject.timeout_add(100, self.end, combo, progressbar, callback,
            dbname)

    def end(self, combo, progressbar, callback, dbname):
        if not self.updated.isSet():
            progressbar.show()
            progressbar.pulse()
            return True
        progressbar.hide()
        dbs, createdb = self.db_info

        if dbs is None:
            dbs, createdb = None, False
        elif dbs == -1:
            dbs, createdb = -1, False
        else:
            from tryton.gui.main import Main
            Main.get_main().refresh_ssl()
            liststore = combo.get_model()
            liststore.clear()
            index = -1
            for db_num, db_name in enumerate(dbs):
                liststore.append([db_name])
                if db_name == dbname:
                    index = db_num
            if index == -1:
                index = 0
            combo.set_active(index)
            dbs = len(dbs)

        callback(dbs, createdb)
        return False


class RPCProgress(object):

    def __init__(self, method, args):
        self.method = method
        self.args = args
        self.parent = get_toplevel_window()
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
            return True
        if not self.res:
            self.error = True
        return True

    def run(self):
        thread.start_new_thread(self.start, ())

        watch = gtk.gdk.Cursor(gtk.gdk.WATCH)
        self.parent.window.set_cursor(watch)
        parent_sensitive = self.parent.props.sensitive
        self.parent.props.sensitive = False
        i = 0
        win = None
        progressbar = None
        while (not self.res) and (not self.error):
            i += 1
            if i > 10:
                if not win or not progressbar:
                    win = gtk.Window(type=gtk.WINDOW_TOPLEVEL)
                    win.set_position(gtk.WIN_POS_CENTER_ON_PARENT)
                    if hasattr(win, 'set_deletable'):
                        win.set_deletable(False)
                    win.set_decorated(False)
                    vbox = gtk.VBox(False, 0)
                    hbox = gtk.HBox(False, 13)
                    hbox.set_border_width(10)
                    img = gtk.Image()
                    img.set_from_stock('tryton-dialog-information',
                            gtk.ICON_SIZE_DIALOG)
                    hbox.pack_start(img, expand=True, fill=False)
                    vbox2 = gtk.VBox(False, 0)
                    label = gtk.Label()
                    label.set_markup('<b>'+_('Operation in progress')+'</b>')
                    label.set_alignment(0.0, 0.5)
                    vbox2.pack_start(label, expand=True, fill=False)
                    vbox2.pack_start(gtk.HSeparator(), expand=True, fill=True)
                    vbox2.pack_start(gtk.Label(_("Please wait,\n" \
                            "this operation may take a while...")),
                            expand=True, fill=False)
                    hbox.pack_start(vbox2, expand=True, fill=True)
                    vbox.pack_start(hbox)
                    progressbar = gtk.ProgressBar()
                    progressbar.set_orientation(gtk.PROGRESS_LEFT_TO_RIGHT)
                    vbox.pack_start(progressbar, expand=True, fill=False)
                    viewport = gtk.Viewport()
                    viewport.set_shadow_type(gtk.SHADOW_ETCHED_IN)
                    viewport.add(vbox)
                    win.add(viewport)
                    win.set_transient_for(self.parent)
                    win.set_modal(True)
                    win.show_all()
                    win.window.set_cursor(watch)
                with gtk.gdk.lock:
                    progressbar.pulse()
            if win:
                with gtk.gdk.lock:
                    while gtk.events_pending():
                        gtk.main_iteration()
            time.sleep(0.1)
        self.parent.props.sensitive = parent_sensitive
        self.parent.window.set_cursor(None)
        if win:
            win.destroy()
            while gtk.events_pending():
                gtk.main_iteration()
        if self.exception:
            raise self.exception
        return self.res


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

COLORS = {
    'invalid':'#ff6969',
    'required':'#d2d2ff',
}

DT_FORMAT = '%Y-%m-%d'
HM_FORMAT = '%H:%M:%S'
DHM_FORMAT = DT_FORMAT + ' ' + HM_FORMAT

FLOAT_TIME_CONV = {
    'Y': 8760,
    'M': 672,
    'w': 168,
    'd': 24,
    'h': 1,
    'm': 1.0/60,
}

FLOAT_TIME_SEPS = {
    'Y': _('Y'),
    'M': _('M'),
    'w': _('w'),
    'd': _('d'),
    'h': _('h'),
    'm': _('m'),
}

def text_to_float_time(text, conv=None):
    try:
        try:
            return locale.atof(text)
        except ValueError:
            pass
        if conv:
            tmp_conv = FLOAT_TIME_CONV.copy()
            tmp_conv.update(conv)
            conv = tmp_conv
        else:
            conv = FLOAT_TIME_CONV
        for key in FLOAT_TIME_SEPS.keys():
            text = text.replace(FLOAT_TIME_SEPS[key], key + ' ')
        value = 0
        for buf in text.split(' '):
            buf = buf.strip()
            if ':' in buf:
                hour, min = buf.split(':')
                value += abs(int(hour or 0))
                value += abs(int(min or 0) * conv['m'])
                continue
            elif '-' in buf and not buf.startswith('-'):
                hour, min = buf.split('-')
                value += abs(int(hour or 0))
                value += abs(int(min or 0) * conv['m'])
                continue
            try:
                value += abs(locale.atof(buf))
                continue
            except ValueError:
                pass
            for sep in conv.keys():
                if buf.endswith(sep):
                    value += abs(locale.atof(buf[:-len(sep)])) * conv[sep]
                    break
        if text.startswith('-'):
            value *= -1
        return value
    except ValueError:
        return 0.0

def float_time_to_text(val, conv=None):
    if conv:
        tmp_conv = FLOAT_TIME_CONV.copy()
        tmp_conv.update(conv)
        conv = tmp_conv
    else:
        conv = FLOAT_TIME_CONV

    value = ''
    if val < 0:
        value += '-'
    val = abs(val)
    years = int(val / conv['Y'])
    val = val - years * conv['Y']
    months = int(val / conv['M'])
    val = val - months * conv['M']
    weeks = int(val / conv['w'])
    val = val - weeks * conv['w']
    days = int(val / conv['d'])
    val = val - days * conv['d']
    hours = int(val)
    val = val - hours
    mins = int((val% 1 + 0.01) / conv['m'])
    if years:
        value += ' ' + locale.format('%d', years, True) + FLOAT_TIME_SEPS['Y']
    if months:
        value += ' ' + locale.format('%d', months, True) + FLOAT_TIME_SEPS['M']
    if weeks:
        value += ' ' + locale.format('%d', weeks, True) + FLOAT_TIME_SEPS['w']
    if days:
        value += ' ' + locale.format('%d', days, True) + FLOAT_TIME_SEPS['d']
    if hours or mins:
        value += ' %02d:%02d' % (hours, mins)
    value = value.strip()
    return value

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

_ALLOWED_CODES = set(dis.opmap[x] for x in [
    'POP_TOP','ROT_TWO','ROT_THREE','ROT_FOUR','DUP_TOP',
    'BUILD_LIST','BUILD_MAP','BUILD_TUPLE',
    'LOAD_CONST','RETURN_VALUE','STORE_SUBSCR',
    'UNARY_POSITIVE','UNARY_NEGATIVE','UNARY_NOT',
    'UNARY_INVERT','BINARY_POWER','BINARY_MULTIPLY',
    'BINARY_DIVIDE','BINARY_FLOOR_DIVIDE','BINARY_TRUE_DIVIDE',
    'BINARY_MODULO','BINARY_ADD','BINARY_SUBTRACT',
    'BINARY_LSHIFT','BINARY_RSHIFT','BINARY_AND','BINARY_XOR', 'BINARY_OR',
    'STORE_MAP', 'LOAD_NAME', 'CALL_FUNCTION', 'COMPARE_OP', 'LOAD_ATTR',
    'STORE_NAME', 'GET_ITER', 'FOR_ITER', 'LIST_APPEND', 'JUMP_ABSOLUTE',
    'DELETE_NAME', 'JUMP_IF_TRUE', 'JUMP_IF_FALSE', 'JUMP_IF_FALSE_OR_POP',
    'JUMP_IF_TRUE_OR_POP', 'POP_JUMP_IF_FALSE', 'POP_JUMP_IF_TRUE',
    'BINARY_SUBSCR',
    ] if x in dis.opmap)

_SAFE_EVAL_CACHE = {}

def safe_eval(source, data=None):
    if '__subclasses__' in source:
        raise ValueError('__subclasses__ not allowed')
    if hashlib:
        key = hashlib.md5(source).digest()
    else:
        key = md5.new(source).digest()
    c = _SAFE_EVAL_CACHE.get(key)
    if not c:
        c = compile(source, '', 'eval')
        codes = []
        s = c.co_code
        i = 0
        while i < len(s):
            code = ord(s[i])
            codes.append(code)
            if code >= dis.HAVE_ARGUMENT:
                i += 3
            else:
                i += 1
        for code in codes:
            if code not in _ALLOWED_CODES:
                raise ValueError('opcode %s not allowed' % dis.opname[code])
        if len(_SAFE_EVAL_CACHE) > 1024:
            _SAFE_EVAL_CACHE.clear()
        _SAFE_EVAL_CACHE[key] = c
    return eval(c, {'__builtins__': {
        'True': True,
        'False': False,
        'str': str,
        'globals': locals,
        'locals': locals,
        'bool': bool,
        'dict': dict,
        }}, data)

def timezoned_date(date, reverse=False):
    if pytz and rpc.CONTEXT.get('timezone') and rpc.TIMEZONE:
        lzone = pytz.timezone(rpc.CONTEXT['timezone'])
        szone = pytz.timezone(rpc.TIMEZONE)
        if reverse:
            lzone, szone = szone, lzone
        sdt = szone.localize(date, is_dst=True)
        ldt = sdt.astimezone(lzone)
        date = ldt
    return date


def untimezoned_date(date):
    return timezoned_date(date, reverse=True).replace(tzinfo=None)
