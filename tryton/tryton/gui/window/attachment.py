#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
"Attachment"
import gtk
import gobject
import gettext
import copy
import os
import base64
import urllib
import tempfile
from tryton.gui.window.view_tree.parse import Parse
import tryton.rpc as rpc
import tryton.common as common
from tryton.config import TRYTON_ICON

_ = gettext.gettext


class Attachment(object):
    "Attachment window"

    def __init__(self, model, obj_id, parent):
        self.dialog = gtk.Dialog(
                title= _("Attachment"),
                parent=parent,
                flags=gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT
                | gtk.WIN_POS_CENTER_ON_PARENT
                | gtk.gdk.WINDOW_TYPE_HINT_DIALOG)
        dialog_vbox = gtk.VBox()
        dialog_vbox.set_size_request(700, 600)
        vpaned = gtk.VPaned()
        vpaned.set_position(450)
        dialog_vbox.pack_start(vpaned, True, True, 0)
        hpaned2 = gtk.HPaned()
        hpaned2.set_position(400)
        vpaned.pack1(hpaned2, False, True)
        vbox_preview = gtk.VBox(False, 0)
        hpaned2.pack1(vbox_preview, False, True)
        self.attach_filename = gtk.Label(_("Preview:"))
        vbox_preview.pack_start(self.attach_filename, False, False, 0)

        scrolledwindow_preview = gtk.ScrolledWindow()
        scrolledwindow_preview.set_policy(gtk.POLICY_AUTOMATIC,
                gtk.POLICY_AUTOMATIC)
        scrolledwindow_preview.set_shadow_type(gtk.SHADOW_NONE)
        viewport_preview = gtk.Viewport()
        scrolledwindow_preview.add(viewport_preview)
        vbox_preview.pack_start(scrolledwindow_preview, True, True, 0)

        self.image_preview = gtk.Image()
        self.image_preview.set_from_stock("tryton-image-missing",
                gtk.ICON_SIZE_DIALOG)
        viewport_preview.add(self.image_preview)

        vbox_descr = gtk.VBox(False, 0)
        hpaned2.pack2(vbox_descr, True, True)
        self.label_descr = gtk.Label(_("Description:"))
        vbox_descr.pack_start(self.label_descr, False, False, 0)
        scrolledwindow_descr = gtk.ScrolledWindow()
        scrolledwindow_descr.set_policy(gtk.POLICY_AUTOMATIC,
                gtk.POLICY_AUTOMATIC)
        scrolledwindow_descr.set_shadow_type(gtk.SHADOW_IN)
        self.text_descr = gtk.TextView()
        scrolledwindow_descr.add(self.text_descr)
        vbox_descr.pack_start(scrolledwindow_descr, True, True, 0)

        button_save_descr = gtk.Button(_("Save _Text"), stock=None,
                use_underline=True)
        img_button = gtk.Image()
        img_button.set_from_stock('tryton-save', gtk.ICON_SIZE_BUTTON)
        button_save_descr.set_image(img_button)
        button_save_descr.connect_after('clicked',  self._sig_comment)
        vbox_descr.pack_start(button_save_descr, False, False, 0)
        hbox = gtk.HBox(False, 0)
        vpaned.pack2(hbox, True, True)
        vbox_buttons = gtk.VBox(False, 0)
        hbox.pack_start(vbox_buttons, False, False, 0)

        button_add_file = gtk.Button(_("Add _File..."), stock=None,
                use_underline=True)
        button_add_file.set_focus_on_click(False)
        button_add_file.set_alignment(0.0,0.0)
        img_button = gtk.Image()
        img_button.set_from_stock('tryton-list-add', gtk.ICON_SIZE_BUTTON)
        button_add_file.set_image(img_button)
        button_add_file.connect_after('clicked', self._sig_add)
        vbox_buttons.pack_start(button_add_file, False, False, 0)

        button_add_link = gtk.Button(_("Add _Link..."), stock=None,
                use_underline=True)
        button_add_link.set_alignment(0.0,0.0)
        img_button = gtk.Image()
        img_button.set_from_stock('tryton-list-add', gtk.ICON_SIZE_BUTTON)
        button_add_link.set_image(img_button)
        button_add_link.connect_after('clicked',  self._sig_link)
        vbox_buttons.pack_start(button_add_link, False, False, 0)

        button_save = gtk.Button(_("_Save as..."), stock=None,
                use_underline=True)
        button_save.set_alignment(0.0,0.0)
        img_button = gtk.Image()
        img_button.set_from_stock('tryton-save-as', gtk.ICON_SIZE_BUTTON)
        button_save.set_image(img_button)
        button_save.connect_after('clicked', self._sig_save)
        vbox_buttons.pack_start(button_save, False, False, 0)

        button_delete = gtk.Button(_("_Delete..."), stock=None,
                use_underline=True)
        button_delete.set_alignment(0.0,0.0)
        img_button = gtk.Image()
        img_button.set_from_stock('tryton-delete', gtk.ICON_SIZE_BUTTON)
        button_delete.set_image(img_button)
        button_delete.connect_after('clicked', self._sig_del)
        vbox_buttons.pack_start(button_delete, False, False, 0)

        button_close = gtk.Button("gtk-close", stock="gtk-close")
        self.dialog.add_action_widget(button_close, gtk.RESPONSE_CLOSE)
        button_close.set_flags(gtk.CAN_DEFAULT)

        scrol_win_all_attachments = gtk.ScrolledWindow()
        scrol_win_all_attachments.set_policy( gtk.POLICY_AUTOMATIC,
                gtk.POLICY_AUTOMATIC)
        scrol_win_all_attachments.set_shadow_type(gtk.SHADOW_NONE)
        viewport_all_attachments = gtk.Viewport()
        scrol_win_all_attachments.add(viewport_all_attachments)
        hbox.pack_start(scrol_win_all_attachments, True, True)

        self.parent = parent
        self.resource = (model, obj_id)

        self.view = gtk.TreeView()
        viewport = viewport_all_attachments
        viewport.add(self.view)

        selection = self.view.get_selection()
        selection.set_mode(gtk.SELECTION_SINGLE)
        selection.connect('changed', self._sig_changed)

        args = ('model', 'ir.attachment', 'fields_view_get', False, 'tree',
                rpc.CONTEXT)
        try:
            view = rpc.execute(*args)
        except Exception, exception:
            view = common.process_exception(exception, parent, *args)
            if not view:
                self.dialog = None
                return

        parse = Parse(view['fields'])
        parse.parse(view['arch'], self.view)
        self.view.set_headers_visible(True)
        self.fields_order = parse.fields_order

        types = [gobject.TYPE_STRING]
        for i in self.fields_order:
            types.append(gobject.TYPE_STRING)
        self.model_name = model
        self.model = gtk.ListStore(*types)

        self.view.set_model(self.model)
        self.view.connect('row-activated', self.sig_activate)
        self.view.show_all()
        self.reload(preview=False)
        self.dialog.vbox.pack_start(dialog_vbox)
        self.dialog.show_all()

    def _sig_comment(self, widget):
        textview = self.text_descr
        start = textview.get_buffer().get_start_iter()
        end = textview.get_buffer().get_end_iter()
        comment = textview.get_buffer().get_text(start, end)
        model, iter = self.view.get_selection().get_selected()
        context = copy.copy(rpc.CONTEXT)
        if not iter:
            common.warning(_('You must put a text comment to an '
                    'attachement.'), self.dialog, _('Text not saved!'))
            return None
        obj_id = model.get_value(iter, 0)
        if obj_id:
            args = ('model', 'ir.attachment', 'write',
                    [int(obj_id)], {'description': comment}, context)
            try:
                rpc.execute(*args)
            except Exception, exception:
                common.process_exception(exception, self.dialog, *args)
        else:
            common.warning(_('You must put a text comment to an '
                    'attachement.'), self.dialog, _('Text not saved!'))

    def _sig_del(self, widget):
        model, iter = self.view.get_selection().get_selected()
        if not iter:
            return None
        obj_id = model.get_value(iter, 0)
        if obj_id:
            if common.sur(_('Are you sure you want to remove this '
                        'attachment?'), self.dialog):
                try:
                    rpc.execute('model', 'ir.attachment', 'delete',
                            [int(obj_id)])
                except Exception, exception:
                    common.process_exception(exception, self.dialog, *args)
        self.reload()

    def _sig_link(self, widget):
        filename = common.file_selection(_('Select file'), parent=self.dialog)
        if not filename:
            return
        try:
            if filename:
                fname = os.path.basename(filename)
                args = ('model', 'ir.attachment', 'create', {
                            'name': fname,
                            'res_model': self.resource[0],
                            'res_id': self.resource[1],
                            'link': filename,})
                try:
                    obj_id = rpc.execute(*args)
                except Exception, exception:
                    obj_id = common.process_exception(exception, self.dialog,
                            *args)
                    if not obj_id:
                        return
                self.reload(preview=False)
                self.preview(int(obj_id))
        except IOError:
            common.message(_('Can not open file!'), self.dialog,
                    gtk.MESSAGE_ERROR)

    def _sig_save(self, widget):
        model, iter = self.view.get_selection().get_selected()
        if not iter:
            return None
        obj_id = model.get_value(iter, 0)
        if obj_id:
            rpcprogress = common.RPCProgress('execute', ('model',
                'ir.attachment', 'read', int(obj_id)), self.dialog)
            try:
                data = rpcprogress.run()
            except Exception, exception:
                common.process_exception(exception, self.dialog)
                return None
            if not data:
                return None
            filename = common.file_selection(_('Save As...'),
                    filename=data['name'], parent=self.dialog,
                    action=gtk.FILE_CHOOSER_ACTION_SAVE)
            if not filename:
                return None
            try:
                if not data['link']:
                    file(filename, 'wb+').write(
                            base64.decodestring(data['datas']))
                else:
                    file(filename, 'wb+').write(
                            urllib.urlopen(data['link']).read())
            except IOError:
                common.message(_('Can not write file!'), self.dialog,
                        gtk.MESSAGE_ERROR)

    def _sig_add(self, widget):
        filter_all = gtk.FileFilter()
        filter_all.set_name(_('All files'))
        filter_all.add_pattern("*")

        filter_image = gtk.FileFilter()
        filter_image.set_name(_('Images'))
        for mime in ("image/png", "image/jpeg", "image/gif"):
            filter_image.add_mime_type(mime)
        for pat in ("*.png", "*.jpg", "*.gif", "*.tif", "*.xpm"):
            filter_image.add_pattern(pat)

        filenames = common.file_selection(_('Open...'), preview=True,
                multi=True, parent=self.dialog,
                filters=[filter_all, filter_image])
        if not filenames:
            return
        for filename in filenames:
            value = file(filename, 'rb').read()
            name = os.path.basename(filename)
            args = ('model', 'ir.attachment', 'create', {
                        'name': name,
                        'datas': base64.encodestring(value),
                        'res_model': self.resource[0],
                        'res_id': self.resource[1],})
            rpcprogress = common.RPCProgress('execute', args, self.dialog)
            try:
                obj_id = rpcprogress.run()
            except Exception, exception:
                common.process_exception(exception, self.dialog)
                return
            self.reload(preview=False)
            self.preview(int(obj_id))

    def _sig_changed(self, widget):
        model, iters = self.view.get_selection().get_selected_rows()
        if not iters:
            return None
        obj_id = model.get_value(model.get_iter(iters[0]), 0)
        self.preview(int(obj_id))

    def sig_activate(self, widget, path, view_column):
        iter = self.model.get_iter(path)
        obj_id = self.model.get_value(iter, 0)
        if obj_id:
            rpcprogress = common.RPCProgress('execute', ('model',
                'ir.attachment', 'read', int(obj_id)), self.dialog)
            try:
                data = rpcprogress.run()
            except Exception, exception:
                common.process_exception(exception, self.dialog)
                return None
            if not data:
                return None
            file_name = data['link']
            if not data['link']:
                (fileno, file_name) = tempfile.mkstemp(
                        data['name'], 'tryton_')
                file_p = file(file_name, 'wb+')
                if data['datas']:
                    file_p.write(base64.decodestring(data['datas']))
                file_p.close()
                os.close(fileno)
            ext = file_name.split('.')[-1].lower()
            common.file_open(file_name, ext, self.parent)

    def preview(self, obj_id):
        rpcprogress = common.RPCProgress('execute', ('model',
            'ir.attachment', 'read', obj_id), self.dialog)
        try:
            data = rpcprogress.run()
        except Exception, exception:
            common.process_exception(exception, self.dialog)
            return None
        if not data:
            return None

        buf = self.text_descr.get_buffer()
        buf.delete(buf.get_start_iter(), buf.get_end_iter())
        iter_start = buf.get_start_iter()
        buf.insert(iter_start, data['description'] or '')

        fname = str(data['name'])

        decoder = {'jpg': 'jpeg',
                   'jpeg': 'jpeg',
                   'gif': 'gif',
                   'png': 'png',
                   'bmp': 'bmp',}
        ext = fname.split('.')[-1].lower()
        img = self.image_preview
        img.clear()
        if ext in decoder.iterkeys():
            try:
                if not data['link']:
                    value = base64.decodestring(data['datas'])
                else:
                    value = urllib.urlopen(data['link']).read()

                def set_size(widget, width, height):
                    allocation = self.dialog.get_allocation()
                    scale1 = 0.3 * float(allocation.width) / float(width)
                    scale2 = 0.3 * float(allocation.height) / float(height)
                    scale = min(scale1, scale2)
                    if int(scale * width) > 0 and int(scale * height) > 0:
                        widget.set_size(int(scale * width),
                                int(scale * height))

                loader = gtk.gdk.PixbufLoader(decoder[ext])
                loader.connect_after('size-prepared', set_size)

                loader.write(value, len(value))
                pixbuf = loader.get_pixbuf()
                loader.close()

                img.set_from_pixbuf(pixbuf)
            except:
                img.set_from_icon_name('gtk-cancel', gtk.ICON_SIZE_DIALOG)

    def reload(self, preview=True):
        self.model.clear()
        try:
            ids = rpc.execute('model', 'ir.attachment', 'search', [
                        ('res_model', '=', self.resource[0]),
                        ('res_id', '=', self.resource[1]),
                        ])
        except Exception, exception:
            common.process_exception(exception, self.dialog)
            return
        try:
            res_ids = rpc.execute('model', 'ir.attachment', 'read', ids,
                    self.fields_order + ['link'])
        except Exception, exception:
            common.process_exception(exception, self.dialog)
            return
        for res in res_ids:
            num = self.model.append()
            args = []
            for i in range(len(self.fields_order)):
                args.append(i + 1)
                if res['link']:
                    args.append(_('link: ') + str(res[self.fields_order[i]]))
                else:
                    args.append(str(res[self.fields_order[i]]))
            self.model.set(num, 0, res['id'], *args)
        if preview and len(res_ids):
            self.preview(int(res_ids[0]['id']))

    def run(self):
        if not self.dialog:
            return
        self.dialog.run()
        self.parent.present()
        self.dialog.destroy()
