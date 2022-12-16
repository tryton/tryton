#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
"Attachment"
from tryton.gui.window.view_form.screen import Screen
from tryton.gui.window.win_form import WinForm


class Attachment(object):
    "Attachment window"

    def __init__(self, model_name, record_id):
        self.resource = '%s,%s' % (model_name, record_id)

    def run(self):
        screen = Screen('ir.attachment', domain=[
            ('resource', '=', self.resource),
            ], mode=['tree', 'form'], context={
                'resource': self.resource,
            }, exclude_field='resource')
        screen.search_filter()
        def callback(result):
            if result:
                screen.group.save()
        WinForm(screen, callback, view_type='tree')
