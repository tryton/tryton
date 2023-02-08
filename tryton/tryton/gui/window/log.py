# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import gettext

from gi.repository import Gtk

from tryton.common import RPCException, RPCExecute, timezoned_date
from tryton.common.underline import set_underline
from tryton.gui.window.view_form.screen import Screen
from tryton.gui.window.win_form import WinForm

_ = gettext.gettext


class Log(WinForm):

    def __init__(self, record):
        self.resource = '%s,%s' % (record.model_name, record.id)
        title = _("Logs (%s)") % record.rec_name()

        context = record.get_context()
        try:
            log, = RPCExecute(
                'model', record.model_name, 'read', [record.id],
                ['create_uid.rec_name', 'create_date',
                    'write_uid.rec_name', 'write_date'], context=context)
        except RPCException:
            return

        date_format = context.get('date_format', '%x')
        datetime_format = date_format + ' %H:%M:%S.%f'

        grid = Gtk.Grid(
            column_spacing=3, row_spacing=3, border_width=3)

        entry_model = Gtk.Entry(editable=False)
        entry_model.set_text(record.model_name)
        grid.attach(entry_model, 1, 1, 1, 1)
        label_model = Gtk.Label(
            label=set_underline(_("Model:")),
            use_underline=True, halign=Gtk.Align.END)
        label_model.set_mnemonic_widget(entry_model)
        grid.attach(label_model, 0, 1, 1, 1)

        entry_id = Gtk.Entry(editable=False)
        entry_id.set_alignment(1)
        entry_id.set_text(str(record.id))
        grid.attach(entry_id, 3, 1, 1, 1)
        label_id = Gtk.Label(
            label=set_underline(_("ID:")),
            use_underline=True, halign=Gtk.Align.END)
        label_id.set_mnemonic_widget(entry_id)
        grid.attach(label_id, 2, 1, 1, 1)

        for i, (user, user_label, date, date_label) in enumerate([
                    ('create_uid.', _("Created by:"),
                        'create_date', _("Created at:")),
                    ('write_uid.', _("Last Modified by:"),
                        'write_date', _("Last Modified at:"))], 2):
            entry_user = Gtk.Entry(editable=False, width_chars=50)
            user = log.get(user)
            if user:
                user = user.get('rec_name', '')
            entry_user.set_text(user or '')
            grid.attach(entry_user, 1, i, 1, 1)
            label_user = Gtk.Label(
                label=set_underline(user_label),
                use_underline=True, halign=Gtk.Align.END)
            label_user.set_mnemonic_widget(entry_user)
            grid.attach(label_user, 0, i, 1, 1)

            entry_date = Gtk.Entry(editable=False)
            date = log.get(date)
            if date:
                date = timezoned_date(date).strftime(datetime_format)
            entry_date.set_width_chars(len(date or ''))
            entry_date.set_text(date or '')
            grid.attach(entry_date, 3, i, 1, 1)
            label_date = Gtk.Label(
                label=set_underline(date_label),
                use_underline=True, halign=Gtk.Align.END)
            label_date.set_mnemonic_widget(entry_date)
            grid.attach(label_date, 2, i, 1, 1)

        grid.show_all()

        screen = Screen('ir.model.log', domain=[
                ('resource', '=', self.resource),
                ], mode=['tree', 'form'])
        super().__init__(screen, view_type='tree', title=title)
        screen.search_filter()

        self.win.vbox.pack_start(grid, expand=False, fill=True, padding=0)
        self.win.vbox.reorder_child(grid, 2)
