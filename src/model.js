/* This file is part of Tryton.  The COPYRIGHT file at the top level of
   this repository contains the full copyright notices and license terms. */
(function() {
    'use strict';

    Sao.Model = Sao.class_(Object, {
        init: function(name, attributes) {
            attributes = attributes || {};
            this.name = name;
            this.session = Sao.Session.current_session;
            this.fields = {};
        },
        add_fields: function(descriptions) {
            for (var name in descriptions) {
                if (descriptions.hasOwnProperty(name) &&
                    (!(name in this.fields))) {
                        var desc = descriptions[name];
                        var Field = Sao.field.get(desc.type);
                        this.fields[name] = new Field(desc);
                    }
            }
        },
        execute: function(method, params, context) {
            var args = {
                'method': 'model.' + this.name + '.' + method,
                'params': params.concat(context)
            };
            return Sao.rpc(args, this.session);
        },
        find: function(condition, offset, limit, order, context) {
            if (!offset) offset = 0;
            var self = this;
            var prm = this.execute('search',
                    [condition, offset, limit, order], context);
            var instanciate = function(ids) {
                return Sao.Group(self, context, ids.map(function(id) {
                    return new Sao.Record(self, id);
                }));
            };
            return prm.pipe(instanciate);
        },
        delete_: function(records) {
            if (jQuery.isEmptyObject(records)) {
                return jQuery.when();
            }
            var record = records[0];
            var root_group = record.group.root_group;
            // TODO test same model
            // TODO test same root group
            records = records.filter(function(record) {
                return record.id >= 0;
            });
            var context = {};
            // TODO timestamp
            var record_ids = records.map(function(record) {
                return record.id;
            });
            // TODO reload ids
            return this.execute('delete', [record_ids], context);
        }
    });

    Sao.Group = function(model, context, array) {
        array.prm = jQuery.when();
        array.model = model;
        array.context = context;
        array.parent = undefined;
        array.screens = [];
        array.parent_name = '';
        array.children = [];
        array.child_name = '';
        array.parent_datetime_field = undefined;
        array.record_removed = [];
        array.record_deleted = [];
        array.forEach(function(e, i, a) {
            e.group = a;
        });
        array.load = function(ids, modified) {
            var new_records = [];
            var i, len;
            for (i = 0, len = ids.length; i < len; i++) {
                var id = ids[i];
                var new_record = this.get(id);
                if (!new_record) {
                    new_record = new Sao.Record(this.model, id);
                    new_record.group = this;
                    this.push(new_record);
                }
                new_records.push(new_record);
            }
            // Remove previously removed or deleted records
            var record_removed = [];
            var record;
            for (i = 0, len = this.record_removed.length; i < len; i++) {
                record = this.record_removed[i];
                if (!~ids.indexOf(record.id)) {
                    record_removed.push(record);
                }
            }
            this.record_removed = record_removed;
            var record_deleted = [];
            for (i = 0, len = this.record_deleted.length; i < len; i++) {
                record = this.record_deleted[i];
                if (!~ids.indexOf(record.id)) {
                    record_deleted.push(record);
                }
            }
            this.record_deleted = record_deleted;
            if (new_records.length && modified) {
                this.changed();
            }
        };
        array.get = function(id) {
            // TODO optimize
            for (var i = 0, len = this.length; i < len; i++) {
                var record = this[i];
                if (record.id == id) {
                    return record;
                }
            }
        };
        array.new_ = function(default_, id) {
            var record = new Sao.Record(this.model, id);
            record.group = this;
            if (default_) {
                record.default_get();
            }
            return record;
        };
        array.add = function(record, position) {
            if (position === undefined) {
                position = -1;
            }
            if (record.group != this) {
                record.group = this;
            }
            this.splice(position, 0, record);
            for (var record_rm in this.record_removed) {
                if (record_rm.id == record.id) {
                    this.record_removed.splice(
                            this.record_removed.indexOf(record_rm), 1);
                }
            }
            for (var record_del in this.record_deleted) {
                if (record_del.id == record.id) {
                    this.record_deleted.splice(
                            this.record_deleted.indexOf(record_del), 1);
                }
            }
            record._changed.id = true;
            this.changed();
            return record;
        };
        array.remove = function(record, remove, modified, force_remove) {
            if (modified === undefined) {
                modified = true;
            }
            var idx = this.indexOf(record);
            if (record.id >= 0) {
                if (remove) {
                    if (~this.record_deleted.indexOf(record)) {
                        this.record_deleted.splice(
                                this.record_deleted.indexOf(record), 1);
                    }
                    this.record_removed.push(record);
                } else {
                    if (~this.record_removed.indexOf(record)) {
                        this.record_removed.splice(
                                this.record_removed.indexOf(record), 1);
                    }
                    this.record_deleted.push(record);
                }
            }
            if (record.group.parent) {
                record.group.parent._changed.id = true;
            }
            if (modified) {
                record._changed.id = true;
            }
            if (!(record.group.parent) || (record.id < 0) || force_remove) {
                this._remove(record);
            }
            record.group.changed();
            record.group.root_group().screens.forEach(function(screen) {
                screen.display();
            });
        };
        array._remove = function(record) {
            var idx = this.indexOf(record);
            this.splice(idx, 1);
        };
        array.unremove = function(record) {
            this.record_removed.splice(this.record_removed.indexOf(record), 1);
            this.record_deleted.splice(this.record_deleted.indexOf(record), 1);
            record.group.changed();
            record.group.root_group().screens.forEach(function(screen) {
                screen.display();
            });
        };
        array.changed = function() {
            if (!this.parent) {
                return jQuery.when();
            }
            this.parent._changed[this.child_name] = true;
            var prm = jQuery.Deferred();
            this.parent.model.fields[this.child_name].changed(this.parent).then(
                    function() {
                        // TODO validate parent
                        this.parent.group.changed().done(prm.resolve);
                    }.bind(this));
            return prm;
        };
        array.root_group = function() {
            var root = this;
            var parent = this.parent;
            while (parent) {
                root = parent.group;
                parent = parent.parent;
            }
            return root;
        };
        array.save = function() {
            var deferreds = [];
            this.forEach(function(record) {
                deferreds.push(record.save());
            });
            if (!jQuery.isEmptyObject(this.record_deleted)) {
                deferreds.push(this.model.delete_(this.record_deleted));
            }
            return jQuery.when.apply(jQuery, deferreds);
        };
        array.written = function(ids) {
            // TODO
        };
        array.reload = function(ids) {
            this.children.forEach(function(child) {
                child.reload(ids);
            });
            ids.forEach(function(id) {
                var record = this.get(id);
                if (record && jQuery.isEmptyObject(record._changed)) {
                    record._loaded = {};
                }
            }.bind(this));
        };
        array.set_parent = function(parent) {
            this.parent = parent;
            if (parent && parent.model_name == this.model.name) {
                this.parent.group.children.push(this);
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
        array.domain = function() {
            var domain = [];
            this.screens.forEach(function(screen) {
                if (screen.attributes.domain) {
                    domain.push(screen.attributes.domain);
                }
            });
            if (this.parent && this.child_name) {
                var field = this.parent.model.fields[this.child_name];
                return [domain, field.get_domain(this.parent)];
            } else {
                return domain;
            }
        };
        array.clean4inversion = function(domain) {
            if (jQuery.isEmptyObject(domain)) {
                return [];
            }
            var inversion = new Sao.common.DomainInversion();
            var head = domain[0];
            var tail = domain.slice(1);
            if (~['AND', 'OR'].indexOf(head)) {
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
            if (!this.__domain4inversion) {
                this.__domain4inversion = this.clean4inversion(this.domain());
            }
            return this.__domain4inversion;
        };
        return array;
    };

    Sao.Record = Sao.class_(Object, {
        id_counter: -1,
        init: function(model, id) {
            this.model = model;
            this.group = Sao.Group(model, {}, []);
            this.id = id || Sao.Record.prototype.id_counter--;
            this._values = {};
            this._changed = {};
            this._loaded = {};
            this.fields = {};
            this._timestamp = null;
            this.state_attrs = {};
        },
        has_changed: function() {
            return !jQuery.isEmptyObject(this._changed);
        },
        save: function() {
            var context = this.get_context();
            var prm = jQuery.when();
            var values = this.get();
            if (this.id < 0) {
                prm = this.model.execute('create', [[values]], context);
                var created = function(ids) {
                    this.id = ids[0];
                };
                prm.done(created.bind(this));
            } else {
                if (!jQuery.isEmptyObject(values)) {
                    // TODO timestamp
                    prm = this.model.execute('write', [[this.id], values],
                            context);
                }
            }
            prm.done(function() {
                this.reload();
            }.bind(this));
            // TODO group written
            // TODO parent
            return prm;
        },
        reload: function(fields) {
            if (this.id < 0) {
                return jQuery.when();
            }
            return this.validate(fields);
        },
        load: function(name) {
            var self = this;
            var fname;
            var prm;
            if ((this.id < 0) || (name in this._loaded)) {
                return jQuery.when();
            }
            if (this.group.prm.state() == 'pending') {
                prm = jQuery.Deferred();
                this.group.prm.then(function() {
                    this.load(name).then(prm.resolve, prm.reject);
                }.bind(this));
                return prm;
            }
            var id2record = {};
            id2record[this.id] = this;
            var loading;
            if (name == '*') {
                loading = 'eager';
                for (fname in this.model.fields) {
                    if (!this.model.fields.hasOwnProperty(fname)) {
                        continue;
                    }
                    var field_loading = (
                            this.model.fields[fname].description.loading ||
                            'eager');
                    if (field_loading != 'eager') {
                        loading = 'lazy';
                        break;
                    }
                }
            } else {
                loading = (this.model.fields[name].description.loading ||
                        'eager');
            }
            if (~this.group.indexOf(this) && (loading == 'eager')) {
                var idx = this.group.indexOf(this);
                var length = this.group.length;
                var n = 1;
                while (Object.keys(id2record).length &&
                        ((idx - n >= 0) || (idx + n < length)) &&
                        n < 100) {
                            var record;
                            if (idx - n >= 0) {
                                record = this.group[idx - n];
                                if (!(name in record._loaded) &&
                                        (record.id >= 0)) {
                                    id2record[record.id] = record;
                                }
                            }
                            if (idx + n < length) {
                                record = this.group[idx + n];
                                if (!(name in record._loaded) &&
                                        (record.id >= 0)) {
                                    id2record[record.id] = record;
                                }
                            }
                            n++;
                        }
            }
            var context = this.get_context();
            var fnames = [];
            if (loading == 'eager') {
                for (fname in this.model.fields) {
                    if (!this.model.fields.hasOwnProperty(fname)) {
                        continue;
                    }
                    if ((this.model.fields[fname].description.loading ||
                                'eager') == 'eager') {
                        fnames.push(fname);
                    }
                }
            } else {
                fnames = Object.keys(this.model.fields);
            }
            fnames = fnames.filter(function(e, i, a) {
                return !(e in self._loaded);
            });
            var fnames_to_fetch = fnames.slice();
            var rec_named_fields = ['many2one', 'one2one', 'reference'];
            for (var i in fnames) {
                fname = fnames[i];
                var fdescription = this.model.fields[fname].description;
                if (~rec_named_fields.indexOf(fdescription.type))
                    fnames_to_fetch.push(fname + '.rec_name');
            }
            if (!~fnames.indexOf('rec_name')) {
                fnames_to_fetch.push('rec_name');
            }
            fnames_to_fetch.push('_timestamp');
            // TODO size of binary
            prm = this.model.execute('read', [Object.keys(id2record),
                    fnames_to_fetch], context);
            var succeed = function(values) {
                var id2value = {};
                values.forEach(function(e, i, a) {
                    id2value[e.id] = e;
                });
                for (var id in id2record) {
                    if (!id2record.hasOwnProperty(id)) {
                        continue;
                    }
                    record = id2record[id];
                    // TODO exception
                    var value = id2value[id];
                    if (record && value) {
                        record.set(value);
                    }
                }
            };
            var failed = function() {
                var failed_values = [];
                var default_values;
                for (var id in id2record) {
                    default_values = {
                        id: id
                    };
                    for (var i in fnames_to_fetch) {
                        default_values[fnames_to_fetch[i]] = null;
                    }
                    failed_values.push(default_values);
                }
                succeed(failed_values);
            };
            this.group.prm = prm.then(succeed, failed);
            return this.group.prm;
        },
        set: function(values) {
            var rec_named_fields = ['many2one', 'one2one', 'reference'];
            for (var name in values) {
                if (!values.hasOwnProperty(name)) {
                    continue;
                }
                var value = values[name];
                if (name == '_timestamp') {
                    this._timestamp = value;
                    continue;
                }
                if (!(name in this.model.fields)) {
                    if (name == 'rec_name') {
                        this._values[name] = value;
                    }
                    continue;
                }
                // TODO delay O2M
                if (this.model.fields[name] instanceof Sao.field.Many2One) {
                    // TODO reference
                    var field_rec_name = name + '.rec_name';
                    if (values.hasOwnProperty(field_rec_name)) {
                        this._values[field_rec_name] = values[field_rec_name];
                    }
                    else if (this._values.hasOwnProperty(field_rec_name)) {
                        delete this._values[field_rec_name];
                    }
                }
                this.model.fields[name].set(this, value);
                this._loaded[name] = true;
            }
        },
        get: function() {
            var value = {};
            for (var name in this.model.fields) {
                if (!this.model.fields.hasOwnProperty(name)) {
                    continue;
                }
                var field = this.model.fields[name];
                if (field.description.readonly) {
                    continue;
                }
                if ((this._changed[name] === undefined) && this.id >= 0) {
                    continue;
                }
                value[name] = field.get(this);
            }
            return value;
        },
        get_context: function() {
            return this.group.context;
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
        default_get: function() {
            var prm;
            if (!jQuery.isEmptyObject(this.model.fields)) {
                prm = this.model.execute('default_get',
                        [Object.keys(this.model.fields)], this.get_context());
                var force_parent = function(values) {
                    // TODO
                    return values;
                };
                prm = prm.pipe(force_parent).done(this.set_default.bind(this));
            } else {
                prm = jQuery.when();
            }
            // TODO autocomplete
            return prm;
        },
        set_default: function(values) {
            for (var fname in values) {
                if (!values.hasOwnProperty(fname)) {
                    continue;
                }
                var value = values[fname];
                if (!(fname in this.model.fields)) {
                    continue;
                }
                if (this.model.fields[fname] instanceof Sao.field.Many2One) {
                    // TODO reference
                    var field_rec_name = fname + '.rec_name';
                    if (values.hasOwnProperty(field_rec_name)) {
                        this._values[field_rec_name] = values[field_rec_name];
                    } else if (this._values.hasOwnProperty(field_rec_name)) {
                        delete this._values[field_rec_name];
                    }
                }
                this.model.fields[fname].set_default(this, value);
                this._loaded[fname] = true;
            }
            this.validate(null, true).then(function() {
                this.group.root_group().screens.forEach(function(screen) {
                    screen.display();
                });
            }.bind(this));
        },
        get_eval: function() {
            var value = {};
            for (var key in this.model.fields) {
                if (!this.model.fields.hasOwnProperty(key) && this.id >= 0)
                    continue;
                value[key] = this.model.fields[key].get_eval(this);
            }
            return value;
        },
        get_on_change_value: function() {
            var value = {};
            for (var key in this.model.fields) {
                if (!this.model.fields.hasOwnProperty(key) && this.id >= 0)
                    continue;
                value[key] = this.model.fields[key].get_on_change_value(this);
            }
            return value;
        },
        _get_on_change_args: function(args) {
            var result = {};
            var values = Sao.common.EvalEnvironment(this, 'on_change');
            args.forEach(function(arg) {
                var scope = values;
                arg.split('.').forEach(function(e) {
                    if (scope !== undefined) {
                        scope = scope[e];
                    }
                });
                result[arg] = scope;
            });
            return result;
        },
        on_change: function(fieldname, attr) {
            if (typeof(attr) == 'string') {
                attr = new Sao.PYSON.Decoder().decode(attr);
            }
            var args = this._get_on_change_args(attr);
            var prm = this.model.execute('on_change_' + fieldname,
                   [args], this.get_context());
            return prm.then(this.set_on_change.bind(this));
        },
        on_change_with: function(field_name) {
            var fieldnames = {};
            var values = {};
            var later = {};
            var fieldname, on_change_with;
            for (fieldname in this.model.fields) {
                if (!this.model.fields.hasOwnProperty(fieldname)) {
                    continue;
                }
                on_change_with = this.model.fields[fieldname]
                    .description.on_change_with;
                if (jQuery.isEmptyObject(on_change_with)) {
                    continue;
                }
                if (!~on_change_with.indexOf(field_name)) {
                    continue;
                }
                if (field_name == fieldname) {
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
                        this._get_on_change_args(on_change_with));
                if (this.model.fields[fieldname] instanceof
                        Sao.field.Many2One) {
                    // TODO reference
                    delete this._values[fieldname + '.rec_name'];
                }
            }
            var prms = [];
            var prm;
            if (!jQuery.isEmptyObject(fieldnames)) {
                prm = this.model.execute('on_change_with',
                        [values, Object.keys(fieldnames)], this.get_context());
                prms.push(prm.then(this.set_on_change.bind(this)));
            }
            var set_on_change = function(fieldname) {
                return function(result) {
                    this.model.fields[fieldname].set_on_change(this, result);
                };
            };
            for (fieldname in later) {
                if (!later.hasOwnProperty(fieldname)) {
                    continue;
                }
                on_change_with = this.model.fields[fieldname]
                    .description.on_change_with;
                values = this._get_on_change_args(on_change_with);
                prm = this.model.execute('on_change_with_' + fieldname,
                    [values], this.get_context());
                prms.push(prm.then(set_on_change(fieldname).bind(this)));
            }
            return jQuery.when.apply(jQuery, prms);
        },
        set_on_change: function(values) {
            var later = {};
            var fieldname, value;
            for (fieldname in values) {
                if (!values.hasOwnProperty(fieldname)) {
                    continue;
                }
                value = values[fieldname];
                if (!(fieldname in this.model.fields)) {
                    continue;
                }
                if (this.model.fields[fieldname] instanceof
                        Sao.field.One2Many) {
                    later[fieldname] = value;
                    continue;
                }
                if (this.model.fields[fieldname] instanceof
                        Sao.field.Many2One) {
                    // TODO reference
                    var field_rec_name = fieldname + '.rec_name';
                    if (values.hasOwnProperty(field_rec_name)) {
                        this._values[field_rec_name] = values[field_rec_name];
                    } else if (this._values.hasOwnProperty(field_rec_name)) {
                        delete this._values[field_rec_name];
                    }
                }
                this.model.fields[fieldname].set_on_change(this, value);
            }
            for (fieldname in later) {
                if (!later.hasOwnProperty(fieldname)) {
                    continue;
                }
                value = later[fieldname];
                var field_x2many = this.model.fields[fieldname];
                try {
                    field_x2many.in_on_change = true;
                    field_x2many.set_on_change(this, value);
                } finally {
                    field_x2many.in_on_change = false;
                }
            }
        },
        expr_eval: function(expr) {
            if (typeof(expr) != 'string') return expr;
            var ctx = jQuery.extend({}, this.get_context());
            ctx.context = jQuery.extend(this.model.session.context, ctx);
            jQuery.extend(ctx, this.get_eval());
            ctx.active_model = this.model.name;
            ctx.active_id = this.id;
            ctx._user = this.model.session.user_id;
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
        validate: function(fields, softvalidation) {
            var prms = [];
            if (fields === undefined) {
                fields = null;
            }
            (fields || ['*']).forEach(function(field) {
                prms.push(this.load(field));
            }.bind(this));
            return jQuery.when.apply(jQuery, prms).then(function() {
                var result = true;
                var exclude_fields = [];
                this.group.screens.forEach(function(screen) {
                    if (screen.exclude_field) {
                        exclude_fields.push(screen.exclude_field);
                    }
                });
                for (var fname in this.model.fields) {
                    if (!this.model.fields.hasOwnProperty(fname)) {
                        continue;
                    }
                    var field = this.model.fields[fname];
                    if ((fields !== null) &&
                        (!~fields.indexOf(fname))) {
                        continue;
                    }
                    if (field.get_state_attrs(this).readonly) {
                        continue;
                    }
                    if (~exclude_fields.indexOf(fname)) {
                        continue;
                    }
                    if (!field.validate(this, softvalidation)) {
                        result = false;
                    }
                }
                return result;
            }.bind(this));
        },
        pre_validate: function() {
            // TODO
            return jQuery.when();
        },
        cancel: function() {
            this._loaded = {};
            this._changed = {};
        },
        get_loaded: function(fields) {
            if (!jQuery.isEmptyObject(fields)) {
                var result = true;
                fields.forEach(function(field) {
                    if (!(field in this._loaded)) {
                        result = false;
                    }
                }.bind(this));
                return result;
            }
            return Sao.common.compare(Object.keys(this.model.fields),
                    Object.keys(this._loaded));
        },
        deleted: function() {
            return Boolean(~this.group.record_deleted.indexOf(this));
        },
        removed: function() {
            return Boolean(~this.group.record_removed.indexOf(this));
        }
    });


    Sao.field = {};

    Sao.field.get = function(type) {
        switch (type) {
            case 'char':
                return Sao.field.Char;
            case 'selection':
                return Sao.field.Selection;
            case 'datetime':
                return Sao.field.DateTime;
            case 'date':
                return Sao.field.Date;
            case 'time':
                return Sao.field.Time;
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
            default:
                return Sao.field.Char;
        }
    };

    Sao.field.Field = Sao.class_(Object, {
        _default: null,
        init: function(description) {
            this.description = description;
            this.name = description.name;
        },
        set: function(record, value) {
            record._values[this.name] = value;
        },
        get: function(record) {
            return record._values[this.name] || this._default;
        },
        set_client: function(record, value, force_change) {
            var previous_value = this.get(record);
            this.set(record, value);
            if (previous_value != this.get(record)) {
                record._changed[this.name] = true;
                this.changed(record).done(function() {
                    // TODO parent
                    record.validate(null, true).then(function() {
                        record.group.changed().done(function() {
                            var root_group = record.group.root_group();
                            root_group.screens.forEach(function(screen) {
                                screen.display();
                            });
                        });
                    });
                });
            } else if (force_change) {
                record._changed[this.name] = true;
                this.changed(record).done(function() {
                    record.validate(null, true).then(function() {
                        var root_group = record.group.root_group();
                        root_group.screens.forEach(function(screen) {
                            screen.display();
                        });
                    });
                });
            }
        },
        get_client: function(record) {
            return this.get(record);
        },
        set_default: function(record, value) {
            record._values[this.name] = value;
            record._changed[this.name] = true;
        },
        set_on_change: function(record, value) {
            record._values[this.name] = value;
            record._changed[this.name] = true;
        },
        changed: function(record) {
            var prms = [];
            // TODO check readonly
            if (this.description.on_change) {
                prms.push(record.on_change(this.name,
                            this.description.on_change));
            }
            prms.push(record.on_change_with(this.name));
            // TODO autocomplete_with
            return jQuery.when.apply(jQuery, prms);
        },
        get_context: function(record) {
            var context = jQuery.extend({}, record.get_context());
            if (record.group.parent) {
                jQuery.extend(context, record.group.parent.get_context());
            }
            // TODO eval context attribute
            return context;
        },
        get_domains: function(record) {
            var inversion = new Sao.common.DomainInversion();
            var screen_domain = inversion.domain_inversion(
                    record.group.domain4inversion(), this.name,
                    Sao.common.EvalEnvironment(record));
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
            return [inversion.localize_domain(screen_domain), attr_domain];
        },
        validation_domains: function(record) {
            var domains = this.get_domains(record);
            var screen_domain = domains[0];
            var attr_domain = domains[1];
            var inversion = new Sao.common.DomainInversion();
            if (!jQuery.isEmptyObject(attr_domain)) {
                return [screen_domain, [screen_domain,
                    inversion.unlocalize_domain(attr_domain, this.name)]];
            } else {
                return [screen_domain, screen_domain];
            }
        },
        get_eval: function(record) {
            return this.get(record);
        },
        get_on_change_value: function(record) {
            return this.get_eval(record);
        },
        set_state: function(record, states) {
            if (states === undefined) {
                states = ['readonly', 'required', 'invisible'];
            }
            var state_changes = record.expr_eval(
                    this.description.states || {});
            states.forEach(function(state) {
                if ((state == 'readonly') && this.description.readonly) {
                    return;
                }
                if (state_changes[state] !== undefined) {
                    this.get_state_attrs(record)[state] = state_changes[state];
                } else if (this.description[state] !== undefined) {
                    this.get_state_attrs(record)[state] =
                        this.description[state];
                }
            }.bind(this));
            // TODO group readonly
            // TODO domain readonly
        },
        get_state_attrs: function(record) {
            if (!(this.name in record.state_attrs)) {
                record.state_attrs[this.name] = jQuery.extend(
                        {}, this.description);
            }
            // TODO group readonly
            return record.state_attrs[this.name];
        },
        check_required: function(record) {
            var state_attrs = this.get_state_attrs(record);
            if (state_attrs.required == 1) {
                if (!this.get(record) && (state_attrs.readonly != 1)) {
                    return false;
                }
            }
            return true;
        },
        validate: function(record, softvalidation) {
            var result = true;
            if (this.description.readonly) {
                return true;
            }
            this.get_state_attrs(record).domain_readonly = false;
            var domains = this.validation_domains(record);
            var inverted_domain = domains[0];
            var domain = domains[1];
            if (!softvalidation) {
                result &= this.check_required(record);
            }
            if (typeof domain == 'boolean') {
                result &= domain;
            } else if (Sao.common.compare(domain, [['id', '=', null]])) {
                result = false;
            } else {
                var inversion = new Sao.common.DomainInversion();
                if ((inverted_domain instanceof Array) &&
                        (inverted_domain.length == 1) &&
                        (inverted_domain[0][1] == '=')) {
                    // If the inverted domain is so constraint that only one
                    // value is possible we should use it. But we must also pay
                    // attention to the fact that the original domain might be
                    // a 'OR' domain and thus not preventing the modification
                    // of fields.
                    var leftpart = inverted_domain[0][0];
                    var value = inverted_domain[0][2];
                    if (value === false) {
                        // XXX to remove once server domains are fixed
                        value = null;
                    }
                    var setdefault = true;
                    if (leftpart.contains('.')) {
                        var recordpart = leftpart.split('.', 1)[0];
                        var localpart = leftpart.split('.', 1)[1];
                        var original_domain = inversion.merge(
                                record.group.domain());
                        var constraintfields = [];
                        if (original_domain[0] == 'AND') {
                            inverted_domain.localize_domain(
                                    original_domain.slice(1))
                                .forEach(function(leaf) {
                                    constraintfields.push(leaf);
                                });
                        }
                        if ((localpart != 'id') ||
                                !~constraintfields.indexOf(recordpart)) {
                            setdefault = false;
                        }
                    }
                    if (setdefault) {
                        this.set_client(record, value);
                        this.get_state_attrs(record).domain_readonly = true;
                    }
                }
                result &= inversion.eval_domain(domain,
                        Sao.common.EvalEnvironment(record));
            }
            this.get_state_attrs(record).valid = result;
            return result;
        }
    });

    Sao.field.Char = Sao.class_(Sao.field.Field, {
        _default: ''
    });

    Sao.field.Selection = Sao.class_(Sao.field.Field, {
        _default: null,
        get_client: function(record) {
            return record._values[this.name];
        }
    });

    Sao.field.DateTime = Sao.class_(Sao.field.Field, {
        _default: null
    });

    Sao.field.Date = Sao.class_(Sao.field.Field, {
        _default: null
    });

    Sao.field.Time = Sao.class_(Sao.field.Field, {
    });

    Sao.field.Number = Sao.class_(Sao.field.Field, {
        _default: null,
        get: function(record) {
            if (record._values[this.name] === undefined) {
                return this._default;
            } else {
                return record._values[this.name];
            }
        },
        digits: function(record) {
            var digits = [];
            var default_ = [16, 2];
            var record_digits = record.expr_eval(
                this.description.digits || default_);
            for (var idx in record_digits) {
                if (record_digits[idx] !== null) {
                    digits.push(record_digits[idx]);
                } else {
                    digits.push(default_[idx]);
                }
            }
            return digits;
        }
    });

    Sao.field.Float = Sao.class_(Sao.field.Number, {
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
        set_client: function(record, value, force_change) {
            if (typeof value == 'string') {
                value = Number(value);
                if (isNaN(value)) {
                    value = this._default;
                }
            }
            Sao.field.Float._super.set_client.call(this, record, value,
                force_change);
        },
        get_client: function(record) {
            var value = record._values[this.name];
            if (value) {
                var digits = this.digits(record);
                return value.toFixed(digits[1]);
            } else {
                return '';
            }
        }
    });

    Sao.field.Numeric = Sao.class_(Sao.field.Number, {
        set_client: function(record, value, force_change) {
            if (typeof value == 'string') {
                value = new Sao.Decimal(value);
                if (isNaN(value.valueOf())) {
                    value = this._default;
                }
            }
            Sao.field.Float._super.set_client.call(this, record, value,
                force_change);
        },
        get_client: function(record) {
            var value = record._values[this.name];
            if (value) {
                var digits = this.digits(record);
                return value.toFixed(digits[1]);
            } else {
                return '';
            }
        }
    });

    Sao.field.Integer = Sao.class_(Sao.field.Number, {
        set_client: function(record, value, force_change) {
            if (typeof value == 'string') {
                value = parseInt(value, 10);
                if (isNaN(value)) {
                    value = this._default;
                }
            }
            Sao.field.Integer._super.set_client.call(this, record, value,
                force_change);
        },
        get_client: function(record) {
            var value = record._values[this.name];
            if (value) {
                return '' + value;
            } else {
                return '';
            }
        },
        digits: function(record) {
            return [16, 0];
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
        get: function(record) {
            var value = record._values[this.name];
            // TODO force parent
            return value;
        },
        get_client: function(record) {
            var rec_name = record._values[this.name + '.rec_name'];
            if (rec_name === undefined) {
                this.set(record, this.get(record));
                rec_name = record._values[this.name + '.rec_name'] || '';
            }
            return rec_name;
        },
        set: function(record, value) {
            var rec_name = record._values[this.name + '.rec_name'] || '';
            // TODO force parent
            var store_rec_name = function(rec_name) {
                record._values[this.name + '.rec_name'] = rec_name[0].rec_name;
            };
            if (!rec_name && (value >= 0) && (value !== null)) {
                var model_name = record.model.fields[this.name].description
                    .relation;
                Sao.rpc({
                    'method': 'model.' + model_name + '.' + 'read',
                    'params': [[value], ['rec_name'], record.get_context()]
                }, record.model.session).done(store_rec_name.bind(this));
            } else {
                store_rec_name.call(this, [{'rec_name': rec_name}]);
            }
            record._values[this.name] = value;
            // TODO force parent
        },
        set_client: function(record, value, force_change) {
            var rec_name;
            if (value instanceof Array) {
                rec_name = value[1];
                value = value[0];
            } else {
                if (value == this.get(record)) {
                    rec_name = record._values[this.name + '.rec_name'] || '';
                } else {
                    rec_name = '';
                }
            }
            record._values[this.name + '.rec_name'] = rec_name;
            Sao.field.Many2One._super.set_client.call(this, record, value,
                    force_change);
        },
        validation_domains: function(record) {
            var screen_domain = this.get_domains(record)[0];
            return [screen_domain, screen_domain];
        },
        get_domain: function(record) {
            var domains = this.get_domains(record);
            var screen_domain = domains[0];
            var attr_domain = domains[1];
            var inversion = new Sao.common.DomainInversion();
            return [inversion.localize_domain(
                    inversion.inverse_leaf(screen_domain), this.name),
                   attr_domain];
        }
    });

    Sao.field.One2One = Sao.class_(Sao.field.Many2One, {
    });

    Sao.field.One2Many = Sao.class_(Sao.field.Field, {
        init: function(description) {
            Sao.field.One2Many._super.init.call(this, description);
            this.in_on_change = false;
            this.context = {};
        },
        _default: null,
        _set_value: function(record, value, default_) {
            var mode;
            if ((value instanceof Array) && !isNaN(parseInt(value[0], 10))) {
                mode = 'list ids';
            } else {
                mode = 'list values';
            }
            var group = record._values[this.name];
            var model;
            if (group !== undefined) {
                model = group.model;
                group.destroy();
                // TODO unconnect
            } else if (record.model.name == this.description.relation) {
                model = record.model;
            } else {
                model = new Sao.Model(this.description.relation);
            }
            var prm = jQuery.when();
            if ((mode == 'list values') && !jQuery.isEmptyObject(value)) {
                var context = this.get_context(record);
                var field_names = {};
                for (var val in value) {
                    if (!value.hasOwnProperty(val)) {
                        continue;
                    }
                    for (var fieldname in val) {
                        if (!val.hasOwnProperty(fieldname)) {
                            continue;
                        }
                        field_names[fieldname] = true;
                    }
                }
                if (!jQuery.isEmptyObject(field_names)) {
                    var args = {
                        'method': 'model.' + this.description.relation +
                            '.fields_get',
                        'params': [Object.keys(field_names), context]
                    };
                    prm = Sao.rpc(args, record.model.session);
                }
            }
            var set_value = function(fields) {
                var group = Sao.Group(model, this.context, []);
                group.set_parent(record);
                group.parent_name = this.description.relation_field;
                group.child_name = this.name;
                if (!jQuery.isEmptyObject(fields)) {
                    group.model.add_fields(fields);
                }
                if (record._values[this.name] !== undefined) {
                    for (var i = 0, len = record._values[this.name].length;
                            i < len; i++) {
                        var r = record._values[this.name][i];
                        if (r.id >= 0) {
                            group.record_deleted.push(r);
                        }
                    }
                    jQuery.extend(group.record_deleted,
                            record._values[this.name].record_deleted);
                    jQuery.extend(group.record_removed,
                            record._values[this.name].record_removed);
                }
                record._values[this.name] = group;
                if (mode == 'list ids') {
                    group.load(value);
                } else {
                    for (var vals in value) {
                        if (!value.hasOwnProperty(vals)) {
                            continue;
                        }
                        var new_record = group.new_(false);
                        if (default_) {
                            new_record.set_default(vals);
                            group.add(new_record);
                        } else {
                            new_record.id *= 1;
                            new_record.set(vals);
                            group.push(new_record);
                        }
                    }
                }
            };
            return prm.pipe(set_value.bind(this));
        },
        set: function(record, value) {
            return this._set_value(record, value, false);
        },
        get: function(record) {
            var group = record._values[this.name];
            if (group === undefined) {
                return [];
            }
            var record_removed = group.record_removed;
            var record_deleted = group.record_deleted;
            var result = [['add', []]];
            var parent_name = this.description.relation_field || '';
            for (var i = 0, len = group.length; i < len; i++) {
                var record2 = group[i];
                if (~record_removed.indexOf(record2) ||
                        ~record_deleted.indexOf(record2)) {
                    continue;
                }
                var values;
                if (record2.id >= 0) {
                    values = record2.get();
                    delete values[parent_name];
                    if (record2.has_changed() &&
                            !jQuery.isEmptyObject(values)) {
                        result.push(['write', [record2.id], values]);
                    }
                    result[0][1].push(record2.id);
                } else {
                    values = record2.get();
                    delete values[parent_name];
                    result.push(['create', values]);
                }
            }
            if (jQuery.isEmptyObject(result[0][1])) {
                result.shift();
            }
            if (!jQuery.isEmptyObject(record_removed)) {
                result.push(['unlink', record_removed.map(function(r) {
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
        },
        get_client: function(record) {
            this._set_default_value(record);
            return record._values[this.name];
        },
        set_default: function(record, value) {
            var previous_group = record._values[this.name];
            var prm = this._set_value(record, value, true);
            prm.done(function() {
                var group = record._values[this.name];
                if (previous_group) {
                    previous_group.forEach(function(r) {
                        if (r.id >= 0) {
                            group.record_deleted.push(r);
                        }
                    });
                    group.record_deleted = group.record_deleted.concat(
                        previous_group.record_deleted);
                    group.record_removed = group.record_removed.concat(
                        previous_group.record_removed);
                }
            }.bind(this));
            record._changed[this.name] = true;
        },
        set_on_change: function(record, value) {
            this._set_default_value(record);
            if (value instanceof Array) {
                this._set_value(record, value);
                record._changed[this.name] = true;
                record.group.changed();
                return;
            }
            var prm = jQuery.when();
            if (value.add || value.update) {
                var context = this.get_context(record);
                var fields = record._values[this.name].model.fields;
                var field_names = {};
                [value.add, value.update].forEach(function(l) {
                    if (!jQuery.isEmptyObject(l)) {
                        l.forEach(function(v) {
                            Object.keys(v).forEach(function(f) {
                                if (!(f in fields) &&
                                    (f != 'id')) {
                                        field_names[f] = true;
                                    }
                            });
                        });
                    }
                });
                if (!jQuery.isEmptyObject(field_names)) {
                    var args = {
                        'method': 'model.' + this.description.relation +
                            '.fields_get',
                        'params': [Object.keys(field_names), context]
                    };
                    prm = Sao.rpc(args, record.model.session);
                } else {
                    prm.resolve({});
                }
            }

            var to_remove = [];
            var group = record._values[this.name];
            group.forEach(function(record2) {
                if (!record2.id) {
                    to_remove.push(record2);
                }
            });
            if (value.remove) {
                value.remove.forEach(function(record_id) {
                    var record2 = group.get(record_id);
                    if (record2) {
                        to_remove.push(record2);
                    }
                }.bind(this));
            }
            to_remove.forEach(function(record2) {
                group.remove(record2, false, true, false);
            }.bind(this));

            if (value.add || value.update) {
                prm.then(function(fields) {
                    group.model.add_fields(fields);
                    if (value.add) {
                        value.add.forEach(function(vals) {
                            var new_record = group.new_(false);
                            group.add(new_record);
                            new_record.set_on_change(vals);
                        });
                    }
                    if (value.update) {
                        value.update.forEach(function(vals) {
                            if (!vals.id) {
                                return;
                            }
                            var record2 = group.get(vals.id);
                            if (record2) {
                                record2.set_on_change(vals);
                            }
                        });
                    }
                }.bind(this));
            }
        },
        _set_default_value: function(record) {
            if (record._values[this.name] !== undefined) {
                return;
            }
            var group = Sao.Group(new Sao.Model(this.description.relation),
                    this.context, []);
            group.set_parent(record);
            group.parent_name = this.description.relation_field;
            group.child_name = this.name;
            if (record.model.name == this.description.relation) {
                group.fields = record.model.fields;
            }
            record._values[this.name] = group;
        },
        get_eval: function(record) {
            var result = [];
            var group = record._values[this.name];
            if (group === undefined) return result;

            var record_removed = group.record_removed;
            var record_deleted = group.record_deleted;
            for (var i = 0, len = record._values[this.name].length; i < len;
                    i++) {
                var record2 = group[i];
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
            for (var i = 0, len = record._values[this.name].length; i < len;
                    i++) {
                var record2 = group[i];
                if (!record2.deleted() || !record2.removed())
                    result.push(record2.get_on_change_value());
            }
            return result;
        },
        changed: function(record) {
            if (!this.in_on_change) {
                return Sao.field.One2Many._super.changed.call(this, record);
            }
        },
        get_domain: function(record) {
            var domains = this.get_domains(record);
            var screen_domain = domains[0];
            var attr_domain = domains[1];
            var inversion = new Sao.common.DomainInversion();
            return [inversion.localize_domain(
                    inversion.inverse_leaf(screen_domain)),
                   attr_domain];
        },
        validation_domains: function(record) {
            var screen_domain = this.get_domains(record)[0];
            return [screen_domain, screen_domain];
        },
        set_state: function(record, states) {
            this._set_default_value(record);
            Sao.field.One2Many._super.set_state.call(this, record, states);
            record._values[this.name].readonly = this.get_state_attrs(record)
                .readonly;
        }
    });

    Sao.field.Many2Many = Sao.class_(Sao.field.One2Many, {
        set: function(record, value) {
            var group = record._values[this.name];
            var model;
            if (group !== undefined) {
                model = group.model;
                group.destroy();
                // TODO unconnect
            } else if (record.model.name == this.description.relation) {
                model = record.model;
            } else {
                model = new Sao.Model(this.description.relation);
            }
            group = Sao.Group(model, this.context, []);
            group.set_parent(record);
            group.parent_name = this.description.relation_field;
            group.child_name = this.name;
            if (record._values[this.name] !== undefined) {
                jQuery.extend(group.record_removed, record._values[this.name]);
                jQuery.extend(group.record_deleted,
                    record._values[this.name].record_deleted);
                jQuery.extend(group.record_removed,
                    record._values[this.name].record_removed);
            }
            record._values[this.name] = group;
            group.load(value);
        },
        get_on_change_value: function(record) {
            return this.get_eval(record);
        }
    });
}());
