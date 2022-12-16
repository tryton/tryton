# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
"Attachment"
import os
from urllib.request import urlopen
from urllib.parse import urlparse, unquote
import gettext
import webbrowser
from functools import partial

from tryton.common import RPCExecute, RPCException, file_write, file_open
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
        self.prev_view.save_width()
        super(Attachment, self).destroy()

    def callback(self, result):
        if result:
            self.screen.save_current()
        if self.attachment_callback:
            self.attachment_callback()

    def add_uri(self, uri):
        data_field = self.screen.group.fields['data']
        link_field = self.screen.group.fields['link']
        type_field = self.screen.group.fields['type']
        name_field = self.screen.group.fields[data_field.attrs['filename']]
        description_field = self.screen.group.fields['description']
        new_record = self.screen.new()
        parse = urlparse(uri)
        if not parse.scheme:
            description_field.set_client(new_record, uri)
        else:
            file_name = os.path.basename(unquote(parse.path))
            name_field.set_client(new_record, file_name)
            if parse.scheme == 'file':
                data_field.set_client(new_record, urlopen(uri).read())
                type_field.set_client(new_record, 'data')
            else:
                link_field.set_client(new_record, uri)
                type_field.set_client(new_record, 'link')
        self.screen.display()

    def add_file(self, filename):
        self.add_uri('file:///' + filename)

    @staticmethod
    def get_attachments(record):
        attachments = []
        context = {}
        if record and record.id >= 0:
            context = record.get_context()
            try:
                attachments = RPCExecute('model', 'ir.attachment',
                    'search_read', [
                        ('resource', '=', '%s,%s' % (
                                record.model_name, record.id)),
                        ], 0, 20, None, ['rec_name', 'name', 'type', 'link'],
                    context=context)
            except RPCException:
                pass
        for attachment in attachments:
            name = attachment['rec_name']
            callback = getattr(
                Attachment, 'open_' + attachment['type'], Attachment.open_data)
            yield name, partial(
                callback, attachment=attachment, context=context)

    @staticmethod
    def open_link(attachment, context):
        if attachment['link']:
            webbrowser.open(attachment['link'], new=2)

    @staticmethod
    def open_data(attachment, context):
        try:
            value, = RPCExecute('model', 'ir.attachment', 'read',
                [attachment['id']], ['data'], context=context)
        except RPCException:
            return
        filepath = file_write(attachment['name'], value['data'])
        file_open(filepath)
