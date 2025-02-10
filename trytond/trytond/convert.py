# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
import logging
import re
import time
from collections import defaultdict
from decimal import Decimal
from xml import sax

from trytond import __version__
from trytond.pyson import CONTEXT, PYSONEncoder
from trytond.transaction import Transaction, inactive_records

logger = logging.getLogger(__name__)

CDATA_START = re.compile(r'^\s*\<\!\[cdata\[', re.IGNORECASE)
CDATA_END = re.compile(r'\]\]\>\s*$', re.IGNORECASE)


class ParsingError(Exception):
    pass


class DummyTagHandler:
    """Dubhandler implementing empty methods. Will be used when whe
    want to ignore the xml content"""

    def __init__(self):
        pass

    def startElement(self, name, attributes):
        pass

    def characters(self, data):
        pass

    def endElement(self, name):
        pass


class MenuitemTagHandler:
    """Taghandler for the tag <record> """
    def __init__(self, master_handler):
        self.mh = master_handler
        self.xml_id = None

    def startElement(self, name, attributes):
        cursor = Transaction().connection.cursor()

        values = {}

        try:
            self.xml_id = attributes['id']
        except KeyError:
            self.xml_id = None
            raise ParsingError("missing 'id' attribute")

        for attr in ('name', 'sequence', 'parent', 'action', 'groups'):
            if attr in attributes:
                values[attr] = attributes.get(attr)
        values['icon'] = attributes.get('icon', 'tryton-folder')

        if attributes.get('active'):
            values['active'] = bool(eval(attributes['active']))

        if values.get('parent'):
            model, id_ = self.mh.get_id(values['parent'])
            if model != 'ir.ui.menu':
                raise ParsingError(
                    "invalid 'ir.ui.menu' parent: %s" % model)
            values['parent'] = id_

        action_name = None
        if values.get('action'):
            model, action_id = self.mh.get_id(values['action'])
            if not model.startswith('ir.action'):
                raise ParsingError(
                    "invalid model for action: %s" % model)

            # TODO maybe use a prefetch for this:
            action = self.mh.pool.get('ir.action').__table__()
            report = self.mh.pool.get('ir.action.report').__table__()
            act_window = self.mh.pool.get('ir.action.act_window').__table__()
            wizard = self.mh.pool.get('ir.action.wizard').__table__()
            url = self.mh.pool.get('ir.action.url').__table__()
            act_window_view = self.mh.pool.get(
                'ir.action.act_window.view').__table__()
            view = self.mh.pool.get('ir.ui.view').__table__()
            icon = self.mh.pool.get('ir.ui.icon').__table__()
            cursor.execute(*action.join(
                    report, 'LEFT',
                    condition=action.id == report.action
                    ).join(act_window, 'LEFT',
                    condition=action.id == act_window.action
                    ).join(wizard, 'LEFT',
                    condition=action.id == wizard.action
                    ).join(url, 'LEFT',
                    condition=action.id == url.action
                    ).join(act_window_view, 'LEFT',
                    condition=act_window.id == act_window_view.act_window
                    ).join(view, 'LEFT',
                    condition=view.id == act_window_view.view
                    ).join(icon, 'LEFT',
                    condition=action.icon == icon.id).select(
                    action.name.as_('action_name'),
                    action.type.as_('action_type'),
                    view.type.as_('view_type'),
                    view.field_childs.as_('field_childs'),
                    icon.name.as_('icon_name'),
                    where=(report.id == action_id)
                    | (act_window.id == action_id)
                    | (wizard.id == action_id)
                    | (url.id == action_id),
                    order_by=act_window_view.sequence, limit=1))
            action_name, action_type, view_type, field_childs, icon_name = \
                cursor.fetchone()

            values['action'] = '%s,%s' % (action_type, action_id)

            icon = attributes.get('icon', '')
            if icon:
                values['icon'] = icon
            elif icon_name:
                values['icon'] = icon_name
            elif action_type == 'ir.action.wizard':
                values['icon'] = 'tryton-launch'
            elif action_type == 'ir.action.report':
                values['icon'] = 'tryton-print'
            elif action_type == 'ir.action.act_window':
                if view_type == 'tree':
                    if field_childs:
                        values['icon'] = 'tryton-tree'
                    else:
                        values['icon'] = 'tryton-list'
                elif view_type == 'form':
                    values['icon'] = 'tryton-form'
                elif view_type == 'graph':
                    values['icon'] = 'tryton-graph'
                elif view_type == 'calendar':
                    values['icon'] = 'tryton-calendar'
                elif view_type == 'board':
                    values['icon'] = 'tryton-board'
                elif view_type == 'list-form':
                    values['icon'] = 'tryton-list-form'
            elif action_type == 'ir.action.url':
                values['icon'] = 'tryton-public'
            else:
                values['icon'] = None

        if values.get('groups'):
            raise ParsingError("forbidden 'groups' attribute")

        if not values.get('name'):
            if not action_name:
                raise ParsingError("missing 'name' or 'action' attribute")
            else:
                values['name'] = action_name

        if values.get('sequence'):
            values['sequence'] = int(values['sequence'])

        self.values = values

    def characters(self, data):
        pass

    def endElement(self, name):
        """Must return the object to use for the next call """
        if name != "menuitem":
            return self
        else:
            self.mh.import_record('ir.ui.menu', self.values, self.xml_id)
            return None

    def current_state(self):
        return "menuitem '%s.%s'" % (self.mh.module, self.xml_id)


