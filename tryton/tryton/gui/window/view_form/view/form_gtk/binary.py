#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import base64
import gtk
import gettext
import os
from tryton.common import file_selection, message, warning, Tooltips
from interface import WidgetInterface

_ = gettext.gettext


class Binary(WidgetInterface):
    "Binary"

    def __init__(self, window, parent, model, attrs=None):
        super(Binary, self).__init__(window, parent, model, attrs)

        self.tooltips = Tooltips()

        self.widget = gtk.HBox(spacing=0)
        self.wid_text = gtk.Entry()
        self.wid_text.set_property('activates_default', True)
        self.widget.pack_start(self.wid_text, expand=True, fill=True)

        self.but_new = gtk.Button()
        img_new = gtk.Image()
        img_new.set_from_stock('tryton-open', gtk.ICON_SIZE_SMALL_TOOLBAR)
        self.but_new.set_image(img_new)
        self.but_new.set_relief(gtk.RELIEF_NONE)
        self.but_new.connect('clicked', self.sig_new)
        self.tooltips.set_tip(self.but_new, _('Select a File'))
        self.widget.pack_start(self.but_new, expand=False, fill=False)

        self.but_save_as = gtk.Button()
        img_save_as = gtk.Image()
        img_save_as.set_from_stock('tryton-save-as', gtk.ICON_SIZE_SMALL_TOOLBAR)
        self.but_save_as.set_image(img_save_as)
        self.but_save_as.set_relief(gtk.RELIEF_NONE)
        self.but_save_as.connect('clicked', self.sig_save_as)
        self.tooltips.set_tip(self.but_save_as, _('Save As...'))
        self.widget.pack_start(self.but_save_as, expand=False, fill=False)

        self.but_remove = gtk.Button()
        img_remove = gtk.Image()
        img_remove.set_from_stock('tryton-clear', gtk.ICON_SIZE_SMALL_TOOLBAR)
        self.but_remove.set_image(img_remove)
        self.but_remove.set_relief(gtk.RELIEF_NONE)
        self.but_remove.connect('clicked', self.sig_remove)
        self.tooltips.set_tip(self.but_remove, _('Clear'))
        self.widget.pack_start(self.but_remove, expand=False, fill=False)

        self.tooltips.enable()

        self.model_field = None

    def _readonly_set(self, value):
        if value:
            self.but_new.hide()
            self.but_remove.hide()
            self.widget.set_focus_chain([])
        else:
            self.but_new.show()
            self.but_remove.show()
            self.widget.set_focus_chain([self.but_new, self.but_save_as,
                self.but_remove])

    def grab_focus(self):
        return self.wid_text.grab_focus()

    def sig_new(self, widget=None):
        try:
            filename = file_selection(_('Open...'),
                    parent=self._window)
            if filename and self.model_field:
                self.model_field.set_client(self._view.model,
                        base64.encodestring(file(filename, 'rb').read()))
                fname = self.attrs.get('fname_widget', False)
                if fname:
                    self.parent.value = {fname:os.path.basename(filename)}
                self.display(self._view.model, self.model_field)
        except Exception, exception:
            warning(_('Error reading the file.\nError message:\n%s') \
                    % str(exception), self._window, _('Error'))

    def sig_save_as(self, widget=None):
        try:
            filename = file_selection(_('Save As...'),
                    parent=self._window, action=gtk.FILE_CHOOSER_ACTION_SAVE)
            if filename and self.model_field:
                file_p = file(filename,'wb+')
                file_p.write(base64.decodestring(
                    self.model_field.get(self._view.model)))
                file_p.close()
        except Exception, exception:
            warning(_('Error writing the file.\nError message:\n%s') \
                    % str(exception), self._window, _('Error'))

    def sig_remove(self, widget=None):
        if self.model_field:
            self.model_field.set_client(self._view.model, False)
            fname = self.attrs.get('fname_widget', False)
            if fname:
                self.parent.value = {fname:False}
        self.display(self._view.model, self.model_field)

    def display(self, model, model_field):
        super(Binary, self).display(model, model_field)
        if not model_field:
            self.wid_text.set_text('')
            self.but_save_as.set_sensitive(False)
            return False
        self.model_field = model_field
        self.wid_text.set_text(self._size_get(model_field.get(model)))
        self.but_save_as.set_sensitive(bool(model_field.get(model)))
        return True

    def display_value(self):
        return self.wid_text.get_text()

    def _size_get(self, value):
        return value and ('%d ' + _('bytes')) % len(value) or ''

    def set_value(self, model, model_field):
        return

    def _color_widget(self):
        return self.wid_text
