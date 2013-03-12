#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import time
from xml import sax
from decimal import Decimal
import datetime
import logging
import traceback
import sys
import re
from trytond.version import VERSION
from trytond.tools import safe_eval
from trytond.transaction import Transaction

CDATA_START = re.compile('^\s*\<\!\[cdata\[', re.IGNORECASE)
CDATA_END = re.compile('\]\]\>\s*$', re.IGNORECASE)

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
        cursor = Transaction().cursor

        values = {}

        self.xml_id = attributes['id']

        for attr in ('name', 'icon', 'sequence', 'parent', 'action', 'groups'):
            if attributes.get(attr):
                values[attr] = attributes.get(attr)

        if attributes.get('active'):
            values['active'] = bool(safe_eval(attributes['active']))

        if values.get('parent'):
            values['parent'] = self.mh.get_id(values['parent'])

        action_name = False
        if values.get('action'):
            action_id = self.mh.get_id(values['action'])

            # TODO maybe use a prefetch for this:
            cursor.execute(cursor.limit_clause(
            "SELECT a.name, a.type, v.type, v.field_childs, icon.name " \
            "FROM ir_action a " \
                "LEFT JOIN ir_action_report report ON (a.id = report.action) " \
                "LEFT JOIN ir_action_act_window act ON (a.id = act.action) " \
                "LEFT JOIN ir_action_wizard wizard ON (a.id = wizard.action) " \
                "LEFT JOIN ir_action_url url ON (a.id = url.action) " \
                "LEFT JOIN ir_action_act_window_view wv ON " \
                    "(act.id = wv.act_window) " \
                "LEFT JOIN ir_ui_view v ON (v.id = wv.view) " \
                "LEFT JOIN ir_ui_icon icon ON (a.icon = icon.id) " \
            "WHERE report.id = %s " \
                "OR act.id = %s " \
                "OR wizard.id = %s " \
                "OR url.id = %s " \
            "ORDER by wv.sequence", 1),
            (action_id, action_id, action_id, action_id))
            action_name, action_type, view_type, field_childs, icon_name = \
                    cursor.fetchone()

            values['action'] = '%s,%s' % (action_type, action_id)

            icon = attributes.get('icon', '')
            if icon:
                values['icon'] = icon
            elif icon_name:
                values['icon'] = icon_name
            elif action_type == 'ir.action.wizard':
                values['icon'] = 'tryton-executable'
            elif action_type == 'ir.action.report':
                values['icon'] = 'tryton-print'
            elif action_type == 'ir.action.act_window':
                if view_type == 'tree':
                    if field_childs:
                        values['icon'] = 'tryton-tree'
                    else:
                        values['icon'] = 'tryton-list'
                elif view_type == 'form':
                    values['icon'] = 'tryton-new'
                elif view_type == 'graph':
                    values['icon'] = 'tryton-graph'
                elif view_type == 'calendar':
                    values['icon'] = 'tryton-calendar'
            elif action_type == 'ir.action.url':
                values['icon'] = 'tryton-web-browser'
            else:
                values['icon'] = 'tryton-new'

        if values.get('groups'):
            raise Exception("Please use separate records for groups")

        if not values.get('name'):
            if not action_name:
                raise Exception("Please provide at least a 'name' attributes "
                        "or a 'action' attributes on the menuitem tags.")
            else:
                values['name'] = action_name

        self.values = values

    def characters(self, data):
        pass

    def endElement(self, name):
        """Must return the object to use for the next call """
        if name != "menuitem":
            return self
        else:
            self.mh.import_record( 'ir.ui.menu', self.values, self.xml_id)
            return None

    def current_state(self):
        return "Tag menuitem with id: %s"% \
               (self.xml_id)


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
            self.model = self.mh.pool.get(attributes["model"])
            assert self.model, "The model %s does not exist !" % \
                    (attributes["model"],)

            self.xml_id = attributes["id"]
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
            # Create a new entry in the values
            self.values[field_name] = ""
            # Remind the current name (see characters)
            self.current_field = field_name
            # Put a flag to escape cdata tags
            if field_type == "xml":
                self.cdata = "start"

            # Catch the known attributes
            search_attr = attributes.get('search','')
            ref_attr = attributes.get('ref', '')
            eval_attr = attributes.get('eval', '')

            if search_attr:
                search_model = self.model._columns[field_name].model_name
                f_obj = self.mh.pool.get(search_model)
                with Transaction().set_context(active_test=False):
                    self.values[field_name], = \
                            f_obj.search(safe_eval(search_attr))

            elif ref_attr:
                self.values[field_name] = self.mh.get_id(ref_attr)

            elif eval_attr:
                context = {}
                context['time'] = time
                context['version'] = VERSION.rsplit('.', 1)[0]
                context['ref'] = self.mh.get_id
                context['obj'] = lambda *a: 1
                self.values[field_name] = safe_eval(eval_attr, context)

        else:
            raise Exception("Tags '%s' not supported inside tag record." %
                    (name,))

    def characters(self, data):

        """If whe are in a field tag, consume all the content"""

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
                raise Exception("Application error"
                                "current_field expected to be set.")
            # Escape end cdata tag :
            if self.cdata in ('inside', 'start'):
                self.values[self.current_field] = \
                    CDATA_END.sub('', self.values[self.current_field])
                self.cdata = 'done'

                value = self.values[self.current_field]
                match = re.findall('[^%]%\((.*?)\)[ds]', value)
                xml_ids = {}
                for xml_id in match:
                    xml_ids[xml_id] = self.mh.get_id(xml_id)
                self.values[self.current_field] = value % xml_ids

            self.current_field = None
            return self

        elif name == "record":
            if self.xml_id in self.xml_ids and not self.update:
                raise Exception('Duplicate id: "%s".' % (self.xml_id,))
            self.mh.import_record(self.model._name, self.values, self.xml_id)
            self.xml_ids.append(self.xml_id)
            return None
        else:
            raise Exception("Unexpected closing tag '%s'"% (name,))

    def current_state(self):
        return "In tag record: model %s with id %s."% \
               (self.model and self.model._name or "?", self.xml_id)