class RecordTagHandler:

    """Taghandler for the tag <record> and all the tags inside it"""

    def __init__(self, master_handler):
        # Remind reference of parent handler
        self.mh = master_handler
        # stock xml_id parsed in one module
        self.xml_ids = []
        self.model = None
        self.xml_id = None
        self.update = None
        self.values = None
        self.current_field = None
        self.cdata = None
        self.start_cdata = None

    def startElement(self, name, attributes):

        # Manage the top level tag
        if name == "record":
            try:
                self.xml_id = attributes["id"]
            except KeyError:
                self.xml_id = None
                raise ParsingError("missing 'id' attribute")

            self.model = self.mh.pool.get(attributes["model"])

            self.update = bool(int(attributes.get('update', '0')))

            # create/update a dict containing fields values
            self.values = {}

            self.current_field = None
            self.cdata = False

            return self.xml_id

        # Manage included tags:
        elif name == "field":

            field_name = attributes['name']
            field_type = attributes.get('type', '')
            # Remind the current name and if we have to load (see characters)
            self.current_field = field_name
            depends = attributes.get('depends', '').split(',')
            depends = {m.strip() for m in depends if m}
            if not depends.issubset(self.mh.modules):
                self.current_field = None
                return
            # Create a new entry in the values
            self.values[field_name] = ""
            # Put a flag to escape cdata tags
            if field_type == "xml":
                self.cdata = "start"

            # Catch the known attributes
            search_attr = attributes.get('search', '')
            ref_attr = attributes.get('ref', '')
            eval_attr = attributes.get('eval', '')
            pyson_attr = bool(int(attributes.get('pyson', '0')))

            context = {}
            context['time'] = time
            context['version'] = __version__.rsplit('.', 1)[0]
            context['ref'] = lambda xml_id: ','.join(self.mh.get_id(xml_id))
            context['Decimal'] = Decimal
            context['datetime'] = datetime
            if pyson_attr:
                context.update(CONTEXT)

            field = self.model._fields[field_name]
            if search_attr:
                search_model = field.model_name
                SearchModel = self.mh.pool.get(search_model)
                with inactive_records():
                    found, = SearchModel.search(eval(search_attr, context))
                    self.values[field_name] = found.id

            elif ref_attr:
                model, id_ = self.mh.get_id(ref_attr)
                if field._type == 'reference':
                    self.values[field_name] = '%s,%s' % (model, id_)
                else:
                    if (field.model_name == 'ir.action'
                            and model.startswith('ir.action')):
                        pass
                    elif model != field.model_name:
                        raise ParsingError(
                            "invalid model for %s: %s" % (field_name, model))
                    self.values[field_name] = id_

            elif eval_attr:
                value = eval(eval_attr, context)
                if pyson_attr:
                    value = PYSONEncoder(sort_keys=True).encode(value)
                self.values[field_name] = value

        else:
            raise ParsingError(
                "forbidden '%s' tag inside record tag" % name)

    def characters(self, data):

        """If we are in a field tag, consume all the content"""

        if not self.current_field:
            return
        # Escape start cdata tag if necessary
        if self.cdata == "start":
            data = CDATA_START.sub('', data)
            self.start_cdata = "inside"

        self.values[self.current_field] += data

    def endElement(self, name):

        """Must return the object to use for the next call, if name is
        not 'record' we return self to keep our hand on the
        process. If name is 'record' we return None to end the
        delegation"""

        if name == "field":
            if not self.current_field:
                return self
            # Escape end cdata tag :
            if self.cdata in ('inside', 'start'):
                self.values[self.current_field] = \
                    CDATA_END.sub('', self.values[self.current_field])
                self.cdata = 'done'
            self.current_field = None
            return self

        elif name == "record":
            if self.xml_id in self.xml_ids and not self.update:
                raise ParsingError("duplicate id: %s" % self.xml_id)
            self.mh.import_record(
                self.model.__name__, self.values, self.xml_id)
            self.xml_ids.append(self.xml_id)
            return None
        else:
            raise ParsingError("unexpected closing tag '%s'" % name)

    def current_state(self):
        return "record '%s.%s'" % (self.mh.module, self.xml_id)


