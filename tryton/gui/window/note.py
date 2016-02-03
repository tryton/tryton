# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from tryton.gui.window.view_form.screen import Screen
from tryton.gui.window.win_form import WinForm


class Note(WinForm):
    "Note window"

    def __init__(self, record, callback=None):
        self.resource = '%s,%s' % (record.model_name, record.id)
        self.note_callback = callback
        context = record.context_get()
        context['resource'] = self.resource
        screen = Screen('ir.note', domain=[
                ('resource', '=', self.resource),
                ], mode=['tree', 'form'], context=context,
            exclude_field='resource')
        super(Note, self).__init__(screen, self.callback, view_type='tree')
        screen.search_filter()
        # Set parent after to be allowed to call search_filter
        screen.parent = record

    def destroy(self):
        self.prev_view.save_width_height()
        super(Note, self).destroy()

    def callback(self, result):
        if result:
            resource = self.screen.group.fields['resource']
            unread = self.screen.group.fields['unread']
            for record in self.screen.group:
                if record.loaded or record.id < 0:
                    resource.set_client(record, self.resource)
                    if 'unread' not in record.modified_fields:
                        unread.set_client(record, False)
            self.screen.group.save()
        if self.note_callback:
            self.note_callback()
