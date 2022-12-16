# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import gtk
import gettext
import gobject

from tryton.config import CONFIG
from tryton.common import RPCExecute
from tryton.exceptions import TrytonServerError, TrytonError

_ = gettext.gettext


def get_completion(search=True, create=True):
    "Return a EntryCompletion"
    completion = gtk.EntryCompletion()
    completion.set_match_func(lambda *a: True)
    completion.set_model(gtk.ListStore(str, int))
    completion.set_text_column(0)
    completion.props.popup_set_width = False
    if search:
        completion.insert_action_markup(0, _('<i>Search...</i>'))
    if create:
        completion.insert_action_markup(1, _('<i>Create...</i>'))
    return completion


def update_completion(entry, record, field, model, domain=None):
    "Update entry completion"
    def update(search_text, domain):
        if not entry.props.window:
            return False
        if search_text != entry.get_text().decode('utf-8'):
            return False
        completion_model = entry.get_completion().get_model()
        if not search_text or not model:
            completion_model.clear()
            completion_model.search_text = search_text
            return False
        if getattr(completion_model, 'search_text', None) == search_text:
            return False
        if domain is None:
            domain = field.domain_get(record)
        context = field.get_context(record)
        domain = [('rec_name', 'ilike', '%' + search_text + '%'), domain]

        def callback(results):
            try:
                results = results()
            except (TrytonError, TrytonServerError):
                results = []
            if search_text != entry.get_text().decode('utf-8'):
                return False
            completion_model.clear()
            for result in results:
                completion_model.append([result['rec_name'], result['id']])
            completion_model.search_text = search_text
            # Force display of popup
            entry.emit('changed')
        RPCExecute('model', model, 'search_read', domain, 0,
            CONFIG['client.limit'], None, ['rec_name'], context=context,
            process_exception=False, callback=callback)
        return False
    search_text = entry.get_text().decode('utf-8')
    gobject.timeout_add(300, update, search_text, domain)
