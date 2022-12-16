# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import logging
import gettext

from gi.repository import GLib, Gtk

from tryton.config import CONFIG
from tryton.common import RPCExecute
from tryton.exceptions import TrytonServerError, TrytonError

_ = gettext.gettext
logger = logging.getLogger(__name__)


def get_completion(search=True, create=True):
    "Return a EntryCompletion"
    completion = Gtk.EntryCompletion()
    completion.set_match_func(lambda *a: True)
    completion.set_model(Gtk.ListStore(str, int))
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
        if search_text != entry.get_text():
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
        context = field.get_search_context(record)
        domain = [('rec_name', 'ilike', '%' + search_text + '%'), domain]
        order = field.get_search_order(record)

        def callback(results):
            try:
                results = results()
            except (TrytonError, TrytonServerError):
                results = []
            if search_text != entry.get_text():
                return False
            completion_model.clear()
            for result in results:
                completion_model.append([result['rec_name'], result['id']])
            completion_model.search_text = search_text
            # Force display of popup
            entry.emit('changed')
        try:
            RPCExecute('model', model, 'search_read', domain, 0,
                CONFIG['client.limit'], order, ['rec_name'], context=context,
                process_exception=False, callback=callback)
        except Exception:
            logger.warning(
                _("Unable to search for completion of %s") % model,
                exc_info=True)
        return False
    search_text = entry.get_text()
    GLib.timeout_add(300, update, search_text, domain)
