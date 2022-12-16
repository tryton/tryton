#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import gtk
import gobject
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
import tryton.rpc as rpc
import locale
import socket
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

_ = gettext.gettext

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

def refresh_dblist(db_widget, host, port, dbtoload=None):
    '''
    Return the number of database available
        or None if it is impossible to connect
        or -1 if the server version doesn't match the client version
    '''
    rpc.logout()
    version = rpc.server_version(host, port)
    if hasattr(version, 'split'):
        if version.split('.')[:2] != VERSION.split('.')[:2]:
            return -1
    if not dbtoload:
        dbtoload = CONFIG['login.db']
    index = 0
    liststore = db_widget.get_model()
    liststore.clear()
    result = rpc.db_list(host, port)
    from tryton.gui.main import Main
    Main.get_main().refresh_ssl()
    if result is None:
        return None
    for db_num, dbname in enumerate(result):
        liststore.append([dbname])
        if dbname == dbtoload:
            index = db_num
    db_widget.set_active(index)
    return len(liststore)

def refresh_langlist(lang_widget, host, port):
    liststore = lang_widget.get_model()
    liststore.clear()
    lang_list = rpc.db_exec(host, port, 'list_lang')
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

def request_server(server_widget, parent):
    result = False
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
    entry_port.set_text("8070")
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


def selection(title, values, parent, alwaysask=False):
    if not values or len(values)==0:
        return None
    elif len(values)==1 and (not alwaysask):
        key = values.keys()[0]
        return (key, values[key])

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

def file_selection(title, filename='', parent=None,
        action=gtk.FILE_CHOOSER_ACTION_OPEN, preview=True, multi=False,
        filters=None):
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
        filename = win.get_preview_filename()
        try:
            pixbuf = gtk.gdk.pixbuf_new_from_file_at_size(filename.encode('utf-8'),
                    128, 128)
            img.set_from_pixbuf(pixbuf)
            have_preview = True
        except:
            have_preview = False
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
            except:
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
            except:
                pass
        parent.present()
        win.destroy()
        return filenames

def file_open(filename, type, parent, print_p=False):
    if os.name == 'nt':
        operation = 'open'
        if print_p:
            operation = 'print'
        try:
            os.startfile(os.path.normpath(filename), operation)
        except:
            # Try without operation, it is not supported on version < 2.5
            try:
                os.startfile(os.path.normpath(filename))
            except:
                save_name = file_selection(_('Save As...'), parent=parent,
                        action=gtk.FILE_CHOOSER_ACTION_SAVE)
                if save_name:
                    file_p = file(filename, 'rb')
                    save_p = file(save_name, 'wb+')
                    save_p.write(file_p.read())
                    save_p.close()
                    file_p.close()
        return
    elif os.name == 'mac' or \
            (hasattr(os, 'uname') and os.uname()[0] == 'Darwin'):
        pid = os.fork()
        if not pid:
            pid = os.fork()
            if not pid:
                try:
                    os.execv('/usr/bin/open', ['/usr/bin/open', filename])
                except:
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
        save_name = file_selection(_('Save As...'), parent=parent,
                action=gtk.FILE_CHOOSER_ACTION_SAVE)
        if save_name:
            file_p = file(filename, 'rb')
            save_p = file(save_name, 'wb+')
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
            except:
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
                except:
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

def error(title, parent, details):
    log = logging.getLogger('common.message')
    log.error('%s' % details)

    if title == details:
        title = ''

    dialog = gtk.Dialog(_('Error'), parent,
            gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT)
    dialog.set_icon(TRYTON_ICON)
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
    label_error.set_markup('<b>' + _('Error: ') + '</b>' + title)
    label_error.set_alignment(0, 0.5)
    label_error.set_padding(-1, 14)
    box.pack_start(label_error, False, False)
    textview = gtk.TextView()
    buf = gtk.TextBuffer()
    buf.set_text(details)
    textview.set_buffer(buf)
    textview.set_editable(False)
    textview.set_sensitive(True)
    box.pack_start(textview, False, False)

    viewport.add(box)
    scrolledwindow.add(viewport)
    hbox.pack_start(scrolledwindow)

    vbox.pack_start(hbox)

    button_roundup = gtk.Button()
    button_roundup.set_relief(gtk.RELIEF_NONE)
    label_roundup = gtk.Label()
    label_roundup.set_markup(_('To report bugs you must have an account on ') \
            + '<u>' + CONFIG['roundup.url'] + '</u>')
    label_roundup.set_alignment(1, 0.5)
    label_roundup.set_padding(20, 5)

    button_roundup.connect('clicked',
            lambda widget: webbrowser.open(CONFIG['roundup.url'], new=2))
    button_roundup.add(label_roundup)
    vbox.pack_start(button_roundup, False, False)

    dialog.vbox.pack_start(vbox)
    dialog.set_size_request(600, 400)

    dialog.show_all()
    response = dialog.run()
    parent.present()
    dialog.destroy()
    if response == gtk.RESPONSE_OK:
        send_bugtracker(details, parent)
    return True

