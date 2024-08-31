/* This file is part of Tryton.  The COPYRIGHT file at the top level of
   this repository contains the full copyright notices and license terms. */
(function() {
    'use strict';

    function get_x2m_sub_fields(f_attrs, prefix) {
        if (f_attrs.loading == 'eager' && f_attrs.views) {
            // There's only one key but we don't know its value
            const [[, view],] = Object.entries(f_attrs.views);

            const sub_fields = view.fields || {};
            const x2m_sub_fields = [];

            for (const [s_field, f_def] of Object.entries(sub_fields)) {
                x2m_sub_fields.push(`${prefix}.${s_field}`);

                var type_ = f_def.type;
                if (['many2one', 'one2one', 'reference'].includes(type_)) {
                    x2m_sub_fields.push(`${prefix}.${s_field}.rec_name`);
                } else if (['selection', 'multiselection'].includes(type_)) {
                    x2m_sub_fields.push(`${prefix}.${s_field}:string`);
                } else if (['one2many', 'many2many'].includes(type_)) {
                    x2m_sub_fields.push(
                        ...get_x2m_sub_fields(f_def, `${prefix}.${s_field}`)
                    );
                }
            }

            x2m_sub_fields.push(
                `${prefix}._timestamp`,
                `${prefix}._write`,
                `${prefix}._delete`);
            return x2m_sub_fields;
        } else {
            return [];
        }
    }

    Sao.Model = Sao.class_(Object, {
        init: function(name, attributes) {
            attributes = attributes || {};
            this.name = name;
            this.session = Sao.Session.current_session;
            this.fields = {};
        },
        add_fields: function(descriptions) {
            var added = [];
            for (var name in descriptions) {
                var desc = descriptions[name];
                if (!(name in this.fields)) {
                    var Field = Sao.field.get(desc.type);
                    this.fields[name] = new Field(desc);
                    added.push(name);
                } else {
                    jQuery.extend(this.fields[name].description, desc);
                }
            }
            return added;
        },
        execute: function(
                method, params, context={}, async=true,
                process_exception=true) {
            var args = {
                'method': 'model.' + this.name + '.' + method,
                'params': params.concat(context)
            };
            return Sao.rpc(args, this.session, async, process_exception);
        },
        copy: function(records, context) {
            if (jQuery.isEmptyObject(records)) {
                return jQuery.when();
            }
            var record_ids = records.map(function(record) {
                return record.id;
            });
            return this.execute('copy', [record_ids, {}], context);
        }
    });

    Sao.Group = function(model, context, array) {
        array.prm = jQuery.when();
        array.model = model;
        array._context = context;
        array.on_write = [];
        array.parent = undefined;
        array.screens = [];
        array.parent_name = '';
        array.children = [];
        array.child_name = '';
        array.parent_datetime_field = undefined;
        array.record_removed = [];
        array.record_deleted = [];
        array.__readonly = false;
        array.exclude_field = null;
        array.skip_model_access = false;
        array.forEach(function(e, i, a) {
            e.group = a;
        });
        Object.defineProperty(array, 'readonly', {
            get: function() {
                // Must skip res.user for Preference windows
                var access = Sao.common.MODELACCESS.get(this.model.name);
                if (this.context._datetime ||
                    (!(access.write || access.create) &&
                        !this.skip_model_access)) {
                    return true;
                }
                return this.__readonly;
            },
            set: function(value) {
                this.__readonly = value;
            }
        });
        array.load = function(ids, modified=false, position=-1, preloaded=null) {
            if (position == -1) {
                position = this.length;
            }
            var new_records = [];
            for (const id of ids) {
                let new_record = this.get(id);
                if (!new_record) {
                    new_record = new Sao.Record(this.model, id);
                    new_record.group = this;
                    this.splice(position, 0, new_record);
                    position += 1;
                }
                if (preloaded && (id in preloaded)) {
                    new_record.set(preloaded[id], false, false);
                }
                new_records.push(new_record);
            }
            // Remove previously removed or deleted records
            var record_removed = [];
            for (const record of this.record_removed) {
                if (!~ids.indexOf(record.id)) {
                    record_removed.push(record);
                }
            }
            this.record_removed = record_removed;
            var record_deleted = [];
            for (const record of this.record_deleted) {
                if (!~ids.indexOf(record.id)) {
                    record_deleted.push(record);
                }
            }
            this.record_deleted = record_deleted;
            if (new_records.length && modified) {
                for (const record of new_records) {
                    record.modified_fields.id = true;
                }
                this.record_modified();
            }
        };
        array.get = function(id) {
            // TODO optimize
            for (const record of this) {
                if (record.id == id) {
                    return record;
                }
            }
        };
        array.new_ = function(default_, id, defaults=null) {
            var record = new Sao.Record(this.model, id);
            record.group = this;
            if (default_) {
                record.default_get(defaults);
            }
            return record;
        };
        array.add = function(record, position=-1, modified=true) {
            if (position == -1) {
                position = this.length;
            }
            position = Math.min(position, this.length);
            if (record.group != this) {
                record.group = this;
            }
            if (this.indexOf(record) < 0) {
                this.splice(position, 0, record);
            }
            for (var record_rm of this.record_removed) {
                if (record_rm.id == record.id) {
                    this.record_removed.splice(
                            this.record_removed.indexOf(record_rm), 1);
                }
            }
            for (var record_del of this.record_deleted) {
                if (record_del.id == record.id) {
                    this.record_deleted.splice(
                            this.record_deleted.indexOf(record_del), 1);
                }
            }
            record.modified_fields.id = true;
            if (modified) {
                // Set parent field to trigger on_change
                if (this.parent && this.model.fields[this.parent_name]) {
                    var field = this.model.fields[this.parent_name];
                    if ((field instanceof Sao.field.Many2One) ||
                            field instanceof Sao.field.Reference) {
                        var value = [this.parent.id, ''];
                        if (field instanceof Sao.field.Reference) {
                            value = [this.parent.model.name, value];
                        }
                        field.set_client(record, value);
                    }
                }
            }
            return record;
        };
        array.remove = function(
            record, remove, force_remove=false, modified=true) {
            if (record.id >= 0) {
                if (remove) {
                    if (~this.record_deleted.indexOf(record)) {
                        this.record_deleted.splice(
                                this.record_deleted.indexOf(record), 1);
                    }
                    if (!~this.record_removed.indexOf(record)) {
                        this.record_removed.push(record);
                    }
                } else {
                    if (~this.record_removed.indexOf(record)) {
                        this.record_removed.splice(
                                this.record_removed.indexOf(record), 1);
                    }
                    if (!~this.record_deleted.indexOf(record)) {
                        this.record_deleted.push(record);
                    }
                }
            }
            record.modified_fields.id = true;
            if ((record.id < 0) || force_remove) {
                this._remove(record);
            }
            if (modified) {
                this.record_modified();
            }
        };
        array._remove = function(record) {
            var idx = this.indexOf(record);
            this.splice(idx, 1);
        };
        array.unremove = function(record) {
            this.record_removed.splice(this.record_removed.indexOf(record), 1);
            this.record_deleted.splice(this.record_deleted.indexOf(record), 1);
            record.group.record_modified();
        };
        array.clear = function() {
            this.splice(0, this.length);
            this.record_removed = [];
            this.record_deleted = [];
        };
        array.record_modified = function() {
            if (!this.parent) {
                for (const screen of this.screens) {
                    screen.record_modified();
                }
            } else {
                this.parent.modified_fields[this.child_name] = true;
                this.parent.model.fields[this.child_name].changed(this.parent);
                this.parent.validate(null, true, false, true);
                this.parent.group.record_modified();
            }
        };
        array.record_notify = function(notifications) {
            for (const screen of this.screens) {
                screen.record_notify(notifications);
            }
        };
        array.delete_ = function(records) {
            if (jQuery.isEmptyObject(records)) {
                return jQuery.when();
            }
            var root_group = this.root_group;
            Sao.Logger.assert(records.every(
                r => r.model.name == this.model.name),
                'records not from the same model');
            Sao.Logger.assert(records.every(
                r =>  r.group.root_group == root_group),
                'records not from the same root group');
            records = records.filter(record => record.id >= 0);
            var context = this.context;
            context._timestamp = {};
            for (const record of records) {
                jQuery.extend(context._timestamp, record.get_timestamp());
            }
            var record_ids = records.map(function(record) {
                return record.id;
            });
            return root_group.on_write_ids(record_ids).then(reload_ids => {
                for (const record of records) {
                    record.destroy();
                }
                reload_ids = reload_ids.filter(e => !~record_ids.indexOf(e));
                return this.model.execute('delete', [record_ids], context)
                .then(() => {
                    root_group.reload(reload_ids);
                });
            });
        };
        Object.defineProperty(array, 'root_group', {
            get: function() {
                var root = this;
                var parent = this.parent;
                while (parent) {
                    root = parent.group;
                    parent = parent.parent;
                }
                return root;
            }
        });
        array.save = function() {
            var deferreds = [];
            this.forEach(record => {
                deferreds.push(record.save());
            });
            if (!jQuery.isEmptyObject(this.record_deleted)) {
                for (const record of this.record_deleted) {
                    this._remove(record);
                }
                deferreds.push(this.delete_(this.record_deleted));
                this.record_deleted.splice(0, this.record_deleted.length);
            }
            return jQuery.when.apply(jQuery, deferreds);
        };
        array.written = function(ids) {
            if (typeof(ids) == 'number') {
                ids = [ids];
            }
            return this.on_write_ids(ids).then(to_reload => {
                to_reload = to_reload.filter(e => !~ids.indexOf(e));
                this.root_group.reload(to_reload);
            });
        };
        array.reload = function(ids) {
            for (const child of this.children) {
                child.reload(ids);
            }
            for (const id of ids) {
                const record = this.get(id);
                if (record && jQuery.isEmptyObject(record.modified_fields)) {
                    record.cancel();
                }
            }
        };
        array.on_write_ids = function(ids) {
            var deferreds = [];
            var result = [];
            this.on_write.forEach(fnct => {
                var prm = this.model.execute(fnct, [ids], this._context)
                .then(res => {
                    jQuery.extend(result, res);
                });
                deferreds.push(prm);
            });
            return jQuery.when.apply(jQuery, deferreds).then(
                () => result.filter((e, i, a) =>  i == a.indexOf(e)));
        };
        array.set_parent = function(parent) {
            this.parent = parent;
            if (parent && parent.model.name == this.model.name) {
                this.parent.group.children.push(this);
            }
        };
        array.add_fields = function(fields) {
            var added = this.model.add_fields(fields);
            if (jQuery.isEmptyObject(this)) {
                return;
            }
            var new_ = [];
            for (const record of this) {
                if (record.id < 0) {
                    new_.push(record);
                }
            }
            if (new_.length && added.length) {
                this.model.execute('default_get', [added, this.context])
                    .then(values => {
                        for (const record of new_) {
                            record.set_default(values, true, false);
                        }
                        this.record_modified();
                    });
            }
        };
        array.destroy = function() {
            if (this.parent) {
                var i = this.parent.group.children.indexOf(this);
                if (~i) {
                    this.parent.group.children.splice(i, 1);
                }
            }
            this.parent = null;
        };
        Object.defineProperty(array, 'domain', {
            get: function() {
                var domain = [];
                for (const screen of this.screens) {
                    if (screen.attributes.domain) {
                        domain.push(screen.attributes.domain);
                    }
                }
                if (this.parent && this.child_name) {
                    var field = this.parent.model.fields[this.child_name];
                    return [domain, field.get_domain(this.parent)];
                } else {
                    return domain;
                }
            }
        });
        Object.defineProperty(array, 'context', {
            get: function() {
                return this._get_context();
            },
            set: function(context) {
                this._context = jQuery.extend({}, context);
            }
        });
        Object.defineProperty(array, 'local_context', {
            get: function() {
                return this._get_context(true);
            }
        });
        array._get_context = function(local) {
            var context;
            if (!local) {
                context = jQuery.extend({}, this.model.session.context);
            } else {
                context = {};
            }
            if (this.parent) {
                var parent_context = this.parent.get_context(local);
                jQuery.extend(context, parent_context);
                if (this.child_name in this.parent.model.fields) {
                    var field = this.parent.model.fields[this.child_name];
                    jQuery.extend(context, field.get_context(
                        this.parent, parent_context, local));
                }
            }
            jQuery.extend(context, this._context);
            if (this.parent_datetime_field) {
                context._datetime = this.parent.get_eval()[
                    this.parent_datetime_field];
            }
            return context;
        };
        array.clean4inversion = function(domain) {
            if (jQuery.isEmptyObject(domain)) {
                return [];
            }
            var inversion = new Sao.common.DomainInversion();
            var head = domain[0];
            var tail = domain.slice(1);
            if (~['AND', 'OR'].indexOf(head)) {
                // pass
            } else if (inversion.is_leaf(head)) {
                var field = head[0];
                if ((field in this.model.fields) &&
                        (this.model.fields[field].description.readonly)) {
                    head = [];
                }
            } else {
                head = this.clean4inversion(head);
            }
            return [head].concat(this.clean4inversion(tail));
        };
        array.domain4inversion = function() {
            var domain = this.domain;
            if (!this.__domain4inversion ||
                    !Sao.common.compare(this.__domain4inversion[0], domain)) {
                this.__domain4inversion = [domain, this.clean4inversion(domain)];
            }
            return this.__domain4inversion[1];
        };
        array.get_by_path = function(path) {
            path = jQuery.extend([], path);
            var record = null;
            var group = this;

            var browse_child = function() {
                if (jQuery.isEmptyObject(path)) {
                    return record;
                }
                var child_name = path[0][0];
                var id = path[0][1];
                path.splice(0, 1);
                record = group.get(id);
                if (!record) {
                    return null;
                }
                if (!child_name) {
                    return browse_child();
                }
                return record.load(child_name).then(function() {
                    group = record._values[child_name];
                    if (!group) {
                        return null;
                    }
                    return browse_child();
                });
            };
            return jQuery.when().then(browse_child);
        };
        array.set_sequence = function(field, position) {
            var changed = false;
            var prev = null;
            var index, update, value, cmp;
            if (position === 0) {
                cmp = function(a, b) { return a > b; };
            } else {
                cmp = function(a, b) { return a < b; };
            }
            for (const record of this) {
                if (record.get_loaded([field]) || changed || record.id < 0) {
                    if (prev) {
                        index = prev.field_get(field);
                    } else {
                        index = null;
                    }
                    update = false;
                    value = record.field_get(field);
                    if (value === null) {
                        if (index) {
                            update = true;
                        } else if (prev) {
                            if (record.id >= 0) {
                                update = cmp(record.id, prev.id);
                            } else if (position === 0) {
                                update = true;
                            }
                        }
                    } else if (value === index) {
                        if (prev) {
                            if (record.id >= 0) {
                                update = cmp(record.id, prev.id);
                            } else if (position === 0) {
                                update = true;
                            }
                        }
                    } else if (value <= (index || 0)) {
                        update = true;
                    }
                    if (update) {
                        if (index === null) {
                            index = 0;
                        }
                        index += 1;
                        record.field_set_client(field, index);
                        changed = record;
                    }
                }
                prev = record;
            }
        };
        return array;
    };

    Sao.Record = Sao.class_(Object, {
        id_counter: -1,
        init: function(model, id=null) {
            this.model = model;
            this.group = Sao.Group(model, {}, []);
            if (id === null) {
                this.id = Sao.Record.prototype.id_counter;
            } else {
                this.id = id;
            }
            if (this.id < 0) {
                Sao.Record.prototype.id_counter--;
            }
            this._values = {};
            this.modified_fields = {};
            this._loaded = {};
            this.fields = {};
            this._timestamp = null;
            this._write = true;
            this._delete = true;
            this.resources = null;
            this.button_clicks = {};
            this.links_counts = {};
            this.state_attrs = {};
            this.autocompletion = {};
            this.exception = false;
            this.destroyed = false;
        },
        get modified() {
            if (!jQuery.isEmptyObject(this.modified_fields)) {
                Sao.Logger.info(
                    "Modified fields of %s@%s", this.id, this.model.name,
                    Object.keys(this.modified_fields));
                return true;
            } else {
                return false;
            }
        },
        save: function(force_reload=false) {
            var context = this.get_context();
            var prm = jQuery.when();
            if ((this.id < 0) || this.modified) {
                var values = this.get();
                if (this.id < 0) {
                    // synchronous call to avoid multiple creation
                    try {
                        this.id = this.model.execute(
                            'create', [[values]], context,  false)[0];
                    } catch (e) {
                        if (e.promise) {
                            return e.then(() => this.save(force_reload));
                        } else {
                            return jQuery.Deferred().reject();
                        }
                    }
                } else {
                    if (!jQuery.isEmptyObject(values)) {
                        context._timestamp = this.get_timestamp();
                        prm = this.model.execute('write', [[this.id], values],
                            context);
                    }
                }
                prm = prm.done(() => {
                    this.cancel();
                    if (force_reload) {
                        return this.reload();
                    }
                });
                if (this.group) {
                    prm = prm.done(() => this.group.written(this.id));
                }
            }
            if (this.group.parent) {
                delete this.group.parent.modified_fields[this.group.child_name];
                prm = prm.done(() => this.group.parent.save(force_reload));
            }
            return prm;
        },
        reload: function(fields) {
            if (this.id < 0) {
                return jQuery.when();
            }
            if (!fields) {
                return this.load('*');
            } else {
                var prms = fields.map(field => this.load(field));
                return jQuery.when.apply(jQuery, prms);
            }
        },
        is_loaded: function(name) {
            return ((this.id < 0) || (name in this._loaded));
        },
        load: function(name, async=true, process_exception=true) {
            var fname;
            if (this.destroyed || this.is_loaded(name)) {
                if (async) {
                    return jQuery.when();
                } else if (name !== '*') {
                    return this.model.fields[name];
                } else {
                    return;
                }
            }
            if (async && this.group.prm.state() == 'pending') {
                return this.group.prm.then(() => this.load(name));
            }
            var id2record = {};
            id2record[this.id] = this;
            var loading, views, field;
            if (name == '*') {
                loading = 'eager';
                views = new Set();
                for (fname in this.model.fields) {
                    field = this.model.fields[fname];
                    if ((field.description.loading || 'eager') == 'lazy') {
                        loading = 'lazy';
                    }
                    for (const view of field.views) {
                        views.add(view);
                    }
                }
            } else {
                loading = this.model.fields[name].description.loading || 'eager';
                views = this.model.fields[name].views;
            }
            var fields = {};
            var views_operator;
            if (loading == 'eager') {
                for (fname in this.model.fields) {
                    field = this.model.fields[fname];
                    if ((field.description.loading || 'eager') == 'eager') {
                        fields[fname] = field;
                    }
                }
                views_operator = views.isSubsetOf.bind(views);
            } else {
                fields = this.model.fields;
                views_operator = function(view) {
                    return Boolean(this.intersection(view).size);
                }.bind(views);
            }
            var fnames = [];
            for (fname in fields) {
                field = fields[fname];
                if (!(fname in this._loaded) &&
                    (!views.size ||
                        views_operator(new Set(field.views)))) {
                    fnames.push(fname);
                }
            }
            var related_read_limit = null;
            var fnames_to_fetch = fnames.slice();
            var rec_named_fields = ['many2one', 'one2one', 'reference'];
            const selection_fields = ['selection', 'multiselection'];
            for (const fname of fnames) {
                var fdescription = this.model.fields[fname].description;
                if (~rec_named_fields.indexOf(fdescription.type))
                    fnames_to_fetch.push(fname + '.rec_name');
                else if (~selection_fields.indexOf(fdescription.type) &&
                    ((fdescription.loading || 'lazy') == 'eager')) {
                    fnames_to_fetch.push(fname + ':string');
                } else if (
                    ['many2many', 'one2many'].includes(fdescription.type)) {
                    var sub_fields = get_x2m_sub_fields(fdescription, fname);
                    fnames_to_fetch = [ ...fnames_to_fetch, ...sub_fields];
                    if (sub_fields.length > 0) {
                        related_read_limit = Sao.config.display_size;
                    }
                }
            }
            if (!~fnames.indexOf('rec_name')) {
                fnames_to_fetch.push('rec_name');
            }
            fnames_to_fetch.push('_timestamp');
            fnames_to_fetch.push('_write');
            fnames_to_fetch.push('_delete');

            var context = jQuery.extend({}, this.get_context());
            if (related_read_limit) {
                context.related_read_limit = related_read_limit;
            }
            if (loading == 'eager') {
                var limit = Math.trunc(Sao.config.limit /
                    Math.min(fnames_to_fetch.length, 10));

                const filter_group = record => {
                    return (!record.destroyed &&
                        (record.id >= 0) &&
                        !(name in record._loaded));
                };
                const filter_parent_group = record => {
                    return (filter_group(record) &&
                            (id2record[record.id] === undefined) &&
                            ((record.group === this.group) ||
                             // Don't compute context for same group
                             (JSON.stringify(record.get_context()) ===
                              JSON.stringify(context))));
                };
                var group, filter;
                if (this.group.parent &&
                        (this.group.parent.model.name == this.model.name)) {
                    group = [];
                    group = group.concat.apply(
                            group, this.group.parent.group.children);
                    filter = filter_parent_group;
                } else {
                    group = this.group;
                    filter = filter_group;
                }
                var idx = group.indexOf(this);
                if (~idx) {
                    var length = group.length;
                    var n = 1;
                    while ((Object.keys(id2record).length < limit) &&
                        ((idx - n >= 0) || (idx + n < length)) &&
                        (n < 2 * limit)) {
                            var record;
                            if (idx - n >= 0) {
                                record = group[idx - n];
                                if (filter(record)) {
                                    id2record[record.id] = record;
                                }
                            }
                            if (idx + n < length) {
                                record = group[idx + n];
                                if (filter(record)) {
                                    id2record[record.id] = record;
                                }
                            }
                            n++;
                        }
                }
            }

            for (fname in this.model.fields) {
                if ((this.model.fields[fname].description.type == 'binary') &&
                        ~fnames_to_fetch.indexOf(fname, fnames_to_fetch)) {
                    context[this.model.name + '.' + fname] = 'size';
                }
            }
            var result = this.model.execute('read', [
                Object.keys(id2record).map( e => parseInt(e, 10)),
                fnames_to_fetch], context, async, process_exception);
            const succeed = (values, exception=false) => {
                var id2value = {};
                for (const e of values) {
                    id2value[e.id] = e;
                }
                for (var id in id2record) {
                    var record = id2record[id];
                    if (!record.exception) {
                        record.exception = exception;
                    }
                    var value = id2value[id];
                    if (record && value) {
                        for (var key in this.modified_fields) {
                            delete value[key];
                        }
                        record.set(value, false);
                    }
                }
            };
            const failed = () => {
                var failed_values = [];
                var default_values;
                for (var id in id2record) {
                    default_values = {
                        id: id
                    };
                    for (const fname of fnames_to_fetch) {
                        if (fname != 'id') {
                            default_values[fname] = null;
                        }
                    }
                    failed_values.push(default_values);
                }
                return succeed(failed_values, true);
            };
            if (async) {
                this.group.prm = result.then(succeed, failed);
                return this.group.prm;
            } else {
                if (result) {
                    succeed(result);
                } else {
                    failed();
                }
                if (name !== '*') {
                    return this.model.fields[name];
                } else {
                    return;
                }
            }
        },
        set: function(values, modified=true, validate=true) {
            var name, value;
            var later = {};
            var fieldnames = [];
            for (name in values) {
                value = values[name];
                if (name == '_timestamp') {
                    // Always keep the older timestamp
                    if (!this._timestamp) {
                        this._timestamp = value;
                    }
                    continue;
                }
                if (name == '_write' || name == '_delete') {
                    this[name] = value;
                    continue;
                }
                if (!(name in this.model.fields)) {
                    if (name == 'rec_name') {
                        this._values[name] = value;
                    }
                    continue;
                }
                if (this.model.fields[name] instanceof Sao.field.One2Many) {
                    later[name] = value;
                    continue;
                }
                const field = this.model.fields[name];
                var related;
                if ((field instanceof Sao.field.Many2One) ||
                        (field instanceof Sao.field.Reference)) {
                    related = name + '.';
                    this._values[related] = values[related] || {};
                } else if ((field instanceof Sao.field.Selection) ||
                    (field instanceof Sao.field.MultiSelection)) {
                    related = name + ':string';
                    if (name + ':string' in values) {
                        this._values[related] = values[related];
                    } else {
                        delete this._values[related];
                    }
                }
                this.model.fields[name].set(this, value);
                this._loaded[name] = true;
                fieldnames.push(name);
            }
            for (name in later) {
                value = later[name];
                this.model.fields[name].set(this, value, false, values[`${name}.`]);
                this._loaded[name] = true;
                fieldnames.push(name);
            }
            if (validate) {
                this.validate(fieldnames, true, false, false);
            }
            if (modified) {
                this.set_modified();
            }
        },
        get: function() {
            var value = {};
            for (var name in this.model.fields) {
                var field = this.model.fields[name];
                if (field.description.readonly &&
                        !((field instanceof Sao.field.One2Many) &&
                            !(field instanceof Sao.field.Many2Many))) {
                    continue;
                }
                if ((this.modified_fields[name] === undefined) && this.id >= 0) {
                    continue;
                }
                value[name] = field.get(this);
                // Sending an empty x2MField breaks ModelFieldAccess.check
                if ((field instanceof Sao.field.One2Many) &&
                        (value[name].length === 0)) {
                    delete value[name];
                }
            }
            return value;
        },
        invalid_fields: function() {
            var fields = {};
            for (var fname in this.model.fields) {
                var field = this.model.fields[fname];
                var invalid = field.get_state_attrs(this).invalid;
                if (invalid) {
                    fields[fname] = invalid;
                }
            }
            return fields;
        },
        get_context: function(local) {
            if (!local) {
                return this.group.context;
            } else {
                return this.group.local_context;
            }
        },
        field_get: function(name) {
            return this.model.fields[name].get(this);
        },
        field_set: function(name, value) {
            this.model.fields[name].set(this, value);
        },
        field_get_client: function(name) {
            return this.model.fields[name].get_client(this);
        },
        field_set_client: function(name, value, force_change) {
            this.model.fields[name].set_client(this, value, force_change);
        },
        default_get: function(defaults=null) {
            if (!jQuery.isEmptyObject(this.model.fields)) {
                var context = this.get_context();
                if (defaults) {
                    for (const name in defaults) {
                        Sao.setdefault(context, `default_${name}` ,defaults[name]);
                    }
                }
                var prm = this.model.execute('default_get',
                        [Object.keys(this.model.fields)], context);
                return prm.then(values => {
                    if (this.group.parent &&
                            this.group.parent_name in this.group.model.fields) {
                        var parent_field =
                            this.group.model.fields[this.group.parent_name];
                        if (parent_field instanceof Sao.field.Reference) {
                            values[this.group.parent_name] = [
                                this.group.parent.model.name,
                                this.group.parent.id];
                        } else if (parent_field.description.relation ==
                                this.group.parent.model.name) {
                            values[this.group.parent_name] =
                                this.group.parent.id;
                        }
                    }
                    return this.set_default(values);
                });
            }
            return jQuery.when();
        },
        set_default: function(values, validate=true, modified=true) {
            var promises = [];
            var fieldnames = [];
            for (var fname in values) {
                if ((fname == '_write') ||
                    (fname == '_delete') ||
                    (fname == '_timestamp')) {
                    this[fname] = values[fname];
                    continue;
                }
                var value = values[fname];
                if (!(fname in this.model.fields)) {
                    continue;
                }
                if (fname == this.group.exclude_field) {
                    continue;
                }
                if ((this.model.fields[fname] instanceof Sao.field.Many2One) ||
                        (this.model.fields[fname] instanceof Sao.field.Reference)) {
                    var related = fname + '.';
                    this._values[related] = values[related] || {};
                }
                promises.push(this.model.fields[fname].set_default(this, value));
                this._loaded[fname] = true;
                fieldnames.push(fname);
            }
            return jQuery.when.apply(jQuery, promises).then(() => {
                this.on_change(fieldnames);
                this.on_change_with(fieldnames);
                const callback = () => {
                    if (modified) {
                        this.set_modified();
                        return jQuery.when.apply(
                            jQuery, this.group.root_group.screens
                            .map(screen => screen.display()));
                    }
                };
                if (validate) {
                    return this.validate(null, true)
                        .then(callback);
                } else {
                    return callback();
                }
            });
        },
        get_timestamp: function() {
            var timestamps = {};
            timestamps[this.model.name + ',' + this.id] = this._timestamp;
            for (var fname in this.model.fields) {
                if (!(fname in this._loaded)) {
                    continue;
                }
                jQuery.extend(timestamps,
                    this.model.fields[fname].get_timestamp(this));
            }
            return timestamps;
        },
        get_eval: function() {
            var value = {};
            for (var key in this.model.fields) {
                if (!(key in this._loaded) && this.id >= 0)
                    continue;
                value[key] = this.model.fields[key].get_eval(this);
            }
            value.id = this.id;
            return value;
        },
        get_on_change_value: function(skip) {
            var value = {};
            for (var key in this.model.fields) {
                if (skip && ~skip.indexOf(key)) {
                    continue;
                }
                if ((this.id >= 0) &&
                        (!this._loaded[key] || !this.modified_fields[key])) {
                    continue;
                }
                value[key] = this.model.fields[key].get_on_change_value(this);
            }
            value.id = this.id;
            return value;
        },
        _get_on_change_args: function(args) {
            var result = {};
            var values = Sao.common.EvalEnvironment(this, 'on_change');
            for (const arg of args) {
                var scope = values;
                for (const e of arg.split('.')) {
                    if (scope !== undefined) {
                        scope = scope[e];
                    }
                }
                result[arg] = scope;
            }
            return result;
        },
        on_change: function(fieldnames) {
            var values = {};
            for (const fieldname of fieldnames) {
                var on_change = this.model.fields[fieldname]
                .description.on_change;
                if (!jQuery.isEmptyObject(on_change)) {
                    values = jQuery.extend(values,
                        this._get_on_change_args(on_change));
                }
            }
            if (!jQuery.isEmptyObject(values)) {
                var changes;
                try {
                    if ((fieldnames.length == 1) ||
                        (values.id === undefined)) {
                        changes = [];
                        for (const fieldname of fieldnames) {
                            changes.push(this.model.execute(
                                'on_change_' + fieldname,
                                [values], this.get_context(), false));
                        }
                    } else {
                        changes = [this.model.execute(
                            'on_change',
                            [values, fieldnames], this.get_context(), false)];
                    }
                } catch (e) {
                    return;
                }
                changes.forEach(this.set_on_change, this);
            }

            var notification_fields = Sao.common.MODELNOTIFICATION.get(
                this.model.name);
            var notification_fields_set = new Set(notification_fields);
            if (fieldnames.some(field => notification_fields_set.has(field))) {
                values = this._get_on_change_args(notification_fields);
                this.model.execute(
                    'on_change_notify', [values], this.get_context())
                    .then(this.group.record_notify.bind(this.group));
            }
        },
        on_change_with: function(field_names) {
            var fieldnames = {};
            var values = {};
            var later = {};
            var fieldname, on_change_with;
            for (fieldname in this.model.fields) {
                on_change_with = this.model.fields[fieldname]
                    .description.on_change_with;
                if (jQuery.isEmptyObject(on_change_with)) {
                    continue;
                }
                for (var i = 0; i < field_names.length; i++) {
                    if (~on_change_with.indexOf(field_names[i])) {
                        break;
                    }
                }
                if (i >= field_names.length) {
                    continue;
                }
                if (!jQuery.isEmptyObject(Sao.common.intersect(
                                Object.keys(fieldnames).sort(),
                                on_change_with.sort()))) {
                    later[fieldname] = true;
                    continue;
                }
                fieldnames[fieldname] = true;
                values = jQuery.extend(values,
                    this._get_on_change_args(
                        on_change_with.concat([fieldname])));
                if ((this.model.fields[fieldname] instanceof
                            Sao.field.Many2One) ||
                        (this.model.fields[fieldname] instanceof
                         Sao.field.Reference)) {
                    delete this._values[fieldname + '.'];
                }
            }
            var changed;
            fieldnames = Object.keys(fieldnames);
            if (fieldnames.length) {
                try {
                    if ((fieldnames.length == 1) ||
                        (values.id === undefined)) {
                        changed = {};
                        for (const fieldname of fieldnames) {
                            changed = jQuery.extend(
                                changed,
                                this.model.execute(
                                    'on_change_with_' + fieldname,
                                    [values], this.get_context(), false));
                        }
                    } else {
                        changed = this.model.execute(
                            'on_change_with',
                            [values, fieldnames], this.get_context(), false);
                    }
                } catch (e) {
                    return;
                }
                this.set_on_change(changed);
            }
            if (!jQuery.isEmptyObject(later)) {
                values = {};
                for (const fieldname in later) {
                    on_change_with = this.model.fields[fieldname]
                        .description.on_change_with;
                    values = jQuery.extend(
                        values,
                        this._get_on_change_args(
                            on_change_with.concat([fieldname])));
                }
                fieldnames = Object.keys(later);
                try {
                    if ((fieldnames.length == 1) ||
                        (values.id === undefined)) {
                        changed = {};
                        for (const fieldname of fieldnames) {
                            changed = jQuery.extend(
                                changed,
                                this.model.execute(
                                    'on_change_with_' + fieldname,
                                    [values], this.get_context(), false));
                        }
                    } else {
                        changed = this.model.execute(
                            'on_change_with',
                            [values, fieldnames], this.get_context(), false);
                    }
                } catch (e) {
                    return;
                }
                this.set_on_change(changed);
            }
        },
        set_on_change: function(values) {
            var fieldname, value;
            for (fieldname in values) {
                value = values[fieldname];
                if (!(fieldname in this.model.fields)) {
                    continue;
                }
                if ((this.model.fields[fieldname] instanceof
                            Sao.field.Many2One) ||
                        (this.model.fields[fieldname] instanceof
                         Sao.field.Reference)) {
                    var related = fieldname + '.';
                    this._values[related] = values[related] || {};
                }
                this.load(fieldname, false).set_on_change(this, value);
            }
        },
        autocomplete_with: function(fieldname) {
            for (var fname in this.model.fields) {
                var field = this.model.fields[fname];
                var autocomplete = field.description.autocomplete || [];
                if (!~autocomplete.indexOf(fieldname)) {
                    continue;
                }
                this.do_autocomplete(fname);
            }
        },
        do_autocomplete: function(fieldname) {
            this.autocompletion[fieldname] = [];
            var field = this.model.fields[fieldname];
            var autocomplete = field.description.autocomplete;
            var values = this._get_on_change_args(autocomplete);
            var result;
            try {
                result = this.model.execute(
                    'autocomplete_' + fieldname, [values], this.get_context(),
                    false, false);
            } catch (e) {
                result = [];
            }
            this.autocompletion[fieldname] = result;
        },
        on_scan_code: function(code, depends) {
            depends = this.expr_eval(depends);
            var values = this._get_on_change_args(depends);
            return this.model.execute(
                'on_scan_code', [values, code], this.get_context(),
                true, false).then((changes) => {
                    this.set_on_change(changes);
                    this.set_modified();
                    return !jQuery.isEmptyObject(changes);
                });
        },
        reset: function(value) {
            this.cancel();
            this.set(value, true);
            if (this.group.parent) {
                this.group.parent.on_change([this.group.child_name]);
                this.group.parent.on_change_with([this.group.child_name]);
            }
        },
        expr_eval: function(expr) {
            if (typeof(expr) != 'string') return expr;
            if (!expr) {
                return;
            } else if (expr == '[]') {
                return [];
            } else if (expr == '{}') {
                return {};
            }
            var ctx = this.get_eval();
            ctx.context = this.get_context();
            ctx.active_model = this.model.name;
            ctx.active_id = this.id;
            if (this.group.parent && this.group.parent_name) {
                var parent_env = Sao.common.EvalEnvironment(this.group.parent);
                ctx['_parent_' + this.group.parent_name] = parent_env;
            }
            return new Sao.PYSON.Decoder(ctx).decode(expr);
        },
        rec_name: function() {
            var prm = this.model.execute('read', [[this.id], ['rec_name']],
                    this.get_context());
            return prm.then(function(values) {
                return values[0].rec_name;
            });
        },
        validate: function(fields, softvalidation, pre_validate, sync) {
            const validate_fields = () => {
                var result = true;
                for (var fname in this.model.fields) {
                    // Skip not loaded fields if sync and record is not new
                    if (sync && this.id >= 0 && !(fname in this._loaded)) {
                        continue;
                    }
                    var field = this.model.fields[fname];
                    if (fields && !~fields.indexOf(fname)) {
                        continue;
                    }
                    if (field.description.readonly) {
                        continue;
                    }
                    if (fname == this.group.exclude_field) {
                        continue;
                    }
                    if (!field.validate(this, softvalidation, pre_validate)) {
                        result = false;
                    }
                }
                return result;
            };
            if (sync) {
                return validate_fields();
            } else {
                return this._check_load(fields).then(validate_fields);
            }
        },
        pre_validate: function() {
            if (jQuery.isEmptyObject(this.modified_fields)) {
                return jQuery.Deferred().resolve(true);
            }
            var values = this._get_on_change_args(
                Object.keys(this.modified_fields).concat(['id']));
            return this.model.execute('pre_validate',
                    [values], this.get_context());
        },
        cancel: function() {
            this._loaded = {};
            this._values = {};
            this.modified_fields = {};
            this._timestamp = null;
            this.button_clicks = {};
            this.links_counts = {};
            this.exception = false;
        },
        _check_load: function(fields) {
            if (!this.get_loaded(fields)) {
                return this.reload(fields);
            }
            return jQuery.when();
        },
        get_loaded: function(fields) {
            if (!jQuery.isEmptyObject(fields)) {
                var result = true;
                for (const field of fields) {
                    if (!(field in this._loaded) && !(field in this.modified_fields)) {
                        result = false;
                    }
                }
                return result;
            }
            return Sao.common.compare(Object.keys(this.model.fields).sort(),
                    Object.keys(this._loaded).sort());
        },
        get root_parent() {
            var parent = this;
            while (parent.group.parent) {
                parent = parent.group.parent;
            }
            return parent;
        },
        get_path: function(group) {
            var path = [];
            var i = this;
            var child_name = '';
            while (i) {
                path.push([child_name, i.id]);
                if (i.group === group) {
                    break;
                }
                child_name = i.group.child_name;
                i = i.group.parent;
            }
            path.reverse();
            return path;
        },
        get_index_path: function(group) {
            var path = [],
                record = this;
            while (record) {
                path.push(record.group.indexOf(record));
                if (record.group === group) {
                    break;
                }
                record = record.group.parent;
            }
            path.reverse();
            return path;
        },
        children_group: function(field_name) {
            var group_prm = jQuery.Deferred();
            if (!field_name) {
                group_prm.resolve([]);
                return group_prm;
            }
            var load_prm = this._check_load([field_name]);
            load_prm.done(() => {
                var group = this._values[field_name];
                if (group === undefined) {
                    group_prm.resolve(null);
                    return;
                }

                if (group.model.fields !== this.group.model.fields) {
                    jQuery.extend(this.group.model.fields, group.model.fields);
                    group.model.fields = this.group.model.fields;
                }
                group.on_write = this.group.on_write;
                group.readonly = this.group.readonly;
                jQuery.extend(group._context, this.group._context);

                group_prm.resolve(group);
                return;
            });
            return group_prm;
        },
        get deleted() {
            return Boolean(~this.group.record_deleted.indexOf(this));
        },
        get removed() {
            return Boolean(~this.group.record_removed.indexOf(this));
        },
        get readonly() {
            return (this.deleted ||
                this.removed ||
                this.exception ||
                this.group.readonly ||
                !this._write);
        },
        get deletable() {
            return this._delete;
        },
        get identity() {
            return JSON.stringify(
                Object.keys(this._values).reduce((values, name) => {
                    var field = this.model.fields[name];
                    if (field) {
                        if (field instanceof Sao.field.Binary) {
                            values[name] = field.get_size(this);
                        } else {
                            values[name] = field.get(this);
                        }
                    }
                    return values;
                }, {}));
        },
        set_field_context: function() {
            for (var name in this.model.fields) {
                var field = this.model.fields[name];
                var value = this._values[name];
                if (!(value instanceof Array)) {
                    continue;
                }
                var context_descriptor = Object.getOwnPropertyDescriptor(
                    value, 'context');
                if (!context_descriptor || !context_descriptor.set) {
                    continue;
                }
                var context = field.description.context;
                if (context) {
                    value.context = this.expr_eval(context);
                }
            }
        },
        get_resources: function(reload) {
            var prm;
            if ((this.id >= 0) && (!this.resources || reload)) {
                prm = this.model.execute(
                    'resources', [this.id], this.get_context())
                    .then(resources => {
                        this.resources = resources;
                        return resources;
                    });
            } else {
                prm = jQuery.when(this.resources);
            }
            return prm;
        },
        get_button_clicks: function(name) {
            if (this.id < 0) {
                return jQuery.when();
            }
            var clicks = this.button_clicks[name];
            if (clicks !== undefined) {
                return jQuery.when(clicks);
            }
            return Sao.rpc({
                'method': 'model.ir.model.button.click.get_click',
                'params': [this.model.name, name, this.id, {}],
            }, this.model.session).then(clicks => {
                this.button_clicks[name] = clicks;
                return clicks;
            });
        },
        set_modified: function(field) {
            if (field) {
                this.modified_fields[field] = true;
            }
            this.group.record_modified();
        },
        destroy: function() {
            var vals = Object.values(this._values);
            for (const val of vals) {
                if (val &&
                    Object.prototype.hasOwnProperty.call(val, 'destroy')) {
                    val.destroy();
                }
            }
            this.destroyed = true;
        }
    });


    Sao.field = {};

    Sao.field.get = function(type) {
        switch (type) {
            case 'char':
                return Sao.field.Char;
            case 'selection':
                return Sao.field.Selection;
            case 'multiselection':
                return Sao.field.MultiSelection;
            case 'datetime':
            case 'timestamp':
                return Sao.field.DateTime;
            case 'date':
                return Sao.field.Date;
            case 'time':
                return Sao.field.Time;
            case 'timedelta':
                return Sao.field.TimeDelta;
            case 'float':
                return Sao.field.Float;
            case 'numeric':
                return Sao.field.Numeric;
            case 'integer':
                return Sao.field.Integer;
            case 'boolean':
                return Sao.field.Boolean;
            case 'many2one':
                return Sao.field.Many2One;
            case 'one2one':
                return Sao.field.One2One;
            case 'one2many':
                return Sao.field.One2Many;
            case 'many2many':
                return Sao.field.Many2Many;
            case 'reference':
                return Sao.field.Reference;
            case 'binary':
                return Sao.field.Binary;
            case 'dict':
                return Sao.field.Dict;
            default:
                return Sao.field.Char;
        }
    };

    Sao.field.Field = Sao.class_(Object, {
        _default: null,
        _single_value: true,
        init: function(description) {
            this.description = description;
            this.name = description.name;
            this.views = new Set();
        },
        set: function(record, value) {
            record._values[this.name] = value;
        },
        get: function(record) {
            var value = record._values[this.name];
            if (value === undefined) {
                value = this._default;
            }
            return value;
        },
        _has_changed: function(previous, value) {
            // Use stringify to compare object instance like Number for Decimal
            return JSON.stringify(previous) != JSON.stringify(value);
        },
        set_client: function(record, value, force_change) {
            var previous_value = this.get(record);
            this.set(record, value);
            if (this._has_changed(previous_value, this.get(record))) {
                this.changed(record);
                record.validate(null, true, false, true);
                record.set_modified(this.name);
            } else if (force_change) {
                this.changed(record);
                record.validate(null, true, false, true);
                record.set_modified();
            }
        },
        get_client: function(record) {
            return this.get(record);
        },
        set_default: function(record, value) {
            this.set(record, value);
            record.modified_fields[this.name] = true;
        },
        set_on_change: function(record, value) {
            this.set(record, value);
            record.modified_fields[this.name] = true;
        },
        changed: function(record) {
            record.on_change([this.name]);
            record.on_change_with([this.name]);
            record.autocomplete_with(this.name);
            record.set_field_context();
        },
        get_timestamp: function(record) {
            return {};
        },
        get_context: function(record, record_context, local) {
            var context;
            if (record_context) {
                context = jQuery.extend({}, record_context);
            } else {
                context = record.get_context(local);
            }
            jQuery.extend(context,
                record.expr_eval(this.description.context || {}));
            return context;
        },
        get_search_context: function(record) {
            var context = this.get_context(record);
            jQuery.extend(context,
                record.expr_eval(this.description.search_context || {}));
            return context;
        },
        get_search_order: function(record) {
            return record.expr_eval(this.description.search_order || null);
        },
        get_domains: function(record, pre_validate) {
            var inversion = new Sao.common.DomainInversion();
            var screen_domain = inversion.domain_inversion(
                    [record.group.domain4inversion(), pre_validate || []],
                    this.name, Sao.common.EvalEnvironment(record));
            if ((typeof screen_domain == 'boolean') && !screen_domain) {
                screen_domain = [['id', '=', null]];
            } else if ((typeof screen_domain == 'boolean') && screen_domain) {
                screen_domain = [];
            }
            var attr_domain = record.expr_eval(this.description.domain || []);
            return [screen_domain, attr_domain];
        },
        get_domain: function(record) {
            var domains = this.get_domains(record);
            var screen_domain = domains[0];
            var attr_domain = domains[1];
            var inversion = new Sao.common.DomainInversion();
            return inversion.concat(
                    [inversion.localize_domain(screen_domain), attr_domain]);
        },
        validation_domains: function(record, pre_validate) {
            var inversion = new Sao.common.DomainInversion();
            return inversion.concat(this.get_domains(record, pre_validate));
        },
        get_eval: function(record) {
            return this.get(record);
        },
        get_on_change_value: function(record) {
            return this.get_eval(record);
        },
        set_state: function(
            record, states=['readonly', 'required', 'invisible']) {
            var state_changes = record.expr_eval(
                    this.description.states || {});
            for (const state of states) {
                if ((state == 'readonly') && this.description.readonly) {
                    continue;
                }
                if (state_changes[state] !== undefined) {
                    this.get_state_attrs(record)[state] = state_changes[state];
                } else if (this.description[state] !== undefined) {
                    this.get_state_attrs(record)[state] =
                        this.description[state];
                }
            }
            if (record.group.readonly ||
                this.get_state_attrs(record).domain_readonly ||
                (record.parent_name == this.name)) {
                this.get_state_attrs(record).readonly = true;
            }
        },
        get_state_attrs: function(record) {
            if (!(this.name in record.state_attrs)) {
                record.state_attrs[this.name] = jQuery.extend(
                        {}, this.description);
            }
            if (record.group.readonly || record.readonly) {
                record.state_attrs[this.name].readonly = true;
            }
            return record.state_attrs[this.name];
        },
        _is_empty: function(record) {
            return !this.get_eval(record);
        },
        check_required: function(record) {
            var state_attrs = this.get_state_attrs(record);
            if (state_attrs.required == 1) {
                if (this._is_empty(record) && (state_attrs.readonly != 1)) {
                    return false;
                }
            }
            return true;
        },
        validate: function(record, softvalidation, pre_validate) {
            if (this.description.readonly) {
                return true;
            }
            var invalid = false;
            var state_attrs = this.get_state_attrs(record);
            var is_required = Boolean(parseInt(state_attrs.required, 10));
            var is_invisible = Boolean(parseInt(state_attrs.invisible, 10));
            state_attrs.domain_readonly = false;
            var inversion = new Sao.common.DomainInversion();
            var domain = inversion.simplify(this.validation_domains(record,
                        pre_validate));
            if (!softvalidation) {
                if (!this.check_required(record)) {
                    invalid = 'required';
                }
            }
            if (typeof domain == 'boolean') {
                if (!domain) {
                    invalid = 'domain';
                }
            } else if (Sao.common.compare(domain, [['id', '=', null]])) {
                invalid = 'domain';
            } else {
                let [screen_domain] = this.get_domains(record, pre_validate);
                var uniques = inversion.unique_value(
                    domain, this._single_value);
                var unique = uniques[0];
                var leftpart = uniques[1];
                var value = uniques[2];
                let unique_from_screen = inversion.unique_value(
                    screen_domain, this._single_value)[0];
                if (this._is_empty(record) &&
                    !is_required &&
                    !is_invisible &&
                    !unique_from_screen) {
                    // Do nothing
                } else if (unique) {
                    // If the inverted domain is so constraint that only one
                    // value is possible we should use it. But we must also pay
                    // attention to the fact that the original domain might be
                    // a 'OR' domain and thus not preventing the modification
                    // of fields.
                    if (value === false) {
                        // XXX to remove once server domains are fixed
                        value = null;
                    }
                    var setdefault = true;
                    var original_domain;
                    if (!jQuery.isEmptyObject(record.group.domain)) {
                        original_domain = inversion.merge(record.group.domain);
                    } else {
                        original_domain = inversion.merge(domain);
                    }
                    var domain_readonly = original_domain[0] == 'AND';
                    if (leftpart.contains('.')) {
                        var recordpart = leftpart.split('.', 1)[0];
                        var localpart = leftpart.split('.', 1)[1];
                        var constraintfields = [];
                        if (domain_readonly) {
                            for (const leaf of inversion.localize_domain(
                                original_domain.slice(1))) {
                                constraintfields.push(leaf);
                            }
                        }
                        if ((localpart != 'id') ||
                                !~constraintfields.indexOf(recordpart)) {
                            setdefault = false;
                        }
                    }
                    if (setdefault && !pre_validate) {
                        this.set_client(record, value);
                        state_attrs.domain_readonly = domain_readonly;
                    }
                }
                if (!inversion.eval_domain(domain,
                            Sao.common.EvalEnvironment(record))) {
                    invalid = domain;
                }
            }
            state_attrs.invalid = invalid;
            return !invalid;
        }
    });

    Sao.field.Char = Sao.class_(Sao.field.Field, {
        _default: '',
        set: function(record, value) {
            if (this.description.strip && value) {
                switch (this.description.strip) {
                    case 'leading':
                        value = value.trimStart();
                        break;
                    case 'trailing':
                        value = value.trimEnd();
                        break;
                    default:
                        value = value.trim();
                }
            }
            Sao.field.Char._super.set.call(this, record, value);
        },
        get: function(record) {
            return Sao.field.Char._super.get.call(this, record) || this._default;
        }
    });

    Sao.field.Selection = Sao.class_(Sao.field.Field, {
        _default: null,
        set_client: function(record, value, force_change) {
            // delete before trigger the display
            delete record._values[this.name + ':string'];
            Sao.field.Selection._super.set_client.call(
                this, record, value, force_change);
        }
    });

    Sao.field.MultiSelection = Sao.class_(Sao.field.Selection, {
        _default: null,
        _single_value: false,
        get: function(record) {
            var value = Sao.field.MultiSelection._super.get.call(this, record);
            if (jQuery.isEmptyObject(value)) {
                value = this._default;
            } else {
                value.sort();
            }
            return value;
        },
        get_eval: function(record) {
            var value = Sao.field.MultiSelection._super.get_eval.call(
                this, record);
            if (value === null) {
                value = [];
            }
            return value;
        },
        set_client: function(record, value, force_change) {
            if (value === null) {
                value = [];
            }
            if (typeof(value) == 'string') {
                value = [value];
            }
            if (value) {
                value = value.slice().sort();
            }
            Sao.field.MultiSelection._super.set_client.call(
                this, record, value, force_change);
        }
    });

    Sao.field.DateTime = Sao.class_(Sao.field.Field, {
        _default: null,
        time_format: function(record) {
            return record.expr_eval(this.description.format);
        },
        set_client: function(record, value, force_change) {
            var current_value;
            if (value) {
                if (value.isTime) {
                    current_value = this.get(record);
                    if (current_value) {
                        value = Sao.DateTime.combine(current_value, value);
                    } else {
                        value = null;
                    }
                } else if (value.isDate) {
                    current_value = this.get(record) || Sao.Time();
                    value = Sao.DateTime.combine(value, current_value);
                }
            }
            Sao.field.DateTime._super.set_client.call(this, record, value,
                force_change);
        },
        date_format: function(record) {
            var context = this.get_context(record);
            return Sao.common.date_format(context.date_format);
        }
    });

    Sao.field.Date = Sao.class_(Sao.field.Field, {
        _default: null,
        set_client: function(record, value, force_change) {
            if (value && !value.isDate) {
                value.isDate = true;
                value.isDateTime = false;
            }
            Sao.field.Date._super.set_client.call(this, record, value,
                force_change);
        },
        date_format: function(record) {
            var context = this.get_context(record);
            return Sao.common.date_format(context.date_format);
        }
    });

    Sao.field.Time = Sao.class_(Sao.field.Field, {
        _default: null,
        time_format: function(record) {
            return record.expr_eval(this.description.format);
        },
        set_client: function(record, value, force_change) {
            if (value && (value.isDate || value.isDateTime)) {
                value = Sao.Time(value.hour(), value.minute(),
                    value.second(), value.millisecond());
            }
            Sao.field.Time._super.set_client.call(this, record, value,
                force_change);
        }
    });

    Sao.field.TimeDelta = Sao.class_(Sao.field.Field, {
        _default: null,
        converter: function(group) {
            return group.context[this.description.converter];
        },
        set_client: function(record, value, force_change) {
            if (typeof(value) == 'string') {
                value = Sao.common.timedelta.parse(
                    value, this.converter(record.group));
            }
            Sao.field.TimeDelta._super.set_client.call(
                this, record, value, force_change);
        },
        get_client: function(record) {
            var value = Sao.field.TimeDelta._super.get_client.call(
                this, record);
            return Sao.common.timedelta.format(
                value, this.converter(record.group));
        }
    });

    Sao.field.Float = Sao.class_(Sao.field.Field, {
        _default: null,
        init: function(description) {
            Sao.field.Float._super.init.call(this, description);
            this._digits = {};
            this._symbol = {};
        },
        digits: function(record, factor=1) {
            var digits = record.expr_eval(this.description.digits);
            if (typeof(digits) == 'string') {
                if (!(digits in record.model.fields)) {
                    return;
                }
                var digits_field = record.model.fields[digits];
                var digits_name = digits_field.description.relation;
                var digits_id = digits_field.get(record);
                if (digits_name && (digits_id !== null) && (digits_id >= 0)) {
                    if (digits_id in this._digits) {
                        digits = this._digits[digits_id];
                    } else {
                        try {
                            digits = Sao.rpc({
                                'method': 'model.' + digits_name + '.get_digits',
                                'params': [digits_id, {}],
                            }, record.model.session, false);
                        } catch(e) {
                            Sao.Logger.warn(
                                "Fail to fetch digits for %s,%s",
                                digits_name, digits_id);
                            return;
                        }
                        this._digits[digits_id] = digits;
                    }
                } else {
                    return;
                }
            }
            if (!digits || !digits.every(function(e) {
                return e !== null;
            })) {
                return;
            }
            var shift = Math.round(Math.log(Math.abs(factor)) / Math.LN10);
            return [digits[0] + shift, digits[1] - shift];
        },
        get_symbol: function(record, symbol) {
            if (record && (symbol in record.model.fields)) {
                var value = this.get(record) || 0;
                var sign = 1;
                if (value < 0) {
                    sign = -1;
                } else if (value === 0) {
                    sign = 0;
                }
                var symbol_field = record.model.fields[symbol];
                var symbol_name = symbol_field.description.relation;
                var symbol_id = symbol_field.get(record);
                if (symbol_name && (symbol_id !== null) && (symbol_id >= 0)) {
                    if (symbol_id in this._symbol) {
                        return this._symbol[symbol_id];
                    }
                    try {
                        var result = Sao.rpc({
                            'method': 'model.' + symbol_name + '.get_symbol',
                            'params': [symbol_id, sign, record.get_context()],
                        }, record.model.session, false) || ['', 1];
                        this._symbol[symbol_id] = result;
                        return result;
                    } catch (e) {
                        Sao.Logger.warn(
                            "Fail to fetch symbol for %s,%s",
                            symbol_name, symbol_id);
                    }
                }
            }
            return ['', 1];
        },
        check_required: function(record) {
            var state_attrs = this.get_state_attrs(record);
            if (state_attrs.required == 1) {
                if ((this.get(record) === null) &&
                    (state_attrs.readonly != 1)) {
                    return false;
                }
            }
            return true;
        },
        convert: function(value) {
            if (!value && (value !== 0)) {
                return null;
            }
            value = Number(value);
            if (isNaN(value)) {
                value = this._default;
            }
            return value;
        },
        apply_factor: function(record, value, factor) {
            if (value !== null) {
                value /= factor;
                var digits = this.digits(record);
                if (digits) {
                    // Round to avoid float precision error
                    // after the division by factor
                    value = value.toFixed(digits[1]);
                }
                value = this.convert(value);
            }
            return value;
        },
        set_client: function(record, value, force_change, factor=1) {
            value = this.apply_factor(record, this.convert(value), factor);
            Sao.field.Float._super.set_client.call(this, record, value,
                force_change);
        },
        get_client: function(record, factor=1, grouping=true) {
            var value = this.get(record);
            if (value !== null) {
                var options = {
                    useGrouping: grouping,
                };
                var digits = this.digits(record, factor);
                if (digits) {
                    options.minimumFractionDigits = digits[1];
                    options.maximumFractionDigits = digits[1];
                }
                return (value * factor).toLocaleString(
                    Sao.i18n.BC47(Sao.i18n.getlang()), options);
            } else {
                return '';
            }
        }
    });

    Sao.field.Numeric = Sao.class_(Sao.field.Float, {
        convert: function(value) {
            if (!value && (value !== 0)) {
                return null;
            }
            value = new Sao.Decimal(value);
            if (isNaN(value.valueOf())) {
                value = this._default;
            }
            return value;
        },
    });

    Sao.field.Integer = Sao.class_(Sao.field.Float, {
        convert: function(value) {
            if (!value && (value !== 0)) {
                return null;
            }
            value = parseInt(value, 10);
            if (isNaN(value)) {
                value = this._default;
            }
            return value;
        }
    });

    Sao.field.Boolean = Sao.class_(Sao.field.Field, {
        _default: false,
        set_client: function(record, value, force_change) {
            value = Boolean(value);
            Sao.field.Boolean._super.set_client.call(this, record, value,
                force_change);
        },
        get: function(record) {
            return Boolean(record._values[this.name]);
        },
        get_client: function(record) {
            return Boolean(record._values[this.name]);
        }
    });

    Sao.field.Many2One = Sao.class_(Sao.field.Field, {
        _default: null,
        check_required: function(record) {
            var state_attrs = this.get_state_attrs(record);
            if (state_attrs.required == 1) {
                if ((this.get(record) === null) &&
                    (state_attrs.readonly != 1)) {
                    return false;
                }
            }
            return true;
        },
        get_client: function(record) {
            var rec_name = (record._values[this.name + '.'] || {}).rec_name;
            if (rec_name === undefined) {
                this.set(record, this.get(record));
                rec_name = (
                    record._values[this.name + '.'] || {}).rec_name || '';
            }
            return rec_name;
        },
        set: function(record, value) {
            var rec_name = (
                record._values[this.name + '.'] || {}).rec_name || '';
            if (!rec_name && (value >= 0) && (value !== null)) {
                var model_name = record.model.fields[this.name].description
                    .relation;
                rec_name = Sao.rpc({
                    'method': 'model.' + model_name + '.read',
                    'params': [[value], ['rec_name'], record.get_context()]
                }, record.model.session, false)[0].rec_name;
            }
            Sao.setdefault(
                record._values, this.name + '.', {}).rec_name = rec_name;
            record._values[this.name] = value;
        },
        set_client: function(record, value, force_change) {
            var rec_name;
            if (value instanceof Array) {
                rec_name = value[1];
                value = value[0];
            } else {
                if (value == this.get(record)) {
                    rec_name = (
                        record._values[this.name + '.'] || {}).rec_name || '';
                } else {
                    rec_name = '';
                }
            }
            if ((value < 0) && (this.name != record.group.parent_name)) {
                value = null;
                rec_name = '';
            }
            Sao.setdefault(
                record._values, this.name + '.', {}).rec_name = rec_name;
            Sao.field.Many2One._super.set_client.call(this, record, value,
                    force_change);
        },
        get_context: function(record, record_context, local) {
            var context = Sao.field.Many2One._super.get_context.call(
                this, record, record_context, local);
            if (this.description.datetime_field) {
                context._datetime = record.get_eval()[
                    this.description.datetime_field];
            }
            return context;
        },
        validation_domains: function(record, pre_validate) {
            return this.get_domains(record, pre_validate)[0];
        },
        get_domain: function(record) {
            var domains = this.get_domains(record);
            var screen_domain = domains[0];
            var attr_domain = domains[1];
            var inversion = new Sao.common.DomainInversion();
            return inversion.concat([
                    inversion.localize_domain(screen_domain, this.name),
                    attr_domain]);
        },
        get_on_change_value: function(record) {
            if ((record.group.parent_name == this.name) &&
                    record.group.parent) {
                return record.group.parent.get_on_change_value(
                        [record.group.child_name]);
            }
            return Sao.field.Many2One._super.get_on_change_value.call(
                    this, record);
        }
    });

    Sao.field.One2One = Sao.class_(Sao.field.Many2One, {
    });

    Sao.field.One2Many = Sao.class_(Sao.field.Field, {
        init: function(description) {
            Sao.field.One2Many._super.init.call(this, description);
        },
        _default: null,
        _single_value: false,
        _set_value: function(record, value, default_, modified, data) {
            this._set_default_value(record);
            var group = record._values[this.name];
            if (jQuery.isEmptyObject(value)) {
                value = [];
            }
            var mode;
            if (jQuery.isEmptyObject(value) ||
                    !isNaN(parseInt(value[0], 10))) {
                mode = 'list ids';
            } else {
                mode = 'list values';
            }
            if ((mode == 'list values') || data) {
                var context = this.get_context(record);
                var value_fields = new Set();
                if (mode == 'list values') {
                    for (const v of value) {
                        for (const f of Object.keys(v)) {
                            value_fields.add(f);
                        }
                    }
                } else {
                    for (const d of data) {
                        for (const f in d) {
                            value_fields.add(f);
                        }
                    }
                }
                let field_names = new Set();
                for (const fieldname of value_fields) {
                    if (!(fieldname in group.model.fields) &&
                            (!~fieldname.indexOf('.')) &&
                            (!~fieldname.indexOf(':')) &&
                            (!fieldname.startsWith('_'))) {
                        field_names.add(fieldname);
                    }
                }
                var attr_fields = Object.values(this.description.views || {})
                    .map(v => v.fields)
                    .reduce((acc, elem) => {
                        for (const field in elem) {
                            acc[field] = elem[field];
                        }
                        return acc;
                    }, {});
                var fields = {};
                for (const n of field_names) {
                    if (n in attr_fields) {
                        fields[n] = attr_fields[n];
                    }
                }

                var to_fetch = Array.from(field_names).filter(k => !(k in attr_fields));
                if (to_fetch.length) {
                    var args = {
                        'method': 'model.' + this.description.relation +
                            '.fields_get',
                        'params': [to_fetch, context]
                    };
                    try {
                        var rpc_fields = Sao.rpc(
                            args, record.model.session, false);
                        for (const [key, value] of Object.entries(rpc_fields)) {
                            fields[key] = value;
                        }
                    } catch (e) {
                        return;
                    }
                }
                if (!jQuery.isEmptyObject(fields)) {
                    group.add_fields(fields);
                }
            }
            if (mode == 'list ids') {
                var records_to_remove = [];
                for (const old_record of group) {
                    if (!~value.indexOf(old_record.id)) {
                        records_to_remove.push(old_record);
                    }
                }
                for (const record_to_remove of records_to_remove) {
                    group.remove(record_to_remove, true, false, false);
                }
                var preloaded = {};
                for (const d of (data || [])) {
                    preloaded[d.id] = d;
                }
                group.load(value, modified || default_, -1, preloaded);
            } else {
                for (const vals of value) {
                    var new_record;
                    if ('id' in vals) {
                        new_record = group.get(vals.id);
                        if (!new_record) {
                            new_record = group.new_(false, vals.id);
                        }
                    } else {
                        new_record = group.new_(false);
                    }
                    if (default_) {
                        // Don't validate as parent will validate
                        new_record.set_default(vals, false, false);
                        group.add(new_record, -1, false);
                    } else {
                        new_record.set(vals, false);
                        group.push(new_record);
                    }
                }
                // Trigger modified only once
                group.record_modified();
            }
        },
        set: function(record, value, _default=false, data=null) {
            var group = record._values[this.name];
            var model;
            if (group !== undefined) {
                model = group.model;
                group.destroy();
            } else if (record.model.name == this.description.relation) {
                model = record.model;
            } else {
                model = new Sao.Model(this.description.relation);
            }
            record._values[this.name] = undefined;
            this._set_default_value(record, model);
            this._set_value(record, value, _default, undefined, data);
        },
        get: function(record) {
            var group = record._values[this.name];
            if (group === undefined) {
                return [];
            }
            var record_removed = group.record_removed;
            var record_deleted = group.record_deleted;
            var result = [];
            var parent_name = this.description.relation_field || '';
            var to_add = [];
            var to_create = [];
            var to_write = [];
            for (const record2 of group) {
                if (~record_removed.indexOf(record2) ||
                        ~record_deleted.indexOf(record2)) {
                    continue;
                }
                var values;
                if (record2.id >= 0) {
                    if (record2.modified) {
                        values = record2.get();
                        delete values[parent_name];
                        if (!jQuery.isEmptyObject(values)) {
                            to_write.push([record2.id]);
                            to_write.push(values);
                        }
                        to_add.push(record2.id);
                    }
                } else {
                    values = record2.get();
                    delete values[parent_name];
                    to_create.push(values);
                }
            }
            if (!jQuery.isEmptyObject(to_add)) {
                result.push(['add', to_add]);
            }
            if (!jQuery.isEmptyObject(to_create)) {
                result.push(['create', to_create]);
            }
            if (!jQuery.isEmptyObject(to_write)) {
                result.push(['write'].concat(to_write));
            }
            if (!jQuery.isEmptyObject(record_removed)) {
                result.push(['remove', record_removed.map(function(r) {
                    return r.id;
                })]);
            }
            if (!jQuery.isEmptyObject(record_deleted)) {
                result.push(['delete', record_deleted.map(function(r) {
                    return r.id;
                })]);
            }
            return result;
        },
        set_client: function(record, value, force_change) {
            // domain inversion try to set None as value
            if (value === null) {
                value = [];
            }
            // domain inversion could try to set id as value
            if (typeof value == 'number') {
                value = [value];
            }

            var previous_ids = this.get_eval(record);
            var modified = !Sao.common.compare(
                previous_ids.sort(), value.sort());
            this._set_value(record, value, false, modified);
            if (modified) {
                this.changed(record);
                record.validate(null, true, false, true);
                record.set_modified(this.name);
            } else if (force_change) {
                this.changed(record);
                record.validate(null, true, false, true);
                record.set_modified();
            }
        },
        get_client: function(record) {
            this._set_default_value(record);
            return record._values[this.name];
        },
        set_default: function(record, value) {
            record.modified_fields[this.name] = true;
            return this.set(record, value, true);
        },
        set_on_change: function(record, value) {
            var fields, new_fields;
            record.modified_fields[this.name] = true;
            this._set_default_value(record);
            if (value instanceof Array) {
                return this._set_value(record, value, false, true);
            }
            var new_field_names = {};
            if (value && (value.add || value.update)) {
                var context = this.get_context(record);
                fields = record._values[this.name].model.fields;
                var adding_values = [];
                if (value.add) {
                    for (const add of value.add) {
                        adding_values.push(add[1]);
                    }
                }
                for (const l of [adding_values, value.update]) {
                    if (!jQuery.isEmptyObject(l)) {
                        for (const v of l) {
                            for (const f of Object.keys(v)) {
                                if (!(f in fields) &&
                                    (f != 'id') &&
                                    (!~f.indexOf('.'))) {
                                        new_field_names[f] = true;
                                    }
                            }
                        }
                    }
                }
                if (!jQuery.isEmptyObject(new_field_names)) {
                    var args = {
                        'method': 'model.' + this.description.relation +
                            '.fields_get',
                        'params': [Object.keys(new_field_names), context]
                    };
                    try {
                        new_fields = Sao.rpc(args, record.model.session, false);
                    } catch (e) {
                        return;
                    }
                } else {
                    new_fields = {};
                }
            }

            var group = record._values[this.name];
            if (value && value.delete) {
                for (const record_id of value.delete) {
                    const record2 = group.get(record_id);
                    if (record2) {
                        group.remove(record2, false, false, false);
                    }
                }
            }
            if (value && value.remove) {
                for (const record_id of value.remove) {
                    const record2 = group.get(record_id);
                    if (record2) {
                        group.remove(record2, true, false, false);
                    }
                }
            }

            if (value && (value.add || value.update)) {
                // First set already added fields to prevent triggering a
                // second on_change call
                if (value.update) {
                    for (const vals of value.update) {
                        if (!vals.id) {
                            continue;
                        }
                        const record2 = group.get(vals.id);
                        if (record2) {
                            var vals_to_set = {};
                            for (var key in vals) {
                                if (!(key in new_field_names)) {
                                    vals_to_set[key] = vals[key];
                                }
                            }
                            record2.set_on_change(vals_to_set);
                        }
                    }
                }

                group.add_fields(new_fields);
                if (value.add) {
                    for (const vals of value.add) {
                        let new_record;
                        const index = vals[0];
                        const data = vals[1];
                        const id_ = data.id;
                        delete data.id;
                        if (id_) {
                            new_record = group.get(id_);
                        }
                        if (!new_record) {
                            new_record = group.new_(false, id_);
                        }
                        group.add(new_record, index, false);
                        new_record.set_on_change(data);
                    }
                }
                if (value.update) {
                    for (const vals of value.update) {
                        if (!vals.id) {
                            continue;
                        }
                        const record2 = group.get(vals.id);
                        if (record2) {
                            record2.set_on_change(vals);
                        }
                    }
                }
            }
        },
        _set_default_value: function(record, model) {
            if (record._values[this.name] !== undefined) {
                return;
            }
            if (!model) {
                model = new Sao.Model(this.description.relation);
            }
            if (record.model.name == this.description.relation) {
                model = record.model;
            }
            var context = record.expr_eval(this.description.context || {});
            var group = Sao.Group(model, context, []);
            group.set_parent(record);
            group.parent_name = this.description.relation_field;
            group.child_name = this.name;
            group.parent_datetime_field = this.description.datetime_field;
            record._values[this.name] = group;
        },
        get_timestamp: function(record) {
            var timestamps = {};
            var group = record._values[this.name] || [];
            var records = group.filter(function(record) {
                return record.modified;
            });
            for (const record of jQuery.extend(
                records, group.record_removed, group.record_deleted)) {
                jQuery.extend(timestamps, record.get_timestamp());
            }
            return timestamps;
        },
        get_eval: function(record) {
            var result = [];
            var group = record._values[this.name];
            if (group === undefined) return result;

            var record_removed = group.record_removed;
            var record_deleted = group.record_deleted;
            for (const record2 of group) {
                if (~record_removed.indexOf(record2) ||
                        ~record_deleted.indexOf(record2))
                    continue;
                result.push(record2.id);
            }
            return result;
        },
        get_on_change_value: function(record) {
            var result = [];
            var group = record._values[this.name];
            if (group === undefined) return result;
            for (const record2 of group) {
                if (!record2.deleted && !record2.removed)
                    result.push(record2.get_on_change_value(
                                [this.description.relation_field || '']));
            }
            return result;
        },
        get_removed_ids: function(record) {
            return record._values[this.name].record_removed.map(function(r) {
                return r.id;
            });
        },
        get_domain: function(record) {
            var domains = this.get_domains(record);
            var attr_domain = domains[1];
            // Forget screen_domain because it only means at least one record
            // and not all records
            return attr_domain;
        },
        validation_domains: function(record, pre_validate) {
            return this.get_domains(record, pre_validate)[0];
        },
        validate: function(record, softvalidation, pre_validate) {
            var invalid = false;
            var inversion = new Sao.common.DomainInversion();
            var ldomain = inversion.localize_domain(inversion.domain_inversion(
                        record.group.clean4inversion(pre_validate || []), this.name,
                        Sao.common.EvalEnvironment(record)), this.name);
            if (typeof ldomain == 'boolean') {
                if (ldomain) {
                    ldomain = [];
                } else {
                    ldomain = [['id', '=', null]];
                }
            }
            for (const record2 of (record._values[this.name] || [])) {
                if (!record2.get_loaded() && (record2.id >= 0) &&
                        !pre_validate) {
                    continue;
                }
                if (!record2.validate(null, softvalidation, ldomain, true)) {
                    invalid = 'children';
                }
            }
            var test = Sao.field.One2Many._super.validate.call(this, record,
                        softvalidation, pre_validate);
            if (test && invalid) {
                this.get_state_attrs(record).invalid = invalid;
                return false;
            }
            return test;
        },
        set_state: function(record, states) {
            this._set_default_value(record);
            Sao.field.One2Many._super.set_state.call(this, record, states);
        },
        _is_empty: function(record) {
            return jQuery.isEmptyObject(this.get_eval(record));
        }
    });

    Sao.field.Many2Many = Sao.class_(Sao.field.One2Many, {
        get_on_change_value: function(record) {
            return this.get_eval(record);
        }
    });

    Sao.field.Reference = Sao.class_(Sao.field.Field, {
        _default: null,
        get_client: function(record) {
            if (record._values[this.name]) {
                var model = record._values[this.name][0];
                var name = (
                    record._values[this.name + '.'] || {}).rec_name || '';
                return [model, name];
            } else {
                return null;
            }
        },
        get: function(record) {
            if (record._values[this.name] &&
                record._values[this.name][0] &&
                record._values[this.name][1] !== null &&
                record._values[this.name][1] >= -1) {
                return record._values[this.name].join(',');
            }
            return null;
        },
        set_client: function(record, value, force_change) {
            if (value) {
                if (typeof(value) == 'string') {
                    value = value.split(',');
                }
                var ref_model = value[0];
                var ref_id = value[1];
                var rec_name;
                if (ref_id instanceof Array) {
                    rec_name = ref_id[1];
                    ref_id = ref_id[0];
                } else {
                    if (ref_id && !isNaN(parseInt(ref_id, 10))) {
                        ref_id = parseInt(ref_id, 10);
                    }
                    if ([ref_model, ref_id].join(',') == this.get(record)) {
                        rec_name = (
                            record._values[this.name + '.'] || {}).rec_name || '';
                    } else {
                        rec_name = '';
                    }
                }
                Sao.setdefault(
                    record._values, this.name + '.', {}).rec_name = rec_name;
                value = [ref_model, ref_id];
            }
            Sao.field.Reference._super.set_client.call(
                    this, record, value, force_change);
        },
        set: function(record, value) {
            if (!value) {
                record._values[this.name] = this._default;
                return;
            }
            var ref_model, ref_id;
            if (typeof(value) == 'string') {
                ref_model = value.split(',')[0];
                ref_id = value.split(',')[1];
                if (!ref_id) {
                    ref_id = null;
                } else if (!isNaN(parseInt(ref_id, 10))) {
                    ref_id = parseInt(ref_id, 10);
                }
            } else {
                ref_model = value[0];
                ref_id = value[1];
            }
            var rec_name = (
                record._values[this.name + '.'] || {}).rec_name || '';
            if (ref_model && ref_id !== null && ref_id >= 0) {
                if (!rec_name && ref_id >= 0) {
                    rec_name = Sao.rpc({
                        'method': 'model.' + ref_model + '.read',
                        'params': [[ref_id], ['rec_name'], record.get_context()]
                    }, record.model.session, false)[0].rec_name;
                }
            } else if (ref_model) {
                rec_name = '';
            } else {
                rec_name = ref_id;
            }
            Sao.setdefault(
                record._values, this.name + '.', {}).rec_name = rec_name;
            record._values[this.name] = [ref_model, ref_id];
        },
        get_on_change_value: function(record) {
            if ((record.group.parent_name == this.name) &&
                    record.group.parent) {
                return [record.group.parent.model.name,
                    record.group.parent.get_on_change_value(
                        [record.group.child_name])];
            }
            return Sao.field.Reference._super.get_on_change_value.call(
                    this, record);
        },
        get_context: function(record, record_context, local) {
            var context = Sao.field.Reference._super.get_context.call(
                this, record, record_context, local);
            if (this.description.datetime_field) {
                context._datetime = record.get_eval()[
                    this.description.datetime_field];
            }
            return context;
        },
        validation_domains: function(record, pre_validate) {
            return this.get_domains(record, pre_validate)[0];
        },
        get_domains: function(record, pre_validate) {
            var model = null;
            if (record._values[this.name]) {
                model = record._values[this.name][0];
            }
            var domains = Sao.field.Reference._super.get_domains.call(
                this, record, pre_validate);
            domains[1] = domains[1][model] || [];
            return domains;
        },
        get_domain: function(record) {
            var model = null;
            if (record._values[this.name]) {
                model = record._values[this.name][0];
            }
            var domains = this.get_domains(record);
            var screen_domain = domains[0];
            var attr_domain = domains[1];
            var inversion = new Sao.common.DomainInversion();
            screen_domain = inversion.filter_leaf(
                screen_domain, this.name, model);
            screen_domain = inversion.prepare_reference_domain(
                screen_domain, this.name);
            return inversion.concat([
                inversion.localize_domain(screen_domain, this.name, true),
                attr_domain]);
        },
        get_search_order: function(record) {
            var order = Sao.field.Reference._super.get_search_order.call(
                this, record);
            if (order !== null) {
                var model = null;
                if (record._values[this.name]) {
                    model = record._values[this.name][0];
                }
                order = order[model] || null;
            }
            return order;
        },
        get_models: function(record) {
            var domains = this.get_domains(record);
            var inversion = new Sao.common.DomainInversion();
            var screen_domain = inversion.prepare_reference_domain(
                domains[0], this.name);
            return inversion.extract_reference_models(
                inversion.concat([screen_domain, domains[1]]),
                this.name);
        },
        _is_empty: function(record) {
            var result = Sao.field.Reference._super._is_empty.call(
                this, record);
            if (!result && record._values[this.name][1] < 0) {
                result = true;
            }
            return result;
        },
    });

    Sao.field.Binary = Sao.class_(Sao.field.Field, {
        _default: null,
        _has_changed: function(previous, value) {
            return previous != value;
        },
        get_size: function(record) {
            var data = record._values[this.name] || 0;
            if ((data instanceof Uint8Array) ||
                (typeof(data) == 'string')) {
                return data.length;
            }
            return data;
        },
        get_data: function(record) {
            var data = record._values[this.name];
            var prm = jQuery.when(data);
            if (!(data instanceof Uint8Array) &&
                (typeof(data) != 'string') &&
                (data !== null)) {
                if (record.id < 0) {
                    return prm;
                }
                var context = record.get_context();
                prm = record.model.execute('read', [[record.id], [this.name]],
                    context).then(data => {
                        data = data[0][this.name];
                        this.set(record, data);
                        return data;
                    });
            }
            return prm;
        }
    });

    Sao.field.Dict = Sao.class_(Sao.field.Field, {
        _default: {},
        _single_value: false,
        init: function(description) {
            Sao.field.Dict._super.init.call(this, description);
            this.schema_model = new Sao.Model(description.schema_model);
            this.keys = {};
        },
        set: function(record, value) {
            if (value) {
                // Order keys to allow comparison with stringify
                var keys = [];
                for (var key in value) {
                    keys.push(key);
                }
                keys.sort();
                var new_value = {};
                for (var index in keys) {
                    key = keys[index];
                    new_value[key] = value[key];
                }
                value = new_value;
            }
            Sao.field.Dict._super.set.call(this, record, value);
        },
        get: function(record) {
            return jQuery.extend(
                {}, Sao.field.Dict._super.get.call(this, record));
        },
        get_client: function(record) {
            return Sao.field.Dict._super.get_client.call(this, record);
        },
        validation_domains: function(record, pre_validate) {
            return this.get_domains(record, pre_validate)[0];
        },
        get_domain: function(record) {
            var inversion = new Sao.common.DomainInversion();
            var domains = this.get_domains(record);
            var screen_domain = domains[0];
            var attr_domain = domains[1];
            return inversion.concat([
                    inversion.localize_domain(screen_domain),
                    attr_domain]);
        },
        date_format: function(record) {
            var context = this.get_context(record);
            return Sao.common.date_format(context.date_format);
        },
        time_format: function(record) {
            return '%X';
        },
        add_keys: function(keys, record) {
            var context = this.get_context(record);
            var domain = this.get_domain(record);
            var batchlen = Math.min(10, Sao.config.limit);

            keys = jQuery.extend([], keys);
            const update_keys = values => {
                for (const k of values) {
                    this.keys[k.name] = k;
                }
            };

            var prms = [];
            while (keys.length > 0) {
                var sub_keys = keys.splice(0, batchlen);
                prms.push(this.schema_model.execute('search_get_keys',
                            [[['name', 'in', sub_keys], domain],
                                Sao.config.limit],
                            context)
                        .then(update_keys));
            }
            return jQuery.when.apply(jQuery, prms);
        },
        add_new_keys: function(ids, record) {
            var context = this.get_context(record);
            return this.schema_model.execute('get_keys', [ids], context)
                .then(new_fields => {
                    var names = [];
                    for (const new_field of new_fields) {
                        this.keys[new_field.name] = new_field;
                        names.push(new_field.name);
                    }
                    return names;
                });
        },
        validate: function(record, softvalidation, pre_validate) {
            var valid = Sao.field.Dict._super.validate.call(
                this, record, softvalidation, pre_validate);

            if (this.description.readonly) {
                return valid;
            }

            var decoder = new Sao.PYSON.Decoder();
            var field_value = this.get_eval(record);
            var domain = [];
            for (var key in field_value) {
                if (!(key in this.keys)) {
                    continue;
                }
                var key_domain = this.keys[key].domain;
                if (key_domain) {
                    domain.push(decoder.decode(key_domain));
                }
            }

            var inversion = new Sao.common.DomainInversion();
            var valid_value = inversion.eval_domain(domain, field_value);
            if (!valid_value) {
                this.get_state_attrs(record).invalid = 'domain';
            }

            return valid && valid_value;
        }
    });
}());
