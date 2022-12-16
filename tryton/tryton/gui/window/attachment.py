#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
"Attachment"
from tryton.gui.window.view_form.screen import Screen
from tryton.gui.window.win_form import WinForm


class Attachment(object):
    "Attachment window"

    def __init__(self, model_name, record_id, parent):
        self.resource = '%s,%s' % (model_name, record_id)
        self.parent = parent

    def run(self):
        screen = Screen('ir.attachment', self.parent, domain=[
            ('resource', '=', self.resource),
            ], view_type=['tree', 'form'], context={
                'resource': self.resource,
            }, exclude_field='resource')
        screen.search_filter()
        win = WinForm(screen, self.parent, view_type='tree')
        if win.run():
            screen.group.save()
        self.parent.present()
        win.destroy()