# Custom exception:
class Unhandled_field(Exception):
    """
    Raised when a field type is not supported by the update mechanism.
    """
    pass

class Fs2bdAccessor:
    """
    Used in TrytondXmlHandler.
    Provide some helper function to ease cache access and management.
    """

    def __init__(self, modeldata_obj, pool):
        self.fs2db = {}
        self.fetched_modules = []
        self.modeldata_obj = modeldata_obj
        self.browserecord = {}
        self.pool = pool

    def get(self, module, fs_id):
        if module not in self.fetched_modules:
            self.fetch_new_module(module)
        return self.fs2db[module].get(fs_id, None)

    def get_browserecord(self, module, model_name, db_id):
        if module not in self.fetched_modules:
            self.fetch_new_module(module)
        if model_name in self.browserecord[module] \
                and db_id in self.browserecord[module][model_name]:
            return self.browserecord[module][model_name][db_id]
        return None

    def set(self, module, fs_id, values):
        """
        Whe call the prefetch function here to. Like that whe are sure
        not to erase data when get is called.
        """
        if not module in self.fetched_modules:
            self.fetch_new_module(module)
        if fs_id not in self.fs2db[module]:
            self.fs2db[module][fs_id] = {}
        fs2db_val = self.fs2db[module][fs_id]
        for key, val in values.items():
            fs2db_val[key] = val

    def reset_browsercord(self, module, model_name, ids=None):
        if module not in self.fetched_modules:
            return
        self.browserecord[module].setdefault(model_name, {})
        model_obj = self.pool.get(model_name)
        if not ids:
            object_ids = self.browserecord[module][model_name].keys()
        else:
            if isinstance(ids, (int, long)):
                object_ids = [ids]
            else:
                object_ids = ids
        models = model_obj.browse(object_ids)
        for model in models:
            if model.id in self.browserecord[module][model_name]:
                for cache in Transaction().cursor.cache.values():
                    for cache in (cache, cache.get('_language_cache',
                        {}).values()):
                        if model_name in cache \
                                and model.id in cache[model_name]:
                            cache[model_name][model.id] = {}
            self.browserecord[module][model_name][model.id] = model

    def fetch_new_module(self, module):
        cursor = Transaction().cursor
        self.fs2db[module] = {}
        module_data_ids = self.modeldata_obj.search([
                ('module', '=', module),
                ('inherit', '=', False),
                ], order=[('db_id', 'ASC')])

        record_ids = {}
        for rec in self.modeldata_obj.browse(module_data_ids):
            self.fs2db[rec.module][rec.fs_id] = {
                "db_id": rec.db_id, "model": rec.model,
                "id": rec.id, "values": rec.values
                }
            record_ids.setdefault(rec.model, [])
            record_ids[rec.model].append(rec.db_id)

        object_name_list = set(self.pool.object_name_list())

        self.browserecord[module] = {}
        for model_name in record_ids.keys():
            if model_name not in object_name_list:
                continue
            model_obj = self.pool.get(model_name)
            self.browserecord[module][model_name] = {}
            for i in range(0, len(record_ids[model_name]), cursor.IN_MAX):
                sub_record_ids = record_ids[model_name][i:i + cursor.IN_MAX]
                with Transaction().set_context(active_test=False):
                    ids = model_obj.search([
                        ('id', 'in', sub_record_ids),
                        ])
                models = model_obj.browse(ids)
                for model in models:
                    self.browserecord[module][model_name][model.id] = model
        self.fetched_modules.append(module)


