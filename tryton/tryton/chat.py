# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import gettext

from gi.repository import Gdk, Gio, GObject, Gtk

from tryton import common, rpc
from tryton.bus import Bus

_ = gettext.gettext


class MessageItem(GObject.GObject):

    def __init__(self, message):
        super().__init__()
        self.message = message


class MessageList(GObject.GObject, Gio.ListModel):

    def __init__(self):
        super().__init__()
        self._messages = []
        self._items = {}

    def do_get_item(self, position):
        if position >= len(self._messages):
            return None
        message = self._messages[position]
        if message['id'] not in self._items:
            self._items[message['id']] = MessageItem(message)
        return self._items[message['id']]

    def do_get_item_type(self):
        return MessageItem

    def do_get_n_items(self):
        return len(self._messages)

    def clear(self):
        self.emit('items-changed', 0, len(self._messages), 0)
        self._messages = []
        self._items = {}

    def append(self, message):
        self._messages.append(message)
        self.emit('items-changed', len(self._messages) - 1, 0, 1)


class Chat:

    def __init__(self, record):
        self.record = record
        Bus.register(f"chat:{self.record}", self.notify)
        self.widget = self.__build()

    def unregister(self):
        Bus.unregister(f"chat:{self.record}", self.notify)

    def send_message(self, message, internal):
        rpc.execute(
            'model', 'ir.chat.channel', 'post', self.record, message,
            'internal' if internal else 'public', rpc.CONTEXT)

    def get_messages(self):
        return rpc.execute(
            'model', 'ir.chat.channel', 'get', self.record, rpc.CONTEXT)

    def notify(self, message):
        self.refresh()

    def refresh(self):
        self._messages.clear()
        for post in self.get_messages():
            self._messages.append(post)
        self.widget.show_all()

        def scroll_to_bottom(*args):
            self._messages_sw.disconnect(signal_id)
            vadj = self._messages_sw.get_vadjustment()
            vadj.props.value = vadj.get_upper()
        signal_id = self._messages_sw.connect(
            'size-allocate', scroll_to_bottom)

    def __build(self):
        widget = Gtk.VBox()
        widget.set_spacing(3)

        def _submit(button):
            buffer = input_.get_buffer()
            self.send_message(
                buffer.get_text(
                    buffer.get_start_iter(), buffer.get_end_iter(), False),
                internal.get_active())
            buffer.set_text('')
            if not Bus.listening:
                self.refresh()

        def _keypress(entry, event):
            if (event.state & Gdk.ModifierType.CONTROL_MASK
                    and event.keyval == Gdk.KEY_Return):
                _submit(None)
                return True

        self._messages = MessageList()
        chat_messages = Gtk.ListBox.new()
        chat_messages.props.activate_on_single_click = False
        chat_messages.set_selection_mode(Gtk.SelectionMode.NONE)
        chat_messages.bind_model(self._messages, self.create_message)
        self._messages_sw = scrolledwindow = Gtk.ScrolledWindow()
        viewport = Gtk.Viewport()
        viewport.add(chat_messages)
        viewport.set_valign(Gtk.Align.END)
        scrolledwindow.set_shadow_type(Gtk.ShadowType.NONE)
        scrolledwindow.set_policy(
            Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolledwindow.add(viewport)
        widget.pack_start(scrolledwindow, True, True, 0)

        input_ = Gtk.TextView()
        input_.connect('key-press-event', _keypress)
        input_.set_size_request(-1, 100)
        widget.pack_start(input_, False, True, 0)

        internal = Gtk.CheckButton.new_with_mnemonic(
            _("Make this an _internal message"))
        widget.pack_start(internal, False, True, 0)

        submit = Gtk.Button.new_with_label(_("Send"))
        submit.connect('clicked', _submit)
        widget.pack_start(submit, False, False, 0)

        return widget

    def create_message(self, item):
        message = item.message

        row = Gtk.ListBoxRow()
        row.set_selectable(False)
        row.set_margin_top(5)

        hbox = Gtk.HBox(spacing=10)
        row.add(hbox)

        if avatar_url := message.get('avatar_url'):
            image = Gtk.Image()
            pixbuf = common.IconFactory.get_pixbuf_url(
                avatar_url, size=32, size_param='s',
                callback=image.set_from_pixbuf)
            image.set_from_pixbuf(pixbuf)
            image.set_valign(Gtk.Align.START)
            hbox.pack_start(image, False, False, 0)

        bubble = Gtk.VBox()
        hbox.pack_end(bubble, True, True, 0)

        author = Gtk.Label(label=message['author'])
        author.set_xalign(0)
        author.get_style_context().add_class('dim')
        timestamp = Gtk.Label(label=message['timestamp'].strftime('%x %X'))
        timestamp.set_xalign(1)
        timestamp.get_style_context().add_class('dim')

        meta = Gtk.HBox()
        meta.pack_start(author, True, True, 0)
        meta.pack_end(timestamp, False, False, 0)

        content = Gtk.Label(label=message['content'])
        content.set_xalign(0)
        content.set_line_wrap(True)
        content.set_selectable(True)
        content.get_style_context().add_class(
            f"chat-content-{message['audience']}")

        bubble.pack_start(meta, False, False, 0)
        bubble.pack_start(content, False, False, 0)

        return row
