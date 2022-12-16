#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
"Attachment"
from tryton.gui.window.view_form.screen import Screen
from tryton.gui.window.win_form import WinForm


class Attachment(WinForm):
    "Attachment window"

    def __init__(self, model_name, record_id, callback=None):
        self.resource = '%s,%s' % (model_name, record_id)
        self.attachment_callback = callback
        screen = Screen('ir.attachment', domain=[
            ('resource', '=', self.resource),
            ], mode=['tree', 'form'], context={
                'resource': self.resource,
            }, exclude_field='resource')
        screen.search_filter()
        screen.parent = True
        super(Attachment, self).__init__(screen, self.callback,
            view_type='tree')

    def destroy(self):
        self.prev_view.save_width_height()
        super(Attachment, self).destroy()

    def callback(self, result):
        if result:
            self.screen.group.save()
        if self.attachment_callback:
            self.attachment_callback()