class FS2DBAccessor:
    """
    Used in TrytondXmlHandler.
    Provide some helper function to ease cache access and management.
    """

    def __init__(self, ModelData):
        self.fs2db = defaultdict(lambda: defaultdict(dict))
        self.fetched_modules = []
        self.ModelData = ModelData

    def get(self, module, fs_id):
        if module not in self.fetched_modules:
            self.fetch_new_module(module)
        return self.fs2db[module].get(fs_id, None)

    def exists(self, module, fs_id):
        if module not in self.fetched_modules:
            self.fetch_new_module(module)
        return fs_id in self.fs2db[module]

    def set(self, module, fs_id, record):
        # We call the prefetch function here to.
        # Like that we are sure not to erase data when get is called.
        if module not in self.fetched_modules:
            self.fetch_new_module(module)
        self.fs2db[module][fs_id] = record

    def fetch_new_module(self, module):
        records = self.ModelData.search([
                ('module', '=', module),
                ],
            order=[('db_id', 'ASC')])
        for record in records:
            self.fs2db[record.module][record.fs_id] = record
        self.fetched_modules.append(module)


class TrytondXmlHandler(sax.handler.ContentHandler):

    def __init__(self, pool, module, module_state, modules, languages):
        "Register known taghandlers, and managed tags."
        sax.handler.ContentHandler.__init__(self)

        self.pool = pool
        self.module = module
        self.ModelData = pool.get('ir.model.data')
        self.fs2db = FS2DBAccessor(self.ModelData)
        self.to_delete = self.populate_to_delete()
        self.noupdate = None
        self.module_state = module_state
        self.grouped = None
        self.grouped_creations = defaultdict(dict)
        self.grouped_write = defaultdict(list)
        self.grouped_model_data = set()
        self.skip_data = False
        self.modules = modules
        self.languages = languages

        # Tag handlders are used to delegate the processing
        self.taghandlerlist = {
            'record': RecordTagHandler(self),
            'menuitem': MenuitemTagHandler(self),
            }
        self.taghandler = None

        # Managed tags are handled by the current class
        self.managedtags = ["data", "tryton"]

        # Connect to the sax api:
        self.sax_parser = sax.make_parser()
        # Tell the parser we are not interested in XML namespaces
        self.sax_parser.setFeature(sax.handler.feature_namespaces, 0)
        self.sax_parser.setContentHandler(self)

    def parse_xmlstream(self, stream):
        """
        Take a byte stream has input and parse the xml content.
        """

        source = sax.InputSource()
        source.setByteStream(stream)

        with Transaction().set_context(language='en', module=self.module):
            try:
                self.sax_parser.parse(source)
            except Exception as e:
                raise ParsingError("in %s" % self.current_state()) from e
        return self.to_delete

    def startElement(self, name, attributes):
        """Rebind the current handler if necessary and call
        startElement on it"""

        if not self.taghandler:

            if name in self.taghandlerlist:
                self.taghandler = self.taghandlerlist[name]
            elif name == "data":
                self.noupdate = bool(int(attributes.get("noupdate", '0')))
                self.grouped = bool(int(attributes.get('grouped', 0)))
                self.skip_data = False
                depends = attributes.get('depends', '').split(',')
                depends = {m.strip() for m in depends if m}
                if not depends.issubset(self.modules):
                    self.skip_data = True
                if (attributes.get('language')
                        and attributes.get('language') not in self.languages):
                    self.skip_data = True

            elif name == "tryton":
                pass

            else:
                logger.info("Tag %s not supported", (name,))
                return
        if self.taghandler and not self.skip_data:
            self.taghandler.startElement(name, attributes)

    def characters(self, data):
        if self.taghandler:
            self.taghandler.characters(data)

    def endElement(self, name):

        if name == 'data' and self.grouped:
            for model, values in self.grouped_creations.items():
                self.create_records(model, values.values(), values.keys())
            self.grouped_creations.clear()
            for model, actions in self.grouped_write.items():
                self.write_records(model, *actions)
            self.grouped_write.clear()
        if name == 'data' and self.grouped_model_data:
            self.ModelData.save(self.grouped_model_data)
            self.grouped_model_data.clear()

        # Closing tag found, if we are in a delegation the handler
        # know what to do:
        if self.taghandler and not self.skip_data:
            self.taghandler = self.taghandler.endElement(name)
        if self.taghandler == self.taghandlerlist.get(name):
            self.taghandler = None

    def current_state(self):
        if self.taghandler:
            return self.taghandler.current_state()
        else:
            return '?'

    def get_id(self, xml_id):

        if '.' in xml_id:
            module, xml_id = xml_id.split('.')
        else:
            module = self.module

        if self.fs2db.get(module, xml_id) is None:
            raise ParsingError("%s.%s not found" % (module, xml_id))
        record = self.fs2db.get(module, xml_id)
        return record.model, record.db_id

    @staticmethod
    def _clean_value(key, record):
        """
        Take a field name, a browse_record, and a reference to the
        corresponding object.  Return a raw value has it must look on the
        db.
        """
        Model = record.__class__
        # search the field type in the object or in a parent
        field_type = Model._fields[key]._type

        # handle the value regarding to the type
        if field_type == 'many2one':
            return getattr(record, key).id if getattr(record, key) else None
        elif field_type == 'reference':
            if not getattr(record, key):
                return None
            return str(getattr(record, key))
        elif field_type in ['one2many', 'many2many']:
            raise ParsingError(
                "unsupported field %s of type %s" % (key, field_type))
        else:
            return getattr(record, key)

    def populate_to_delete(self):
        """Create a list of all the records that whe should met in the update
        process. The records that are not encountered are deleted from the
        database in post_import."""

        # Fetch the data in id descending order to avoid depedendcy
        # problem when the corresponding recordds will be deleted:
        module_data = self.ModelData.search([
                ('module', '=', self.module),
                ], order=[('id', 'DESC')])
        return set(rec.fs_id for rec in module_data)

    def import_record(self, model, values, fs_id):
        module = self.module

        if not fs_id:
            raise ValueError("missing fs_id")

        if '.' in fs_id:
            module, fs_id = fs_id.split('.')
            if not self.fs2db.get(module, fs_id):
                raise ParsingError("%s.%s not found" % (module, fs_id))

        # Remove this record from the to_delete list.
        # This means that the corresponding record have been found.
        self.to_delete.discard(fs_id)

        if self.fs2db.exists(module, fs_id):
            if self.noupdate and self.module_state != 'to activate':
                return
            mdata = self.fs2db.get(module, fs_id)
            # Check if record has not been deleted
            if mdata.db_id is None:
                return
            if self.grouped:
                self.grouped_write[model].extend([mdata, values])
            else:
                self.write_records(model, mdata, values)
        else:
            if self.grouped:
                self.grouped_creations[model][fs_id] = values
            else:
                self.create_records(model, [values], [fs_id])

    def create_records(self, model, vlist, fs_ids):
        Model = self.pool.get(model)
        records = Model.create(vlist)
        for record, values, fs_id in zip(records, vlist, fs_ids):
            mdata = self.ModelData(
                fs_id=fs_id,
                model=model,
                module=self.module,
                db_id=record.id,
                field_names=tuple(values.keys()),
                noupdate=self.noupdate,
                )
            self.fs2db.set(self.module, fs_id, mdata)
            self.grouped_model_data.add(mdata)

    def write_records(self, model, *actions):
        Model = self.pool.get(model)
        records = Model.browse([r.db_id for r in actions[::2]])
        actions = iter(actions)
        to_update = []
        for record, mdata, values in zip(records, actions, actions):
            new_values = {}
            for field, value in values.items():
                new_value = self._clean_value(field, record)
                if new_value != value:
                    new_values[field] = new_value
            if new_values:
                to_update += [[record], values]
            if values.keys() - set(mdata.field_names):
                mdata.field_names = tuple(
                    set(mdata.field_names) | values.keys())
                self.grouped_model_data.add(mdata)
            if (self.module == mdata.module
                    and self.noupdate != mdata.noupdate):
                mdata.noupdate = self.noupdate
                self.grouped_model_data.add(mdata)
        if to_update:
            Model.write(*to_update)