class TrytondXmlHandler(sax.handler.ContentHandler):

    def __init__(self, pool, module,):
        "Register known taghandlers, and managed tags."
        sax.handler.ContentHandler.__init__(self)

        self.pool = pool
        self.module = module
        self.modeldata_obj = pool.get('ir.model.data')
        self.fs2db = Fs2bdAccessor(self.modeldata_obj, pool)
        self.to_delete = self.populate_to_delete()
        self.noupdate = None
        self.skip_data = False

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

        try:
            self.sax_parser.parse(source)
        except Exception:
            logging.getLogger("convert").error(
                "Error while parsing xml file:\n" +\
                    self.current_state()
                )

            raise
        return self.to_delete

    def startElement(self, name, attributes):
        """Rebind the current handler if necessary and call
        startElement on it"""

        if not self.taghandler:

            if  name in self.taghandlerlist:
                self.taghandler = self.taghandlerlist[name]
                self.taghandler.startElement(name, attributes)

            elif name == "data":
                self.noupdate = bool(int(attributes.get("noupdate", '0')))
                if self.pool.test and \
                        bool(int(attributes.get("skiptest", '0'))):
                    self.skip_data = True
                else:
                    self.skip_data = False

            elif name == "tryton":
                pass

            else:
                logging.getLogger("convert").info( "Tag %s not supported" %
                        name)
                return
        elif not self.skip_data:
            self.taghandler.startElement(name, attributes)

    def characters(self, data):
        if self.taghandler:
            self.taghandler.characters(data)

    def endElement(self, name):

        # Closing tag found, if we are in a delegation the handler
        # know what to do:
        if self.taghandler and not self.skip_data:
            self.taghandler = self.taghandler.endElement(name)

    def current_state(self):
        if self.taghandler:
            return self.taghandler.current_state()
        else:
            return ''

    def get_id(self, xml_id):

        if '.' in xml_id:
            module, xml_id = xml_id.split('.')
        else:
            module = self.module

        if self.fs2db.get(module, xml_id) is None:
            raise Exception("Reference to %s not found"% \
                                ".".join([module,xml_id]))
        return self.fs2db.get(module, xml_id)["db_id"]



    @staticmethod
    def _clean_value(key, browse_record, object_ref):
        """
        Take a field name, a browse_record, and a reference to the
        corresponding object.  Return a raw value has it must look on the
        db.
        """

        # search the field type in the object or in a parent
        if key in object_ref._columns:
            field_type = object_ref._columns[key]._type
        else:
            field_type = object_ref._inherit_fields[key][2]._type

        # handle the value regarding to the type
        if field_type == 'many2one':
            return browse_record[key] and browse_record[key].id or False
        elif field_type == 'reference':
            if not browse_record[key]:
                return False
            ref_mode, ref_id = browse_record[key].split(',', 1)
            try:
                ref_id = safe_eval(ref_id)
            except Exception:
                pass
            if isinstance(ref_id, (list, tuple)):
                ref_id = ref_id[0]
            return ref_mode + ',' + str(ref_id)
        elif field_type in ['one2many', 'many2many']:
            raise Unhandled_field("Unhandled field %s" % key)
        else:
            return browse_record[key]


    def populate_to_delete(self):
        """Create a list of all the records that whe should met in the update
        process. The records that are not encountered are deleted from the
        database in post_import."""

        # Fetch the data in id descending order to avoid depedendcy
        # problem when the corresponding recordds will be deleted:
        module_data_ids = self.modeldata_obj.search([
                ('module', '=', self.module),
                ('inherit', '=', False),
                ], order=[('id', 'DESC')])
        return set(rec.fs_id for rec in self.modeldata_obj.browse(
            module_data_ids))

    def import_record(self, model, values, fs_id):
        cursor = Transaction().cursor
        module = self.module

        if not fs_id:
            raise Exception('import_record : Argument fs_id is mandatory')

        if '.' in fs_id:
            assert len(fs_id.split('.')) == 2, '"%s" contains too many dots. '\
                    'file system ids should contain ot most one dot ! ' \
                    'These are used to refer to other modules data, ' \
                    'as in module.reference_id' % (fs_id)

            module, fs_id = fs_id.split('.')
            if not self.fs2db.get(module, fs_id):
                raise Exception('Reference to %s.%s not found' % \
                        (module, fs_id))

        object_ref = self.pool.get(model)
        translation_obj = self.pool.get('ir.translation')

        if self.fs2db.get(module, fs_id):

            # Remove this record from the to_delete list. This means that
            # the corresponding record have been found.
            if module == self.module and fs_id in self.to_delete:
                self.to_delete.remove(fs_id)

            if self.noupdate:
                return

            # this record is already in the db:
            # XXX maybe use only one call to get()
            db_id, db_model, mdata_id, old_values = \
                    [self.fs2db.get(module, fs_id)[x] for x in \
                    ["db_id","model","id","values"]]
            inherit_db_ids = {}
            inherit_mdata_ids = []

            if not old_values:
                old_values = {}
            else:
                old_values = safe_eval(old_values, {
                    'Decimal': Decimal,
                    'datetime': datetime,
                    })

            for key in old_values:
                if isinstance(old_values[key], str):
                    # Fix for migration to unicode
                    old_values[key] = old_values[key].decode('utf-8')

            if model != db_model:
                raise Exception("This record try to overwrite " \
                "data with the wrong model: %s (module: %s)" % (fs_id, module))

            #Re-create record if it was deleted
            if not self.fs2db.get_browserecord(module, object_ref._name, db_id):
                with Transaction().set_context(module=module):
                    db_id = object_ref.create(values)

                # reset_browsercord
                self.fs2db.reset_browsercord(module, object_ref._name, db_id)

                record = self.fs2db.get_browserecord(module, object_ref._name,
                        db_id)
                for table, field_name, field in \
                        object_ref._inherit_fields.values():
                    inherit_db_ids[table] = record[field_name].id

                #Add a translation record for field translatable
                for field_name in object_ref._columns.keys() + \
                        object_ref._inherit_fields.keys():
                    if field_name in object_ref._columns:
                        field = object_ref._columns[field_name]
                        table_name = object_ref._name
                        res_id = db_id
                    else:
                        field = object_ref._inherit_fields[field_name][2]
                        table_name = self.pool.get(
                                object_ref._inherit_fields[field_name][0])._name
                        res_id = inherit_db_ids[table_name]
                    if getattr(field, 'translate', False) and \
                            values.get(field_name):
                        cursor.execute('SELECT id FROM ir_translation ' \
                                'WHERE name = %s ' \
                                    'AND lang = %s ' \
                                    'AND type = %s ' \
                                    'AND res_id = %s ' \
                                    'AND module = %s',
                                (table_name + ',' + field_name,
                                    'en_US', 'model', res_id, module))
                        fetchone = cursor.fetchone()
                        src_md5 = translation_obj.get_src_md5(
                            values[field_name])
                        if fetchone:
                            trans_id = fetchone[0]
                            cursor.execute('UPDATE ir_translation '
                                'SET src = %s, src_md5 = %s, module = %s '
                                'WHERE id = %s',
                                (values[field_name], src_md5, module, trans_id))
                        else:
                            cursor.execute('INSERT INTO ir_translation '
                                '(name, lang, type, src, src_md5, res_id, '
                                    'value, module, fuzzy) '
                                'VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)',
                                (table_name + ',' + field_name, 'en_US',
                                    'model', values[field_name], src_md5,
                                    res_id, '', module, False))

                for table in inherit_db_ids.keys():
                    data_id = self.modeldata_obj.search([
                        ('fs_id', '=', fs_id),
                        ('module', '=', module),
                        ('model', '=', table),
                        ], limit=1)
                    if data_id:
                        self.modeldata_obj.write(data_id, {
                            'db_id': inherit_db_ids[table],
                            'inherit': True,
                            })
                    else:
                        data_id = self.modeldata_obj.create({
                            'fs_id': fs_id,
                            'module': module,
                            'model': table,
                            'db_id': inherit_db_ids[table],
                            'inherit': True,
                            })
                    inherit_mdata_ids.append((table, data_id))

                data_id = self.modeldata_obj.search([
                    ('fs_id', '=', fs_id),
                    ('module', '=', module),
                    ('model', '=', object_ref._name),
                    ], limit=1)[0]
                self.modeldata_obj.write(data_id, {
                    'db_id': db_id,
                    })
                self.fs2db.get(module, fs_id)["db_id"] = db_id

            db_val = self.fs2db.get_browserecord(module, object_ref._name,
                    db_id)
            if not db_val:
                db_val = object_ref.browse(db_id)

            to_update = {}
            for key in values:

                db_field = self._clean_value(key, db_val, object_ref)

                # if the fs value is the same has in the db, whe ignore it
                val = values[key]
                if isinstance(values[key], str):
                    # Fix for migration to unicode
                    val = values[key].decode('utf-8')
                if db_field == val:
                    continue

                # we cannot update a field if it was changed by a user...
                if key not in old_values:
                    if key in object_ref._columns:
                        expected_value = object_ref._defaults.get(
                            key, lambda *a: None)()
                    else:
                        inherit_obj = self.pool.get(
                            object_ref._inherit_fields[key][0])
                        expected_value = inherit_obj._defaults.get(
                            key, lambda *a: None)()
                else:
                    expected_value = old_values[key]

                # Migration from 2.0: Reference field change value
                if key in object_ref._columns:
                    field_type = object_ref._columns[key]._type
                else:
                    field_type = object_ref._inherit_fields[key][2]._type
                if field_type == 'reference':
                    if (expected_value and expected_value.endswith(',0')
                            and not db_field):
                        db_field = expected_value

                # ... and we consider that there is an update if the
                # expected value differs from the actual value, _and_
                # if they are not false in a boolean context (ie None,
                # False, {} or [])
                if db_field != expected_value and (db_field or expected_value):
                    logging.getLogger("convert").warning(
                        "Field %s of %s@%s not updated (id: %s), because "\
                        "it has changed since the last update"% \
                        (key, db_id, model, fs_id))
                    continue

                # so, the field in the fs and in the db are different,
                # and no user changed the value in the db:
                to_update[key] = values[key]

            # if there is values to update:
            if to_update:
                # write the values in the db:
                with Transaction().set_context(module=module):
                    object_ref.write(db_id, to_update)
                self.fs2db.reset_browsercord(module, object_ref._name, db_id)


            if not inherit_db_ids:
                record = object_ref.browse(db_id)
                for table, field_name, field in \
                        object_ref._inherit_fields.values():
                    inherit_db_ids[table] = record[field_name].id
            if not inherit_mdata_ids:
                for table in inherit_db_ids.keys():
                    data_id = self.modeldata_obj.search([
                        ('fs_id', '=', fs_id),
                        ('module', '=', module),
                        ('model', '=', table),
                        ], limit=1)
                    inherit_mdata_ids.append((table, data_id))

            #Update/Create translation record for field translatable
            if to_update:
                for field_name in object_ref._columns.keys() + \
                        object_ref._inherit_fields.keys():
                    if field_name in object_ref._columns:
                        field = object_ref._columns[field_name]
                        table_name = object_ref._name
                        res_id = db_id
                    else:
                        field = object_ref._inherit_fields[field_name][2]
                        table_name = self.pool.get(
                                object_ref._inherit_fields[field_name][0])._name
                        res_id = inherit_db_ids[table_name]
                    if getattr(field, 'translate', False):
                        cursor.execute('SELECT id FROM ir_translation ' \
                                'WHERE name = %s ' \
                                    'AND lang = %s ' \
                                    'AND type = %s ' \
                                    'AND res_id = %s ' \
                                    'AND module = %s',
                                (table_name + ',' + field_name,
                                    'en_US', 'model', res_id, module))
                        fetchone = cursor.fetchone()
                        if fetchone:
                            if to_update.get(field_name):
                                src_md5 = translation_obj.get_src_md5(
                                    to_update[field_name])
                                trans_id = fetchone[0]
                                cursor.execute('UPDATE ir_translation '
                                    'SET src = %s, src_md5 = %s, module = %s '
                                    'WHERE id = %s',
                                    (to_update[field_name], src_md5, module,
                                        trans_id))
                        elif values.get(field_name):
                            src_md5 = translation_obj.get_src_md5(
                                values[field_name])
                            cursor.execute('INSERT INTO ir_translation '
                                '(name, lang, type, src, src_md5, res_id, '
                                        'value, module, fuzzy) '
                                'VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)',
                                (table_name + ',' + field_name, 'en_US',
                                    'model', values[field_name], src_md5,
                                    res_id, '', module, False))

            if to_update:
                # re-read it: this ensure that we store the real value
                # in the model_data table:
                db_val = self.fs2db.get_browserecord(module, object_ref._name,
                        db_id)
                if not db_val:
                    db_val = object_ref.browse(db_id)
                for key in to_update:
                    values[key] = self._clean_value( key, db_val, object_ref)

            if module != self.module:
                temp_values = old_values.copy()
                temp_values.update(values)
                values = temp_values

            if values != old_values:
                self.modeldata_obj.write(mdata_id, {
                    'fs_id': fs_id,
                    'model': model,
                    'module': module,
                    'db_id': db_id,
                    'values': values,
                    'date_update': datetime.datetime.now(),
                    })
                for table, inherit_mdata_id in inherit_mdata_ids:
                    self.modeldata_obj.write(inherit_mdata_id, {
                        'fs_id': fs_id,
                        'model': table,
                        'module': module,
                        'db_id': inherit_db_ids[table],
                        'values': values,
                        'date_update': datetime.datetime.now(),
                        })
            # reset_browsercord to keep cache memory low
            self.fs2db.reset_browsercord(module, object_ref._name, db_id)

        else:
            # this record is new, create it in the db:
            with Transaction().set_context(module=module):
                db_id = object_ref.create(values)
            inherit_db_ids = {}

            record = object_ref.browse(db_id)
            for table, field_name, field in object_ref._inherit_fields.values():
                inherit_db_ids[table] = record[field_name].id

            #Add a translation record for field translatable
            for field_name in object_ref._columns.keys() + \
                    object_ref._inherit_fields.keys():
                if field_name in object_ref._columns:
                    field = object_ref._columns[field_name]
                    table_name = object_ref._name
                    res_id = db_id
                else:
                    field = object_ref._inherit_fields[field_name][2]
                    table_name = self.pool.get(
                            object_ref._inherit_fields[field_name][0])._name
                    res_id = inherit_db_ids[table_name]
                if getattr(field, 'translate', False) and \
                        values.get(field_name):
                    cursor.execute('SELECT id FROM ir_translation ' \
                            'WHERE name = %s' \
                                'AND lang = %s ' \
                                'AND type = %s ' \
                                'AND res_id = %s ' \
                                'AND module = %s',
                            (table_name + ',' + field_name,
                                'en_US', 'model', res_id, module))
                    trans_id = None
                    if cursor.rowcount == -1 or cursor.rowcount is None:
                        data = cursor.fetchone()
                        if data:
                            trans_id, = data
                    elif cursor.rowcount != 0:
                        trans_id, = cursor.fetchone()
                    src_md5 = translation_obj.get_src_md5(values[field_name]
                        or '')
                    if trans_id:
                        cursor.execute('UPDATE ir_translation '
                            'SET src = %s, src_md5 = %s, module = %s '
                            'WHERE id = %s',
                            (values[field_name], src_md5, module, trans_id))
                    else:
                        cursor.execute('INSERT INTO ir_translation '
                            '(name, lang, type, src, src_md5, res_id, '
                                'value, module, fuzzy) '
                            'VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)',
                            (table_name + ',' + field_name, 'en_US', 'model',
                                values[field_name], src_md5, res_id, '',
                                module, False))

            # re-read it: this ensure that we store the real value
            # in the model_data table:
            db_val = object_ref.browse(db_id)
            for key in values:
                values[key] = self._clean_value(key, db_val, object_ref)

            for table in inherit_db_ids.keys():
                self.modeldata_obj.create({
                    'fs_id': fs_id,
                    'model': table,
                    'module': module,
                    'db_id': inherit_db_ids[table],
                    'values': str(values),
                    'inherit': True,
                    'noupdate': self.noupdate,
                    })

            mdata_id = self.modeldata_obj.create({
                'fs_id': fs_id,
                'model': model,
                'module': module,
                'db_id': db_id,
                'values': str(values),
                'noupdate': self.noupdate,
                })

            # update fs2db:
            self.fs2db.set(module, fs_id, {
                    "db_id": db_id, "model": model,
                    "id": mdata_id, "values": str(values)})
            self.fs2db.reset_browsercord(module, model, db_id)

