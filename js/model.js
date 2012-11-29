/* This file is part of Tryton.  The COPYRIGHT file at the top level of
   this repository contains the full copyright notices and license terms. */
'use strict';

Sao.Model = Class(Object, {
    init: function(name, attributes) {
              this.name = name;
              this.session = Sao.Session.current_session;
              this.fields = {};
              this.context = attributes.context || {};
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
              var prm = this.execute('search',
                      [condition, offset, limit, order], context);
              var instanciate = function(ids) {
                  return Sao.Group(this, ids.map(function(id) {
                      return new Sao.Record(this, id);
                  }));
              };
              return prm.pipe(instanciate.bind(this));
          },
    delete: function(records) {
                var context = {}; // TODO
                return this.execute('delete', [records.map(function(record) {
                    return record.id;
                })], context);
            }
});

Sao.Group = function(model, array) {
    array.model = model;
    return array;
};

Sao.Record = Class(Object, {
    id_counter: -1,
    init: function(model, id) {
              this.model = model;
              this.id = id || Sao.Record.prototype.id_counter--;
              this._values = {};
              this._changed = {};
              this._loaded = {};
              this.fields = {};
          },
    has_changed: function() {
                     return !jQuery.isEmptyObject(this._changed);
                 },
    _get_values: function(fields) {
                     if (!fields) {
                         fields = Object.keys(this._values);
                     }
                     var values = {};
                     for (var i = 0, len = fields.length; i < len; i++) {
                         var name = fields[i];
                         var field = this.model.fields[name];
                         values[name] = field.get(this);
                     }
                     return values;
                 },
    save: function() {
              // TODO context
              var context = {};
              var prm, values;
              if (this.id < 0) {
                  values = this._get_values();
                  prm = this.model.execute('create', [values], context);
                  var created = function(id) {
                      this.id = id;
                  };
                  prm.done(created.bind(this));
              } else {
                  if (!this.has_changed()) {
                      return jQuery.when();
                  }
                  values = this._get_values(Object.keys(this._changed));
                  prm = this.model.execute('write', [this.id, values], context);
              }
              prm.done(this.reload);
              return prm;
          },
    reload: function() {
                this._values = {};
                this._loaded = {};
                this._changed = {};
            },
    load: function(name) {
              if ((this.id < 0) || !(name in this._loaded)) {
                  return jQuery.when();
              }
              var id2record = {};
              id2record[this.id] = this;
              var loading;
              if (name == '*') {
                  loading = 'eager';
                  for (var fname in this.model.fields) {
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
              // TODO group
              var context = {}; // TODO
              var fnames = [];
              if (loading == 'eager') {
                  for (var fname in this.model.fields) {
                      if (!this.model.fields.hasOwnProperty(fname)) {
                          continue;
                      }
                      if ((this.mode.fields[fname].description.loading ||
                                  'eager') == 'eager') {
                          fnames.push(fname);
                      }
                  }
              } else {
                  fnames = Object.keys(this.model.fields);
              }
              fnames = fnames.filter(function(e, i, a) {
                  return !(e in this._loaded);
              });
              // TODO add rec_name
              if (!('rec_name' in fnames)) {
                  fnames.push('rec_name');
              }
              fnames.push('_timestamp');
              // TODO size of binary
              prm = this.model.execute('read', [Object.keys(id2record),
                      fnames], context);
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
                      value = id2value[id];
                      if (record && value) {
                          record.set(value);
                      }
                  }
              };
              var failed = function() {
                  // TODO  call succeed
              };
              return prm;
          },
    get: function(name) {
             return this.model.fields[name].get(this);
         },
    set: function(name, value) {
             this.model.fields[name].set(this, value);
         },
    get_client: function(name) {
                    return this.model.fields[name].get_client(this);
                },
    set_client: function(name) {
                    this.model.fields[name].set_client(this, value);
                }
});

Sao.field = {};

Sao.field.get = function(type) {
    switch (type) {
        default:
            return Sao.field.Char;
    }
};

Sao.field.Field = Class(Object, {
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
    set_client: function(record, value) {
                    var previous_value = this.get(record);
                    this.set(record, value);
                    if (previous_value != this.get(record)) {
                        record._changed[this.name] = true;
                        this.changed(record);
                    }
                },
    get_client: function(record) {
                    return this.get(record);
                },
    changed: function(record) {
                 // TODO
             }
});

Sao.field.Char = Class(Sao.field.Field, {
    _default: ''
});