def post_import(pool, module, to_delete):
    """
    Remove the records that are given in to_delete.
    """
    transaction = Transaction()
    mdata_delete = []
    ModelData = pool.get("ir.model.data")

    with inactive_records():
        mdata = ModelData.search([
            ('fs_id', 'in', to_delete),
            ('module', '=', module),
            ], order=[('id', 'DESC')])

    for mrec in mdata:
        model, db_id, fs_id = mrec.model, mrec.db_id, mrec.fs_id
        if db_id is None:
            mdata_delete.append(mrec)
            continue

        try:
            # Deletion of the record
            try:
                Model = pool.get(model)
            except KeyError:
                Model = None
            if Model:
                Model.delete([Model(db_id)])
                mdata_delete.append(mrec)
            else:
                logger.warning(
                    "could not delete %d@%s from %s.%s "
                    "because model no longer exists",
                    db_id, model, module, fs_id)
        except Exception as e:
            transaction.rollback()
            logger.warning(
                "could not delete %d@%s from %s.%s (%s).",
                db_id, model, module, fs_id, e)
            if 'active' in Model._fields:
                try:
                    Model.write([Model(db_id)], {
                            'active': False,
                            })
                except Exception as e:
                    transaction.rollback()
                    logger.error(
                        "could not deactivate %d@%s from %s.%s (%s)",
                        db_id, model, module, fs_id, e)
        else:
            logger.info(
                "deleted %s@%s from %s.%s", db_id, model, module, fs_id)
        transaction.commit()

    # Clean model_data:
    if mdata_delete:
        ModelData.delete(mdata_delete)
        transaction.commit()

    return True
