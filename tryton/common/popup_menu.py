# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import gettext

from gi.repository import Gtk, Gdk

from tryton.common import RPCExecute, RPCException
from tryton.common.common import selection
from tryton.gui.window.view_form.screen import Screen
from tryton.action import Action
from tryton.gui.window import Window
from tryton.gui.window.attachment import Attachment
from tryton.gui.window.email_ import Email
from tryton.gui.window.note import Note

_ = gettext.gettext


def populate(menu, model, record, title='', field=None, context=None):
    '''
    Fill menu with the actions of model for the record.
    If title is filled, the actions will be put in a submenu.
    '''
    if record is None:
        return
    elif isinstance(record, int):
        if record < 0:
            return
    elif record.id < 0:
        return

    def load(record):
        if isinstance(record, int):
            screen = Screen(model, context=context)
            screen.load([record])
            record = screen.current_record
        return record

    def id_(record):
        if not isinstance(record, int):
            return record.id
        return record

    def activate(menuitem, action, atype):
        rec = load(record)
        data = {
            'model': model,
            'id': rec.id,
            'ids': [rec.id],
            }
        event = Gtk.get_current_event()
        allow_similar = False
        if (event.state & Gdk.ModifierType.CONTROL_MASK
                or event.state & Gdk.ModifierType.MOD1_MASK):
            allow_similar = True
        with Window(hide_current=True, allow_similar=allow_similar):
            Action.execute(action, data, context=rec.get_context())

    def attachment(menuitem):
        Attachment(load(record), None)

    def note(menuitem):
        Note(load(record), None)

    def is_report(action):
        return action['type'] == 'ir.action.report'

    def email(menuitem, toolbar):
        rec = load(record)
        prints = filter(is_report, toolbar['print'])
        emails = {e['name']: e['id'] for e in toolbar['emails']}
        template = selection(_("Template"), emails, alwaysask=True)
        if template:
            template = template[1]
        Email(
            '%s: %s' % (title, rec.rec_name()), rec, prints,
            template=template)

    def edit(menuitem):
        with Window(hide_current=True, allow_similar=True):
            Window.create(model,
                view_ids=field.attrs.get('view_ids', '').split(','),
                res_id=id_(record),
                mode=['form'],
                name=field.attrs.get('string'))

    if title:
        if len(menu):
            menu.append(Gtk.SeparatorMenuItem())
        title_item = Gtk.MenuItem(label=title)
        menu.append(title_item)
        submenu = Gtk.Menu()
        title_item.set_submenu(submenu)
        action_menu = submenu
    else:
        action_menu = menu

    if len(action_menu):
        action_menu.append(Gtk.SeparatorMenuItem())
    if field:
        edit_item = Gtk.MenuItem(label=_('Edit...'))
        edit_item.connect('activate', edit)
        action_menu.append(edit_item)
        action_menu.append(Gtk.SeparatorMenuItem())
    attachment_item = Gtk.MenuItem(label=_('Attachments...'))
    action_menu.append(attachment_item)
    attachment_item.connect('activate', attachment)
    note_item = Gtk.MenuItem(label=_('Notes...'))
    action_menu.append(note_item)
    note_item.connect('activate', note)

    try:
        toolbar = RPCExecute('model', model, 'view_toolbar_get')
    except RPCException:
        pass
    else:
        for atype, icon, label, flavor in (
                ('action', 'tryton-launch', _('Actions...'), None),
                ('relate', 'tryton-link', _('Relate...'), None),
                ('print', 'tryton-open', _('Report...'), 'open'),
                ('print', 'tryton-print', _('Print...'), 'print'),
                ):
            if len(action_menu):
                action_menu.append(Gtk.SeparatorMenuItem())
            title_item = Gtk.MenuItem(label=label)
            action_menu.append(title_item)
            if not toolbar[atype]:
                title_item.set_sensitive(False)
                continue
            submenu = Gtk.Menu()
            title_item.set_submenu(submenu)
            for action in toolbar[atype]:
                action = action.copy()
                item = Gtk.MenuItem(label=action['name'])
                submenu.append(item)
                if flavor == 'print':
                    action['direct_print'] = True
                item.connect('activate', activate, action, atype)
            menu.show_all()

        email_item = Gtk.MenuItem(label=_('E-Mail...'))
        action_menu.append(email_item)
        email_item.connect('activate', email, toolbar)
    menu.show_all()