def send_bugtracker(msg, parent):
    from tryton import rpc
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
                        '%s' % issue_id, parent)
            else:
                # create a new issue for this error-message
                # first create message
                msg_id = server.create('msg', *['content=' + msg,
                    'author=' + user, 'summary=' + msg_md5])
                # second create issue with this message
                issue_id = server.create('issue', *['messages=' + str(msg_id),
                    'nosy=' + user, 'title=' + title, 'priority=bug'])
                message(_('Created new bug with ID ') + \
                        'issue%s' % issue_id, parent)
            webbrowser.open(CONFIG['roundup.url'] + 'issue%s' % issue_id, new=2)
        except Exception, exception:
            if hasattr(exception, 'faultString') \
                    and 'roundup.cgi.exceptions.Unauthorised' in exception.faultString:
                message(_('Connection error!\n' \
                        'Bad username or password!'), parent)
                return send_bugtracker(msg, parent)
            tb_s = reduce(lambda x, y: x + y,
                    traceback.format_exception(sys.exc_type,
                        sys.exc_value, sys.exc_traceback))
            message(_('Exception:') + '\n' + tb_s, parent,
                    msg_type=gtk.MESSAGE_ERROR)

def message(msg, parent, msg_type=gtk.MESSAGE_INFO):
    dialog = gtk.MessageDialog(parent,
      gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
      msg_type, gtk.BUTTONS_OK,
      msg)
    dialog.set_icon(TRYTON_ICON)
    dialog.run()
    parent.present()
    dialog.destroy()
    return True

def to_xml(string):
    return string.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')

def warning(msg, parent, title=''):
    dialog = gtk.MessageDialog(parent, gtk.DIALOG_DESTROY_WITH_PARENT,
            gtk.MESSAGE_WARNING, gtk.BUTTONS_OK)
    dialog.set_icon(TRYTON_ICON)
    # format_secondary_markup available in PyGTK 2.6 and above.
    if hasattr(dialog, 'format_secondary_markup'):
        dialog.set_markup('<b>%s</b>' % (to_xml(title)))
        dialog.format_secondary_markup(to_xml(msg))
    else:
        dialog.set_markup('<b>%s</b>\n%s' % (to_xml(title), to_xml(msg)))
    dialog.show_all()
    dialog.run()
    parent.present()
    dialog.destroy()
    return True

def userwarning(msg, parent, title=''):
    dialog = gtk.MessageDialog(parent, gtk.DIALOG_DESTROY_WITH_PARENT,
            gtk.MESSAGE_WARNING, gtk.BUTTONS_OK_CANCEL)
    dialog.set_icon(TRYTON_ICON)
    # format_secondary_markup available in PyGTK 2.6 and above.
    if hasattr(dialog, 'format_secondary_markup'):
        dialog.set_markup('<b>%s</b>' % (to_xml(title)))
        dialog.format_secondary_markup(to_xml(msg))
    else:
        dialog.set_markup('<b>%s</b>\n%s' % (to_xml(title), to_xml(msg)))
    check = gtk.CheckButton(_('Always ignore this warning.'))
    alignment = gtk.Alignment(1, 0.5)
    alignment.add(check)
    dialog.vbox.pack_end(alignment, True, False)
    dialog.show_all()
    response = dialog.run()
    parent.present()
    always = check.get_active()
    dialog.destroy()
    if response == gtk.RESPONSE_OK:
        if always:
            return 'always'
        return 'ok'
    return 'cancel'

