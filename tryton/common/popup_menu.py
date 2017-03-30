# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import gtk
import gettext
from tryton.common import RPCExecute, RPCException
from tryton.gui.window.view_form.screen import Screen
from tryton.action import Action
from tryton.gui.window import Window
from tryton.gui.window.attachment import Attachment
from tryton.gui.window.note import Note

_ = gettext.gettext


def populate(menu, model, record, title='', field=None):
    '''
    Fill menu with the actions of model for the record.
    If title is filled, the actions will be put in a submenu.
    '''
    if record is None:
        return
    elif isinstance(record, (int, long)):
        if record < 0:
            return
    elif record.id < 0:
        return

    def load(record):
        if isinstance(record, (int, long)):
            screen = Screen(model)
            screen.load([record])
            record = screen.current_record
        return record

    def id_(record):
        if not isinstance(record, (int, long)):
            return record.id
        return record

    def activate(menuitem, action, atype):
        rec = load(record)
        action = Action.evaluate(action, atype, rec)
        data = {
            'model': model,
            'id': rec.id,
            'ids': [rec.id],
            }
        event = gtk.get_current_event()
        allow_similar = False
        if (event.state & gtk.gdk.CONTROL_MASK
                or event.state & gtk.gdk.MOD1_MASK):
            allow_similar = True
        with Window(hide_current=True, allow_similar=allow_similar):
            Action._exec_action(action, data, {})

    def attachment(menuitem):
        Attachment(load(record), None)

    def note(menuitem):
        Note(load(record), None)

    def edit(menuitem):
        with Window(hide_current=True, allow_similar=True):
            Window.create(
                field.attrs.get('view_ids', '').split(','), model, id_(record),
                mode=['form'], name=field.attrs.get('string'))

    if title:
        if len(menu):
            menu.append(gtk.SeparatorMenuItem())
        title_item = gtk.MenuItem(title)
        menu.append(title_item)
        submenu = gtk.Menu()
        title_item.set_submenu(submenu)
        action_menu = submenu
    else:
        action_menu = menu

    if len(action_menu):
        action_menu.append(gtk.SeparatorMenuItem())
    if field:
        edit_item = gtk.MenuItem(_('Edit...'))
        edit_item.connect('activate', edit)
        action_menu.append(edit_item)
        action_menu.append(gtk.SeparatorMenuItem())
    attachment_item = gtk.ImageMenuItem()
    attachment_item.set_label(_('Attachments...'))
    attachment_icon = gtk.Image()
    attachment_icon.set_from_stock('tryton-attachment', gtk.ICON_SIZE_MENU)
    attachment_item.set_image(attachment_icon)
    action_menu.append(attachment_item)
    attachment_item.connect('activate', attachment)
    note_item = gtk.ImageMenuItem()
    note_item.set_label(_('Notes...'))
    note_icon = gtk.Image()
    note_icon.set_from_stock('tryton-note', gtk.ICON_SIZE_MENU)
    note_item.set_image(note_icon)
    action_menu.append(note_item)
    note_item.connect('activate', note)

    def set_toolbar(toolbar):
        try:
            toolbar = toolbar()
        except RPCException:
            return
        for atype, icon, label, flavor in (
                ('action', 'tryton-executable', _('Actions...'), None),
                ('relate', 'tryton-go-jump', _('Relate...'), None),
                ('print', 'tryton-print-open', _('Report...'), 'open'),
                ('print', 'tryton-print-email', _('E-Mail...'), 'email'),
                ('print', 'tryton-print', _('Print...'), 'print'),
                ):
            if len(action_menu):
                action_menu.append(gtk.SeparatorMenuItem())
            title_item = gtk.ImageMenuItem()
            title_item.set_label(label)
            title_icon = gtk.Image()
            title_icon.set_from_stock(icon, gtk.ICON_SIZE_MENU)
            title_item.set_image(title_icon)
            action_menu.append(title_item)
            if not toolbar[atype]:
                title_item.set_sensitive(False)
                continue
            submenu = gtk.Menu()
            title_item.set_submenu(submenu)
            for action in toolbar[atype]:
                action = action.copy()
                item = gtk.MenuItem(action['name'])
                submenu.append(item)
                if flavor == 'print':
                    action['direct_print'] = True
                elif flavor == 'email':
                    action['email_print'] = True
                item.connect('activate', activate, action, atype)
            menu.show_all()
    RPCExecute('model', model, 'view_toolbar_get', callback=set_toolbar)
    menu.show_all()