def post_import(pool, module, to_delete):
    """
    Remove the records that are given in to_delete.
    """
    cursor = Transaction().cursor
    mdata_delete = []
    modeldata_obj = pool.get("ir.model.data")
    transition_delete = []

    with Transaction().set_context(active_test=False):
        mdata_ids = modeldata_obj.search([
            ('fs_id', 'in', to_delete),
            ('module', '=', module),
            ], order=[('id', 'DESC')])

    object_name_list = set(pool.object_name_list())
    for mrec in modeldata_obj.browse(mdata_ids):
        mdata_id, model, db_id = mrec.id, mrec.model, mrec.db_id

        # Whe skip transitions, they will be deleted with the
        # corresponding activity:
        if model == 'workflow.transition':
            transition_delete.append((mdata_id, db_id))
            continue

        if model == 'workflow.activity':

            wkf_todo = []
            # search for records that are in the state/activity that
            # we want to delete...
            cursor.execute('SELECT res_type, res_id ' \
                    'FROM wkf_instance ' \
                    'WHERE id IN (' \
                        'SELECT instance FROM wkf_workitem ' \
                        'WHERE activity = %s)', (db_id,))
            #... connect the transitions backward...
            wkf_todo.extend(cursor.fetchall())
            cursor.execute("UPDATE wkf_transition " \
                    'SET condition = \'True\', "group" = NULL, ' \
                        "signal = NULL, act_to = act_from, " \
                        "act_from = %s " \
                    "WHERE act_to = %s", (db_id, db_id))
            # ... and force the record to follow them:
            for wkf_model, wkf_model_id in wkf_todo:
                model_obj = pool.get(wkf_model)
                #XXX must perhaps use workflow_trigger_trigger?
                model_obj.workflow_trigger_write(wkf_model_id)

            # Collect the ids of these transition in model_data
            cursor.execute(
                "SELECT md.id FROM ir_model_data md " \
                    "JOIN wkf_transition t ON "\
                    "(md.model='workflow.transition' and md.db_id=t.id)" \
                    "WHERE t.act_to = %s", (db_id,))
            mdata_delete.extend([x[0] for x in cursor.fetchall()])

            # And finally delete the transitions
            cursor.execute("DELETE FROM wkf_transition " \
                    "WHERE act_to = %s", (db_id,))


        logging.getLogger("convert").info(
                'Deleting %s@%s' % (db_id, model))
        try:
            # Deletion of the record
            if model in object_name_list:
                model_obj = pool.get(model)
                model_obj.delete(db_id)
                mdata_delete.append(mdata_id)
            else:
                logging.getLogger("convert").warning(
                        'Could not delete id %d of model %s because model no '
                        'longer exists.' % (db_id, model))
            cursor.commit()
        except Exception:
            cursor.rollback()
            tb_s = reduce(lambda x, y: x + y,
                    traceback.format_exception(*sys.exc_info()))
            logging.getLogger("convert").error(
                'Could not delete id: %d of model %s\n'
                    'There should be some relation '
                    'that points to this resource\n'
                    'You should manually fix this '
                    'and restart --update=module\n'
                    'Exception: %s' %
                    (db_id, model, tb_s.decode('utf-8', 'ignore')))

    transition_obj = pool.get('workflow.transition')
    for mdata_id, db_id in transition_delete:
        logging.getLogger("convert").info(
            'Deleting %s@workflow.transition' % (db_id,))
        try:
            transition_obj.delete(db_id)
            mdata_delete.append(mdata_id)
            cursor.commit()
        except Exception:
            cursor.rollback()
            logging.getLogger("convert").error(
                'Could not delete id: %d of model workflow.transition' %
                (db_id,))

    # Clean model_data:
    if mdata_delete:
        modeldata_obj.delete(mdata_delete)
        cursor.commit()

    return True