def sur(msg, parent):
    dialog = gtk.Dialog(_('Confirmation'), parent, gtk.DIALOG_MODAL
            | gtk.DIALOG_DESTROY_WITH_PARENT | gtk.WIN_POS_CENTER_ON_PARENT
            | gtk.gdk.WINDOW_TYPE_HINT_DIALOG)
    dialog.set_icon(TRYTON_ICON)
    dialog.set_has_separator(True)
    hbox = gtk.HBox()
    image = gtk.Image()
    image.set_from_stock('tryton-dialog-information',
            gtk.ICON_SIZE_DIALOG)
    image.set_padding(15, 15)
    hbox.pack_start(image, False, False)
    label = gtk.Label('%s' % (to_xml(msg)))
    hbox.pack_start(label, True, True)
    dialog.vbox.pack_start(hbox)
    dialog.add_button("gtk-cancel", gtk.RESPONSE_CANCEL)
    dialog.add_button("gtk-ok", gtk.RESPONSE_OK | gtk.CAN_DEFAULT
            | gtk.HAS_DEFAULT)
    dialog.set_default_response(gtk.RESPONSE_OK)
    dialog.set_transient_for(parent)
    dialog.show_all()
    response = dialog.run()
    parent.present()
    dialog.destroy()
    return response == gtk.RESPONSE_OK

def sur_3b(msg, parent):
    dialog = gtk.Dialog(_('Confirmation'), parent, gtk.DIALOG_MODAL
            | gtk.DIALOG_DESTROY_WITH_PARENT | gtk.WIN_POS_CENTER_ON_PARENT
            | gtk.gdk.WINDOW_TYPE_HINT_DIALOG)
    dialog.set_icon(TRYTON_ICON)
    dialog.set_has_separator(True)
    hbox = gtk.HBox()
    image = gtk.Image()
    image.set_from_stock('tryton-dialog-information',
            gtk.ICON_SIZE_DIALOG)
    image.set_padding(15, 15)
    hbox.pack_start(image, False, False)
    label = gtk.Label('%s' % (to_xml(msg)))
    hbox.pack_start(label, True, True)
    dialog.vbox.pack_start(hbox)
    dialog.add_button("gtk-cancel", gtk.RESPONSE_CANCEL)
    dialog.add_button("gtk-no", gtk.RESPONSE_NO)
    dialog.add_button("gtk-yes", gtk.RESPONSE_YES | gtk.CAN_DEFAULT
            | gtk.HAS_DEFAULT)
    dialog.set_default_response(gtk.RESPONSE_YES)
    dialog.set_transient_for(parent)
    dialog.show_all()

    response = dialog.run()
    parent.present()
    dialog.destroy()
    if response == gtk.RESPONSE_YES:
        return 'ok'
    elif response == gtk.RESPONSE_NO:
        return 'ko'
    elif response == gtk.RESPONSE_CANCEL:
        return 'cancel'
    else:
        return 'cancel'

def ask(question, parent, visibility=True):
    win = gtk.Dialog('Tryton', parent,
            gtk.DIALOG_MODAL|gtk.DIALOG_DESTROY_WITH_PARENT,
            (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                gtk.STOCK_OK, gtk.RESPONSE_OK))
    win.set_icon(TRYTON_ICON)
    win.set_has_separator(True)
    win.set_default_response(gtk.RESPONSE_OK)

    hbox = gtk.HBox()
    image = gtk.Image()
    image.set_from_stock('tryton-dialog-information',
            gtk.ICON_SIZE_DIALOG)
    hbox.pack_start(image)
    vbox = gtk.VBox()
    vbox.pack_start(gtk.Label(question))
    entry = gtk.Entry()
    entry.set_activates_default(True)
    entry.set_visibility(visibility)
    vbox.pack_start(entry)
    hbox.pack_start(vbox)
    win.vbox.pack_start(hbox)
    win.show_all()

    response = win.run()
    parent.present()
    res = entry.get_text()
    win.destroy()
    if response == gtk.RESPONSE_OK:
        return res
    else:
        return None

def concurrency(resource, obj_id, context, parent):
    dialog = gtk.Dialog(_('Concurrency Exception'), parent, gtk.DIALOG_MODAL
            | gtk.DIALOG_DESTROY_WITH_PARENT | gtk.WIN_POS_CENTER_ON_PARENT
            | gtk.gdk.WINDOW_TYPE_HINT_DIALOG)
    dialog.set_icon(TRYTON_ICON)
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
    label.set_markup(_('''<b>Write Concurrency Warning:</b>

This record has been modified while you were editing it.
  Choose:
   - "Cancel" to cancel saving;
   - "Compare" to see the modified version;
   - "Write Anyway" to save your current version.'''))
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
    dialog.show_all()

    res = dialog.run()
    parent.present()
    dialog.destroy()

    if res == gtk.RESPONSE_OK:
        return True
    if res == gtk.RESPONSE_APPLY:
        from tryton.gui.window import Window
        Window.create(False, resource, obj_id, [('id', '=', obj_id)], 'form',
                parent, context, ['form', 'tree'])
    return False

