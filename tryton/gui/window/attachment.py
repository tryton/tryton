# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
"Attachment"
import os
import urllib
import urlparse
import sys
import gettext

from tryton.gui.window.view_form.screen import Screen
from tryton.gui.window.win_form import WinForm

_ = gettext.gettext


class Attachment(WinForm):
    "Attachment window"

    def __init__(self, record, callback=None):
        self.resource = '%s,%s' % (record.model_name, record.id)
        self.attachment_callback = callback
        title = _('Attachments (%s)') % (record.rec_name())
        screen = Screen('ir.attachment', domain=[
            ('resource', '=', self.resource),
            ], mode=['tree', 'form'])
        super(Attachment, self).__init__(screen, self.callback,
            view_type='tree', title=title)
        screen.search_filter()

    def destroy(self):
        self.prev_view.save_width_height()
        super(Attachment, self).destroy()

    def callback(self, result):
        if result:
            self.screen.save_current()
        if self.attachment_callback:
            self.attachment_callback()

    def add_uri(self, uri):
        self.screen.switch_view('form')
        data_field = self.screen.group.fields['data']
        name_field = self.screen.group.fields[data_field.attrs['filename']]
        new_record = self.screen.new()
        file_name = os.path.basename(urlparse.urlparse(uri).path)
        name_field.set_client(new_record, file_name)
        uri = urllib.unquote(uri)
        uri = uri.decode('utf-8').encode(sys.getfilesystemencoding())
        data_field.set_client(new_record, urllib.urlopen(uri).read())
        self.screen.display()