def process_exception(exception, parent, *args):
    global _USERNAME, _DATABASE, _SOCK
    if str(exception.args[0]) == 'NotLogged':
        if not rpc._SOCK:
            message(_('Connection error!\n' \
                    'Unable to connect to the server!'), parent)
            return False
        host = rpc._SOCK.host
        port = rpc._SOCK.port
        while True:
            password = ask(_('Password:'), parent, visibility=False)
            if password is None:
                raise Exception('NotLogged')
            res = rpc.login(rpc._USERNAME, password, host, port, rpc._DATABASE)
            from tryton.gui.main import Main
            Main.get_main().refresh_ssl()
            if res == -1:
                message(_('Connection error!\n' \
                        'Unable to connect to the server!'), parent)
                return False
            if res < 0:
                continue
            if args:
                try:
                    return rpc.execute(*args)
                except Exception, exception:
                    return process_exception(exception, parent, *args)
            return True

    if exception.args[0] == 'ConcurrencyException':
        if len(args) >= 6:
            if concurrency(args[1], args[3][0], args[5], parent):
                if '_timestamp' in args[5]:
                    del args[5]['_timestamp']
                try:
                    return rpc.execute(*args)
                except Exception, exception:
                    return process_exception(exception, parent, *args)
            return False
        else:
            message(_('Concurrency Exception'), parent,
                    msg_type=gtk.MESSAGE_ERROR)
            return False

    if exception.args[0] == 'UserWarning':
        msg = ''
        if len(exception.args) > 4:
            msg = exception.args[3]
        res = userwarning(str(msg), parent, str(exception.args[2]))
        if res in ('always', 'ok'):
            args2 = ('model', 'res.user.warning', 'create', {
                    'user': rpc._USER,
                    'name': exception.args[1],
                    'always': (res == 'always'),
                    }, rpc.CONTEXT)
            try:
                rpc.execute(*args2)
            except Exception, exception:
                process_exception(exception, parent, *args2)
            if args:
                try:
                    return rpc.execute(*args)
                except Exception, exception:
                    return process_exception(exception, parent, *args)
            return True
        return False

    if exception.args[0] == 'UserError':
        msg = ''
        if len(exception.args) > 3:
            msg = exception.args[2]
        warning(str(msg), parent, str(exception.args[1]))
        return False

    if isinstance(exception, socket.error):
        msg = ''
        if len(exception.args) > 2:
            msg = exception.args[1]
        warning(msg, parent, _('Network Error!'))
        return False

    error(str(exception.args[0]), parent, str(exception.args[-1]))
    return False

def node_attributes(node):
    result = {}
    attrs = node.attributes
    if attrs is None:
        return {}
    for i in range(attrs.length):
        result[str(attrs.item(i).localName)] = str(attrs.item(i).nodeValue)
        if attrs.item(i).localName == "digits" \
                and isinstance(attrs.item(i).nodeValue, basestring):
            result[attrs.item(i).localName] = eval(attrs.item(i).nodeValue)
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


class RPCProgress(object):

    def __init__(self, method, args, parent):
        self.method = method
        self.args = args
        self.parent = parent
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

        i = 0
        win = None
        progressbar = None
        while (not self.res) and (not self.error):
            time.sleep(0.1)
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
                progressbar.pulse()
                while gtk.events_pending():
                    gtk.main_iteration()
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
        except:
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
            except:
                pass
            for sep in conv.keys():
                if buf.endswith(sep):
                    value += abs(locale.atof(buf[:-len(sep)])) * conv[sep]
                    break
        if text.startswith('-'):
            value *= -1
        return value
    except:
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


def safe_eval(source, data=None):
    if '__subclasses__' in source:
        raise ValueError('__subclasses__ not allowed')
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
    return eval(c, {'__builtins__': {
        'True': True,
        'False': False,
        'str': str,
        'globals': locals,
        'locals': locals,
        'bool': bool,
        'dict': dict,
        }}, data)
