/* This file is part of Tryton.  The COPYRIGHT file at the top level of
   this repository contains the full copyright notices and license terms. */
(function() {
    'use strict';

    Sao.common = {};

    Sao.common.BACKSPACE_KEYCODE = 8;
    Sao.common.TAB_KEYCODE = 9;
    Sao.common.RETURN_KEYCODE = 13;
    Sao.common.ESC_KEYCODE = 27;
    Sao.common.UP_KEYCODE = 38;
    Sao.common.DOWN_KEYCODE = 40;
    Sao.common.DELETE_KEYCODE = 46;
    Sao.common.F2_KEYCODE = 113;
    Sao.common.F3_KEYCODE = 114;

    Sao.common.SELECTION_NONE = 1;
    Sao.common.SELECTION_SINGLE = 2;
    Sao.common.SELECTION_MULTIPLE = 3;

    Sao.common.compare = function(arr1, arr2) {
        if (arr1.length != arr2.length) {
            return false;
        }
        for (var i = 0; i < arr1.length; i++) {
            var a = arr1[i], b = arr2[i];
            if ((a instanceof Array) && (b instanceof Array)) {
                if (!Sao.common.compare(a, b)) {
                    return false;
                }
            } else if (moment.isMoment(a) && moment.isMoment(b)) {
                if ((a.isDate != b.isDate) &&
                    (a.isDateTime != b.isDateTime) &&
                    (a.valueOf() != b.valueOf())) {
                    return false;
                }
            } else if (moment.isDuration(a) && moment.isDuration(b)) {
                if (a.valueOf() != b.valueOf()) {
                    return false;
                }
            } else if ((a instanceof Number) || (b instanceof Number)) {
                if (Number(a) !== Number(b)) {
                    return false;
                }
            } else if (a != b) {
                return false;
            }
        }
        return true;
    };

    Sao.common.contains = function(array1, array2) {
        for (var i = 0; i < array1.length; i++) {
            if (Sao.common.compare(array1[i], array2)) {
                return true;
            }
        }
        return false;
    };

    // Find the intersection of two arrays.
    // The arrays must be sorted.
    Sao.common.intersect = function(a, b) {
        var ai = 0, bi = 0;
        var result = [];
        while (ai < a.length && bi < b.length) {
            if (a[ai] < b[bi]) {
                ai++;
            } else if (a[ai] > b[bi]) {
                bi++;
            } else {
                result.push(a[ai]);
                ai++;
                bi++;
            }
        }
        return result;
    };

    Sao.common.scrollIntoViewIfNeeded = function(element) {
        element = element[0];
        if (element) {
            var rect = element.getBoundingClientRect();
            if (rect.bottom > window.innerHeight) {
                element.scrollIntoView(false);
            }
            if (rect.top < 0) {
                element.scrollIntoView();
            }
        }
    };

    // Handle click and Return press event
    // If one, the handler is executed at most once for both events
    Sao.common.click_press = function(func, one) {
        return function handler(evt) {
            if (evt.type != 'keypress' ||
                    evt.which == Sao.common.RETURN_KEYCODE) {
                if (one) {
                    jQuery(this).off('click keypress', null, handler);
                }
                return func(evt);
            }
        };
    };

    // Cartesian product
    Sao.common.product = function(array, repeat) {
        repeat = repeat || 1;
        var pools = [];
        var i = 0;
        while (i < repeat) {
            pools = pools.concat(array);
            i++;
        }
        var result = [[]];
        for (const pool of pools) {
            var tmp = [];
            for (const x of result) {
                for (const y of pool) {
                    tmp.push(x.concat([y]));
                }
            }
            result = tmp;
        }
        return result;
    };

    Sao.common.selection = function(title, values, alwaysask=false) {
        var prm = jQuery.Deferred();
        if (jQuery.isEmptyObject(values)) {
            prm.reject();
            return prm;
        }
        var keys = Object.keys(values).sort();
        if ((keys.length == 1) && (!alwaysask)) {
            var key = keys[0];
            prm.resolve(values[key]);
            return prm;
        }
        var dialog = new Sao.Dialog(
                title || Sao.i18n.gettext('Your selection:'),
                'selection-dialog');

        keys.forEach(function(k, i) {
            jQuery('<div/>', {
                'class': 'radio'
            }).append(jQuery('<label/>')
                .text(' ' + k)
                .prepend(jQuery('<input/>', {
                    'type': 'radio',
                    'name': 'selection',
                    'value': i
                })))
            .appendTo(dialog.body);
        });
        dialog.body.find('input').first().prop('checked', true);

        jQuery('<button/>', {
            'class': 'btn btn-link',
            'type': 'button',
            'title': Sao.i18n.gettext("Cancel"),
        }).text(Sao.i18n.gettext('Cancel')).click(function() {
            dialog.modal.modal('hide');
            prm.reject();
        }).appendTo(dialog.footer);
        jQuery('<button/>', {
            'class': 'btn btn-primary',
            'type': 'button',
            'title': Sao.i18n.gettext("OK"),
        }).text(Sao.i18n.gettext('OK')).click(function() {
            var i = dialog.body.find('input:checked').attr('value');
            dialog.modal.modal('hide');
            prm.resolve(values[keys[i]]);
        }).appendTo(dialog.footer);
        dialog.modal.on('hidden.bs.modal', function(e) {
            jQuery(this).remove();
        });
        dialog.modal.modal('show');
        return prm;
    };

    Sao.common.moment_format = function(format) {
        return format
            .replace('%a', 'ddd')
            .replace('%A', 'dddd')
            .replace('%w', 'd')
            .replace('%d', 'DD')
            .replace('%b', 'MMM')
            .replace('%B', 'MMMM')
            .replace('%m', 'MM')
            .replace('%y', 'YY')
            .replace('%Y', 'YYYY')
            .replace('%H', 'HH')
            .replace('%I', 'hh')
            .replace('%p', 'A')
            .replace('%M', 'mm')
            .replace('%S', 'ss')
            .replace('%f', 'SSS')
            .replace('%z', 'ZZ')
            .replace('%Z', 'zz')
            .replace('%j', 'DDDD')
            .replace('%U', 'ww')
            .replace('%W', 'WW')
            .replace('%c', 'llll')
            .replace('%x', 'L')
            .replace('%X', 'LTS')
            .replace('%', '%%')
            ;
    };

    Sao.common.DATE_OPERATORS = [
        ['S', moment.duration(-1, 'seconds')],
        ['s', moment.duration(1, 'seconds')],
        ['I', moment.duration(-1, 'minutes')],
        ['i', moment.duration(1, 'minutes')],
        ['H', moment.duration(-1, 'hours')],
        ['h', moment.duration(1, 'hours')],
        ['D', moment.duration(-1, 'days')],
        ['d', moment.duration(1, 'days')],
        ['W', moment.duration(-1, 'weeks')],
        ['w', moment.duration(1, 'weeks')],
        ['M', moment.duration(-1, 'months')],
        ['m', moment.duration(1, 'months')],
        ['Y', moment.duration(-1, 'years')],
        ['y', moment.duration(1, 'years')],
    ];

    Sao.common.date_format = function(format) {
        return Sao.common.moment_format(
            format || Sao.i18n.locale.date || '%x');
    };

    Sao.common.format_time = function(format, date) {
        if (!date) {
            return '';
        }
        return date.format(Sao.common.moment_format(format));
    };

    Sao.common.parse_time = function(format, value) {
        var date = moment(value, Sao.common.moment_format(format));
        if (date.isValid()) {
            date = Sao.Time(
                date.hour(), date.minute(), date.second(), date.millisecond());
        } else {
            date = null;
        }
        return date;
    };

    Sao.common.format_date = function(date_format, date) {
        if (!date) {
            return '';
        }
        return date.format(Sao.common.moment_format(date_format));
    };

    Sao.common.parse_date = function(date_format, value) {
        var date = moment(value,
               Sao.common.moment_format(date_format));
        if (date.isValid()) {
            date = Sao.Date(date.year(), date.month(), date.date());
        } else {
            date = null;
        }
        return date;
    };

    Sao.common.format_datetime = function(datetime_format, date) {
        if (!date) {
            return '';
        }
        return date.format(Sao.common.moment_format(datetime_format));
    };

    Sao.common.parse_datetime = function(datetime_format, value) {
        var date = moment(value, Sao.common.moment_format(datetime_format));
        if (date.isValid()) {
            date = Sao.DateTime(date.year(), date.month(), date.date(),
                    date.hour(), date.minute(), date.second(),
                    date.millisecond());
        } else {
            date = null;
        }
        return date;
    };

    Sao.common.timedelta = {};
    Sao.common.timedelta.DEFAULT_CONVERTER = {
        's': 1
    };
    Sao.common.timedelta.DEFAULT_CONVERTER.m =
        Sao.common.timedelta.DEFAULT_CONVERTER.s * 60;
    Sao.common.timedelta.DEFAULT_CONVERTER.h =
        Sao.common.timedelta.DEFAULT_CONVERTER.m * 60;
    Sao.common.timedelta.DEFAULT_CONVERTER.d =
        Sao.common.timedelta.DEFAULT_CONVERTER.h * 24;
    Sao.common.timedelta.DEFAULT_CONVERTER.w =
        Sao.common.timedelta.DEFAULT_CONVERTER.d * 7;
    Sao.common.timedelta.DEFAULT_CONVERTER.M =
        Sao.common.timedelta.DEFAULT_CONVERTER.d * 30;
    Sao.common.timedelta.DEFAULT_CONVERTER.Y =
        Sao.common.timedelta.DEFAULT_CONVERTER.d * 365;
    Sao.common.timedelta._get_separator = function() {
        return {
            Y: Sao.i18n.gettext('Y'),
            M: Sao.i18n.gettext('M'),
            w: Sao.i18n.gettext('w'),
            d: Sao.i18n.gettext('d'),
            h: Sao.i18n.gettext('h'),
            m: Sao.i18n.gettext('m'),
            s: Sao.i18n.gettext('s')
        };
    };
    Sao.common.timedelta.format = function(value, converter) {
        if (!value) {
            return '';
        }
        if (!converter) {
            converter = Sao.common.timedelta.DEFAULT_CONVERTER;
        }
        var text = [];
        value = value.asSeconds();
        var sign = '';
        if (value < 0) {
            sign = '-';
        }
        value = Math.abs(value);
        converter = Object.keys(
            Sao.common.timedelta._get_separator()).map(function(key) {
                return [key, converter[key]];
            });
        var values = [];
        var k, v;
        for (var i = 0; i < converter.length; i++) {
            k = converter[i][0];
            v = converter[i][1];
            if (v) {
                var part = Math.floor(value / v);
                value -= part * v;
                values.push(part);
            } else {
                values.push(0);
            }
        }
        for (i = 0; i < converter.length - 3; i++) {
            k = converter[i][0];
            v = values[i];
            if (v) {
                text.push(v + Sao.common.timedelta._get_separator()[k]);
            }
        }
        if (jQuery(values.slice(-3)).is(function(i, v) { return v; }) ||
                jQuery.isEmptyObject(text)) {
            var time_values = values.slice(-3);
            var time = time_values[0].toString().padStart(2, "0");
            time += ":" + time_values[1].toString().padStart(2, "0");
            if (time_values[2] || value) {
                time += ':' + time_values[2].toString().padStart(2, "0");
            }
            text.push(time);
        }
        text = sign + text.reduce(function(p, c) {
            if (p) {
                return p + ' ' + c;
            } else {
                return c;
            }
        });
        if (value) {
            if (!jQuery(values.slice(-3)).is(function(i, v) { return v; })) {
                // Add space if no time
                text += ' ';
            }
            text += ('' + value.toFixed(6)).slice(1);
        }
        return text;
    };
    Sao.common.timedelta.parse = function(text, converter) {
        if (!text) {
            return null;
        }
        if (!converter) {
            converter = Sao.common.timedelta.DEFAULT_CONVERTER;
        }
        var separators = Sao.common.timedelta._get_separator();
        var separator;
        for (var k in separators) {
            separator = separators[k];
            text = text.replace(separator, separator + ' ');
        }

        var seconds = 0;
        var sec;
        var parts = text.split(' ');
        for (var i = 0; i < parts.length; i++) {
            var part = parts[i];
            if (part.contains(':')) {
                var subparts = part.split(':');
                var subconverter = [
                    converter.h, converter.m, converter.s];
                for (var j = 0;
                        j < Math.min(subparts.length, subconverter.length);
                        j ++) {
                    var t = subparts[j];
                    var v = subconverter[j];
                    sec = Math.abs(parseFloat(t)) * v;
                    if (!isNaN(sec)) {
                        seconds += sec;
                    }
                }
            } else {
                var found = false;
                for (var key in separators) {
                    separator =separators[key];
                    if (part.endsWith(separator)) {
                        part = part.slice(0, -separator.length);
                        sec = Math.abs(parseFloat(part)) * converter[key];
                        if (!isNaN(sec)) {
                            seconds += sec;
                        }
                        found = true;
                        break;
                    }
                }
                if (!found) {
                    sec = Math.abs(parseFloat(part));
                    if (!isNaN(sec)) {
                        seconds += sec;
                    }
                }
            }
        }
        if (text.contains('-')) {
            seconds *= -1;
        }
        return Sao.TimeDelta(null, seconds);
    };

    Sao.common.btoa = function(value) {
        var strings = [], chunksize = 0xffff;
        // JavaScript Core has hard-coded argument limit of 65536
        // String.fromCharCode can not be called with too many
        // arguments
        for (var j = 0; j * chunksize < value.length; j++) {
            strings.push(String.fromCharCode.apply(
                null, value.subarray(
                    j * chunksize, (j + 1) * chunksize)));
        }
        return btoa(strings.join(''));
    };

    Sao.common.atob = function(value) {
       // javascript's atob does not understand linefeed
       // characters
       var byte_string = atob(value.base64.replace(/\s/g, ''));
       // javascript decodes base64 string as a "DOMString", we
       // need to convert it to an array of bytes
       var array_buffer = new ArrayBuffer(byte_string.length);
       var uint_array = new Uint8Array(array_buffer);
       for (var j=0; j < byte_string.length; j++) {
           uint_array[j] = byte_string.charCodeAt(j);
       }
       return uint_array;
    };

    Sao.common.ModelAccess = Sao.class_(Object, {
        init: function() {
            this.batchnum = 100;
            this._models = [];
            this._access = {};
        },
        load_models: function(refresh) {
            if (!refresh) {
                this._access = {};
            }
            try {
                this._models = Sao.rpc({
                    'method': 'model.ir.model.list_models',
                    'params': [{}]
                }, Sao.Session.current_session, false);
            } catch(e) {
                Sao.Logger.error("Unable to get model list.");
            }
        },
        get: function(model) {
            if (this._access[model] !== undefined) {
                return this._access[model];
            }
            var idx = this._models.indexOf(model);
            if (idx < 0) {
                this.load_models(false);
                idx = this._models.indexOf(model);
            }
            var to_load = this._models.slice(
                Math.max(0, idx - Math.floor(this.batchnum / 2)),
                idx + Math.floor(this.batchnum / 2));
            var access;
            try {
                access = Sao.rpc({
                    'method': 'model.ir.model.access.get_access',
                    'params': [to_load, {}]
                }, Sao.Session.current_session, false);
            } catch(e) {
                Sao.Logger.error(`Unable to get access for ${model}.`);
                access = {
                    model: {
                        'read': true,
                        'write': false,
                        'create': false,
                        'delete': false,
                    },
                };
            }
            this._access = jQuery.extend(this._access, access);
            return this._access[model];
        }
    });
    Sao.common.MODELACCESS = new Sao.common.ModelAccess();

    Sao.common.ModelHistory = Sao.class_(Object, {
        init: function() {
            this._models = [];
        },
        load_history: function() {
            this._models = [];
            return Sao.rpc({
                'method': 'model.ir.model.list_history',
                'params': [{}]
            }, Sao.Session.current_session).then(models => {
                this._models = models;
            });
        },
        contains: function(model) {
            return ~this._models.indexOf(model);
        }
    });
    Sao.common.MODELHISTORY = new Sao.common.ModelHistory();

    Sao.common.ModelName = Sao.class_(Object, {
        init: function() {
            this._names = {};
        },
        load_names: function() {
            this._names = Sao.rpc({
                'method':'model.ir.model.get_names',
                'params': [{}],
            }, Sao.Session.current_session, false);
        },
        get: function(model) {
            if (jQuery.isEmptyObject(this._names)) {
                this.load_names();
            }
            return this._names[model] || '';
        },
        clear: function() {
            this._names = {};
        },
    });
    Sao.common.MODELNAME = new Sao.common.ModelName();

    Sao.common.ModelNotification = Sao.class_(Object, {
        init: function() {
            this._depends = null;
        },
        load_names: function() {
            this._depends = Sao.rpc({
                'method': 'model.ir.model.get_notification',
                'params': [{}],
            }, Sao.Session.current_session, false);
        },
        get: function(model) {
            if (!this._depends) {
                this.load_names();
            }
            return this._depends[model] || [];
        },
    });
    Sao.common.MODELNOTIFICATION = new Sao.common.ModelNotification();

    Sao.common.ViewSearch = Sao.class_(Object, {
        init: function() {
            this.encoder = new Sao.PYSON.Encoder();
        },
        load_searches: function() {
            this.searches = {};
            return Sao.rpc({
                'method': 'model.ir.ui.view_search.get',
                'params': [{}]
            }, Sao.Session.current_session).then(searches => {
                this.searches = searches;
            });
        },
        get: function(model) {
            return this.searches[model] || [];
        },
        add: function(model, name, domain) {
            return Sao.rpc({
                'method': 'model.ir.ui.view_search.set',
                'params': [name, model, this.encoder.encode(domain), {}],
            }, Sao.Session.current_session).then(id => {
                if (this.searches[model] === undefined) {
                    this.searches[model] = [];
                }
                this.searches[model].push([id, name, domain, true]);
            });
        },
        remove: function(model, id) {
            return Sao.rpc({
                'method': 'model.ir.ui.view_search.unset',
                'params': [id, {}]
            }, Sao.Session.current_session).then(() => {
                for (var i = 0; i < this.searches[model].length; i++) {
                    var domain = this.searches[model][i];
                    if (domain[0] === id) {
                        this.searches[model].splice(i, 1);
                        break;
                    }
                }
            });
        }
    });
    Sao.common.VIEW_SEARCH = new Sao.common.ViewSearch();

    Sao.common.humanize = function(size, suffix) {
        suffix = suffix || '';
        var sizes, u;
        if ((0 < Math.abs(size)) && (Math.abs(size) < 1)) {
            sizes = ['', 'm', 'µ', 'n', 'p', 'f', 'a', 'z', 'y', 'r', 'q'];
            for (let i=0, len=sizes.length; i < len; i++) {
                u = sizes[i];
                if (Math.abs(size) >= 0.01) {
                    break;
                }
                if (i + 1 < len ) {
                    size *= 1000;
                }
            }
        } else {
            sizes = ['', 'k', 'M', 'G', 'T', 'P', 'E', 'Z', 'Y', 'R', 'Q'];
            for (let i=0, len= sizes.length; i < len; i++) {
                u = sizes[i];
                if (Math.abs(size) <= 1000) {
                    break;
                }
                if (i + 1 < len) {
                    size /= 1000;
                }
            }
        }
        size = size.toLocaleString(
            Sao.i18n.BC47(Sao.i18n.getlang()), {
                'minimumFractionDigits': 0,
                'maximumFractionDigits': Math.abs(size) < 0.01? 15 : 2,
            });
        return size + u + suffix;
    };

    Sao.common.EvalEnvironment = function(parent_, eval_type='eval') {
        var environment;
        if (eval_type == 'eval') {
            environment = parent_.get_eval();
        } else {
            environment = {};
            for (var key in parent_.model.fields) {
                var field = parent_.model.fields[key];
                environment[key] = field.get_on_change_value(parent_);
            }
        }
        environment.id = parent_.id;
        if (parent_.group.parent)
            Object.defineProperty(environment, '_parent_' +
                    parent_.group.parent_name, {
                'enumerable': true,
                'get': function() {
                    return Sao.common.EvalEnvironment(parent_.group.parent,
                        eval_type);
                }
            });
        environment.get = function(item, default_) {
            if (Object.prototype.hasOwnProperty.call(this, item))
                return this[item];
            return default_;
        };

        return environment;
    };

    Sao.common.selection_mixin = {};
    Sao.common.selection_mixin.init = function() {
        this.selection = null;
        this.help = null;
        this.inactive_selection = [];
        this._last_domain = null;
        this._values2selection = {};
        this._domain_cache = {};
        if (this.nullable_widget === undefined) {
            this.nullable_widget = true;
        }
    };
    Sao.common.selection_mixin.init_selection = function(value, callback) {
        if (!value) {
            value = {};
            for (const e of (this.attributes.selection_change_with || [])) {
                value[e] = null;
            }
        }
        var key = JSON.stringify(value);
        var selection = this.attributes.selection || [];
        var prm;
        let prepare_selection = selection => {
            selection = jQuery.extend([], selection);
            if (this.attributes.sort === undefined || this.attributes.sort) {
                selection.sort(function(a, b) {
                    return a[1].localeCompare(b[1]);
                });
            }
            this.selection = jQuery.extend([], selection);
            this.help = this.attributes.help_selection || {};
            if (callback) callback(this.selection, this.help);
        };
        if (!(selection instanceof Array) &&
                !(key in this._values2selection)) {
            if (!jQuery.isEmptyObject(this.attributes.selection_change_with)) {
                prm = this.model.execute(
                    selection, [value], {}, true, false);
            } else {
                prm = this.model.execute(
                    selection, [], {}, true, false);
            }
            prm = prm.then(selection => {
                this._values2selection[key] = selection;
                return selection;
            });
            prm = prm.then(prepare_selection);
        } else {
            if (key in this._values2selection) {
                selection = this._values2selection[key];
            }
            prepare_selection(selection);
            prm = jQuery.when();
        }
        this.inactive_selection = [];
        this._selection_prm = prm;
    };
    Sao.common.selection_mixin.update_selection = function(record, field,
            callback) {
        const _update_selection = () => {
            if (!field) {
                if (callback) {
                    callback(this.selection, this.help);
                }
                return;
            }
            var domain = field.get_domain(record);
            if (!('relation' in this.attributes)) {
                var change_with = this.attributes.selection_change_with || [];
                var value = record._get_on_change_args(change_with);
                delete value.id;
                Sao.common.selection_mixin.init_selection.call(
                    this, value, () => {
                        Sao.common.selection_mixin.filter_selection.call(
                            this, domain, record, field);
                        if (callback) {
                            callback(this.selection, this.help);
                        }
                    });
            } else {
                var context = field.get_context(record);
                var jdomain = JSON.stringify([domain, context]);
                if (jdomain in this._domain_cache) {
                    this.selection = this._domain_cache[jdomain];
                    this._last_domain = [domain, context];
                }
                if ((this._last_domain !== null) &&
                        Sao.common.compare(domain, this._last_domain[0]) &&
                        (JSON.stringify(context) ==
                         JSON.stringify(this._last_domain[1]))) {
                    if (callback) {
                        callback(this.selection, this.help);
                    }
                    return;
                }
                var fields = ['rec_name'];
                var help_field = this.attributes.help_field;
                if (help_field) {
                    fields.push(help_field);
                }
                var prm = Sao.rpc({
                    'method': 'model.' + this.attributes.relation +
                        '.search_read',
                    'params': [domain, 0, null, null, fields, context]
                }, record.model.session, true, false);
                prm.done(result => {
                    var selection = [];
                    for (const x of result) {
                        selection.push([x.id, x.rec_name]);
                    }
                    if (this.nullable_widget) {
                        selection.push([null, '']);
                    }
                    var help = {};
                    if (help_field){
                        for (const x of result) {
                            help[x.id] = x[help_field];
                        }
                    }
                    this._last_domain = [domain, context];
                    this._domain_cache[jdomain] = selection;
                    this.selection = jQuery.extend([], selection);
                    this.help = help;
                    if (callback) {
                        callback(this.selection, this.help);
                    }
                });
                prm.fail(() => {
                    var selection = [];
                    if (this.nullable_widget) {
                        selection.push([null, '']);
                    }
                    this._last_domain = null;
                    this.selection = selection;
                    if (callback) {
                        callback(this.selection, this.help);
                    }
                });
            }
        };
        this._selection_prm.done(_update_selection);
    };
    Sao.common.selection_mixin.filter_selection = function(
            domain, record, field) {
        if (jQuery.isEmptyObject(domain)) {
            return;
        }

        var inversion = new Sao.common.DomainInversion();
        const _value_evaluator = value => {
            var context = {};
            context[this.field_name] = value[0];
            return inversion.eval_domain(domain, context);
        };

        var _model_evaluator = function(allowed_models) {
            return function(value) {
                return ~allowed_models.indexOf(value[0]) ||
                    jQuery.isEmptyObject(allowed_models);
            };
        };

        var evaluator;
        var type_ = field.description.type;
        if (type_ == 'reference') {
            var allowed_models = field.get_models(record);
            evaluator = _model_evaluator(allowed_models);
        } else if (type_ == 'multiselection') {
            return;
        } else {
            evaluator = _value_evaluator;
        }

        this.selection = this.selection.filter(evaluator);
    };
    Sao.common.selection_mixin.get_inactive_selection = function(value) {
        if (!this.attributes.relation) {
            return jQuery.when([]);
        }
        if (value === null) {
            return jQuery.when([null, '']);
        }
        for (var i = 0, len = this.inactive_selection.length; i < len; i++) {
            if (value == this.inactive_selection[i][0]) {
                return jQuery.when(this.inactive_selection[i]);
            }
        }
        var prm = Sao.rpc({
            'method': 'model.' + this.attributes.relation + '.read',
            'params': [[value], ['rec_name'], {}]
        }, Sao.Session.current_session);
        return prm.then(result => {
            this.inactive_selection.push([result[0].id, result[0].rec_name]);
            return [result[0].id, result[0].rec_name];
        });
    };

    Sao.common.Button = Sao.class_(Object, {
        init: function(attributes, el, size, style) {
            this.attributes = attributes;
            if (el) {
                this.el = el;
            } else {
                this.el = jQuery('<button/>', {
                    title: attributes.string || '',
                    name: attributes.name || '',
                });
                this.el.text(attributes.string || '');
                if (this.attributes.rule) {
                    this.el.append(' ').append(jQuery('<span/>', {
                        'class': 'badge'
                    }));
                }
                this.el.attr(
                    'accesskey',
                    Sao.common.accesskey(attributes.string || ''));
            }
            this.icon = this.el.children('img');
            if (!this.icon.length) {
                this.icon = jQuery('<img/>', {
                    'class': 'icon',
                }).prependTo(this.el);
                this.icon.hide();
            }
            this.el.addClass([
                'btn', 'btn-horizontal',
                (style || 'btn-default'), (size || '')].join(' '));
            this.el.attr('type', 'button');
            this.icon.attr('aria-hidden', true);
            this.set_icon(attributes.icon);
        },
        set_icon: function(icon_name) {
            if (!icon_name) {
                this.icon.attr('src', '');
                this.icon.hide();
                return;
            }
            Sao.common.ICONFACTORY.get_icon_url(icon_name).done(url => {
                this.icon.attr('src', url);
                this.icon.show();
            });
        },
        set_state: function(record) {
            var states;
            if (record) {
                states = record.expr_eval(this.attributes.states || {});
            } else {
                states = {};
            }
            if (states.invisible) {
                this.el.hide();
            } else {
                this.el.show();
            }
            this.el.prop('disabled', Boolean(states.readonly));
            this.set_icon(states.icon || this.attributes.icon);

            if (this.attributes.rule) {
                var prm;
                if (record) {
                    prm = record.get_button_clicks(this.attributes.name);
                } else {
                    prm = jQuery.when();
                }
                prm.then(clicks => {
                    var counter = this.el.children('.badge');
                    var users = [];
                    var tip = '';
                    if (!jQuery.isEmptyObject(clicks)) {
                        for (var u in clicks) {
                            users.push(clicks[u]);
                        }
                        tip = Sao.i18n.gettext('By: ') +
                            users.join(Sao.i18n.gettext(', '));
                    }
                    counter.text(users.length || '');
                    counter.attr('title', tip);
                });
            }

            if (((this.attributes.type === undefined) ||
                        (this.attributes.type === 'class')) && (record)) {
                var parent = record.group.parent;
                while (parent) {
                    if (parent.modified) {
                        this.el.prop('disabled', true);
                        break;
                    }
                    parent = parent.group.parent;
                }
            }
        }
    });

    Sao.common.udlex = Sao.class_(Object, {
        init: function(instream) {

            var Stream = Sao.class_(Object, {
                init: function(stream) {
                    this.stream = stream.split('');
                    this.i = 0;
                },
                read: function(length=1) {
                    if (this.i >= this.stream.length) {
                        return null;
                    }
                    var value = this.stream
                        .slice(this.i, this.i + length).join();
                    this.i += length;
                    return value;
                }
            });
            this.instream = new Stream(instream);
            this.eof = null;
            this.commenters = '';
            this.nowordchars = [':', '>', '<', '=', '!', '"', ';', '(', ')'];
            this.whitespace = ' \t\r\n';
            this.whitespace_split = false;
            this.quotes = '"';
            this.escape = '\\';
            this.escapedquotes = '"';
            this.state = ' ';
            this.pushback = [];
            this.token = '';
        },
        get_token: function() {
            if (this.pushback.length > 0) {
                return this.pushback.shift();
            }
            var raw = this.read_token();
            return raw;
        },
        read_token: function() {
            var quoted = false;
            var escapedstate = ' ';
            const always = true;
            while (always) {
                var nextchar = this.instream.read(1);
                if (this.state === null) {
                    this.token = '';  // past en of file
                    break;
                } else if (this.state == ' ') {
                    if (!nextchar) {
                        this.state = null;  // end of file
                        break;
                    } else if (this.whitespace.contains(nextchar)) {
                        if (this.token || quoted) {
                            break;  // emit current token
                        } else {
                            continue;
                        }
                    } else if (this.commenters.contains(nextchar)) {
                        // TODO readline
                    } else if (this.escape.contains(nextchar)) {
                        escapedstate = 'a';
                        this.state = nextchar;
                    } else if (!~this.nowordchars.indexOf(nextchar)) {
                        this.token = nextchar;
                        this.state = 'a';
                    } else if (this.quotes.contains(nextchar)) {
                        this.state = nextchar;
                    } else if (this.whitespace_split) {
                        this.token = nextchar;
                        this.state = 'a';
                    } else {
                        this.token = nextchar;
                        if (this.token || quoted) {
                            break;  // emit current token
                        } else {
                            continue;
                        }
                    }
                } else if (this.quotes.contains(this.state)) {
                    quoted = true;
                    if (!nextchar) {  // end of file
                        throw 'no closing quotation';
                    }
                    if (nextchar == this.state) {
                        this.state = 'a';
                    } else if (this.escape.contains(nextchar) &&
                        this.escapedquotes.contains(this.state)) {
                        escapedstate = this.state;
                        this.state = nextchar;
                    } else {
                        this.token = this.token + nextchar;
                    }
                } else if (this.escape.contains(this.state)) {
                    if (!nextchar) {  // end of file
                        throw 'no escaped character';
                    }
                    if (this.quotes.contains(escapedstate) &&
                        (nextchar != this.state) &&
                        (nextchar != escapedstate)) {
                        this.token = this.token + this.state;
                    }
                    this.token = this.token + nextchar;
                    this.state = escapedstate;
                } else if (this.state == 'a') {
                    if (!nextchar) {
                        this.state = null;  // end of file
                        break;
                    } else if (this.whitespace.contains(nextchar)) {
                        this.state = ' ';
                        if (this.token || quoted) {
                            break;  // emit current token
                        } else {
                            continue;
                        }
                    } else if (this.commenters.contains(nextchar)) {
                        // TODO
                    } else if (this.quotes.contains(nextchar)) {
                        this.state = nextchar;
                    } else if (this.escape.contains(nextchar)) {
                        escapedstate = 'a';
                        this.state = nextchar;
                    } else if ((!~this.nowordchars.indexOf(nextchar)) ||
                            this.quotes.contains(nextchar) ||
                            this.whitespace_split) {
                        this.token = this.token + nextchar;
                    } else {
                        this.pushback.unshift(nextchar);
                        this.state = ' ';
                        if (this.token) {
                            break;  // emit current token
                        } else {
                            continue;
                        }
                    }
                }
            }
            var result = this.token;
            this.token = '';
            if (!quoted && result === '') {
                result = null;
            }
            return result;
        },
        next: function() {
            var token = this.get_token();
            if (token == this.eof) {
                return null;
            }
            return token;
        }
    });

    Sao.common.DomainParser = Sao.class_(Object, {
        OPERATORS: ['!=', '<=', '>=', '=', '!', '<', '>'],
        init: function(fields, context) {
            this.fields = {};
            this.strings = {};
            this.context = context;
            this.update_fields(fields);
        },
        update_fields: function(fields, prefix, string_prefix) {
            prefix = prefix || '';
            string_prefix = string_prefix || '';
            for (var name in fields) {
                var field = fields[name];
                if ((field.searchable || (field.searchable === undefined)) &&
                    (name !== 'rec_name')) {
                    field = jQuery.extend({}, field);
                    var fullname = prefix ? prefix + '.' + name : name;
                    var string = string_prefix ?
                        string_prefix + '.' + field.string : field.string;
                    field.string = string;
                    field.name = fullname;
                    this.fields[fullname] = field;
                    this.strings[field.string.toLowerCase()] = field;
                    var rfields = field.relation_fields;
                    if (rfields) {
                        this.update_fields(rfields, fullname, string);
                    }
                }
            }
        },
        parse: function(input) {
            try {
                var lex = new Sao.common.udlex(input);
                var tokens = [];
                do {
                    var token = lex.next();
                    if (token !== null) {
                        tokens.push(token);
                    }
                } while (token !== null);
                tokens = this.group_operator(tokens);
                tokens = this.parenthesize(tokens);
                tokens = this.group(tokens);
                tokens = this.operatorize(tokens, 'or');
                tokens = this.operatorize(tokens, 'and');
                tokens = this.parse_clause(tokens);
                return this.simplify(tokens);
            } catch (e) {
                if (e == 'no closing quotation') {
                    return this.parse(input + '"');
                }
                throw e;
            }
        },
        stringable: function(domain) {
            const stringable_ = clause => {
                if (!clause || jQuery.isEmptyObject(clause)) {
                    return true;
                }
                var is_array = function(e) {
                    return e instanceof Array;
                };
                if ((~['AND', 'OR'].indexOf(clause[0]) ||
                            (is_array(clause[0]))) &&
                        clause.slice(1).every(is_array)) {
                    return this.stringable(clause);
                }
                var name = clause[0];
                var value = clause[2];
                if (name.endsWith('.rec_name')) {
                    name = name.slice(0, -9);
                }
                if (name in this.fields) {
                    var field = this.fields[name];
                    if (~['many2one', 'one2one', 'one2many', 'many2many']
                        .indexOf(field.type)) {
                        var test = function(value) {
                            return ((typeof value == 'string') ||
                                (value === null));
                        };
                        if (value instanceof Array) {
                            return value.every(test);
                        } else {
                            return test(value);
                        }
                    } else if (field.type == 'multiselection') {
                        return (!value ||
                            jQuery.isEmptyObject(value) ||
                            (value instanceof Array));
                    } else {
                        return true;
                    }
                } else if (name == 'rec_name') {
                    return true;
                }
                return false;
            };
            if (!domain) {
                return true;
            }
            if (~['AND', 'OR'].indexOf(domain[0])) {
                domain = domain.slice(1);
            }
            return domain.every(stringable_);
        },
        string: function(domain) {

            const string = clause => {
                if (jQuery.isEmptyObject(clause)) {
                    return '';
                }
                if ((typeof clause[0] != 'string') ||
                        ~['AND', 'OR'].indexOf(clause[0])) {
                    return '(' + this.string(clause) + ')';
                }
                var name = clause[0];
                var operator = clause[1];
                var value = clause[2];
                if (name.endsWith('.rec_name')) {
                    name = name.slice(0, -9);
                }
                if (!(name in this.fields)) {
                    if (this.is_full_text(value)) {
                        value = value.slice(1, -1);
                    }
                    return this.quote(value);
                }
                var field = this.fields[name];
                var target = null;
                if (clause.length > 3) {
                    target = clause[3];
                }
                if (operator.contains('ilike')) {
                    if (this.is_full_text(value)) {
                        value = value.slice(1, -1);
                    } else if (!this.is_like(value)) {
                        if (operator == 'ilike') {
                            operator = '=';
                        } else {
                            operator = '!';
                        }
                        value = this.unescape(value);
                    }
                }
                var def_operator = this.default_operator(field);
                if (def_operator == operator.trim()) {
                    operator = '';
                    if (~this.OPERATORS.indexOf(value)) {
                        // As the value could be interpreted as an operator
                        // the default operator must be forced
                        operator = '"" ';
                    }
                } else if ((operator.contains(def_operator) &&
                            (operator.contains('not') ||
                             operator.contains('!')))) {
                    operator = operator.replace(def_operator, '')
                        .replace('not', '!').trim();
                }
                if (operator.endsWith('in')) {
                    if (operator == 'not in') {
                        operator = '!';
                    } else {
                        operator = '';
                    }
                }
                var formatted_value = this.format_value(field, value, target);
                if (~this.OPERATORS.indexOf(operator) &&
                        ~['char', 'text', 'selection']
                        .indexOf(field.type) &&
                        (value === '')) {
                    formatted_value = '""';
                }
                return (this.quote(field.string) + ': ' +
                        operator + formatted_value);
            };

            if (jQuery.isEmptyObject(domain)) {
                return '';
            }
            var nary = ' ';
            if ((domain[0] == 'AND') || (domain[0] == 'OR')) {
                if (domain[0] == 'OR') {
                    nary = ' | ';
                }
                domain = domain.slice(1);
            }
            return domain.map(string).join(nary);
        },
        completion: function(input) {
            var results = [];
            var domain = this.parse(input);
            var closing = 0;
            var i, len;
            for (i=input.length; i>0; i--) {
                if (input[i] == ')' || input[i] == ' ') {
                    break;
                }
                if (input[i] == ')') {
                    closing += 1;
                }
            }
            var endings = this.ending_clause(domain);
            var ending = endings[0];
            var deep_ending = endings[1];
            var deep = deep_ending - closing;
            var string_domain = this.string(domain);

            if (deep > 0) {
                string_domain = string_domain.substring(0,
                        string_domain.length - deep);
            }
            if (string_domain != input) {
                results.push(string_domain);
            }

            var pslice = function(string, depth) {
                if (depth > 0) {
                    return string.substring(0, string.length - depth);
                }
                return string;
            };
            var complete, complete_string;
            if (ending !== null && closing === 0) {
                var completes = this.complete(ending);
                for (i=0, len=completes.length; i < len; i++) {
                    complete = completes[i];
                    complete_string = this.string(
                            this.replace_ending_clause(domain, complete));
                    results.push(pslice(complete_string, deep));
                }
            }
            if (input.length > 0) {
                if (input.substr(input.length - 1, 1) != ' ') {
                    return results;
                }
                if (input.length >= 2 ||
                        input.substr(input.length - 2, 1) == ':') {
                    return results;
                }
            }
            var field, operator, value;
            for (var key in this.strings) {
                field = this.strings[key];
                operator = this.default_operator(field);
                value = '';
                if ((operator == 'ilike') || (operator == 'not ilike')) {
                    value = this.likify(value);
                }
                var new_domain = this.append_ending_clause(domain,
                        [field.name, operator, value], deep);
                var new_domain_string = this.string(new_domain);
                results.push(pslice(new_domain_string, deep));
            }
            return results;
        },
        complete: function(clause) {
            var results = [];
            var name, operator, value;
            if (clause.length == 1) {
                name = clause[0];
            } else if (clause.length == 3) {
                name = clause[0];
                operator = clause[1];
                value = clause[2];
            } else {
                name = clause[0];
                operator = clause[1];
                value = clause[2];
                if (name.endsWith('.rec_name')) {
                    name = name.substring(0, name.length - 9);
                }
            }
            var escaped;
            if (name == "rec_name") {
                if (operator == "ilike") {
                    escaped = value.replace(/%%/g, '__');
                    if (escaped.startsWith('%') || escaped.endsWith('%')) {
                        value = escaped.substring(1, escaped.length - 1);
                    } else if (~escaped.indexOf('%')) {
                        value = value.replace(/%%/g, '%');
                    }
                    operator = null;
                }
                name = value;
                value = '';
            }
            if (name === undefined || name === null) {
                name = '';
            }
            var field;
            if (!(name.toLowerCase() in this.strings) &&
                    !(name in this.fields)) {
                for (var key in this.strings) {
                    field = this.strings[key];
                    if (field.string.toLowerCase()
                            .startsWith(name.toLowerCase())) {
                        operator = this.default_operator(field);
                        value = '';
                        if (operator == 'ilike') {
                            value = this.likify(value);
                        }
                        results.push([field.name, operator, value]);
                    }
                }
                return results;
            }
            if (name in this.fields) {
                field = this.fields[name];
            } else {
                field = this.strings[name.toLowerCase()];
            }
            if (!operator) {
                operator = this.default_operator(field);
                value = '';
                if ((operator == 'ilike') || (operator == 'not ilike')) {
                    value = this.likify(value);
                }
                results.push([field.name, operator, value]);
            } else {
                var completes = this.complete_value(field, value);
                for (var i=0, len=completes.length; i < len; i++) {
                    results.push([field.name, operator, completes[i]]);
                }
            }
            return results;
        },
        is_subdomain: function(element) {
            return (element instanceof Array) && !element.clause;
        },
        ending_clause: function(domain, depth=0) {
            if (domain.length === 0) {
                return [null, depth];
            }
            var last_element = domain[domain.length - 1];
            if (this.is_subdomain(last_element)) {
                return this.ending_clause(last_element, depth + 1);
            }
            return [last_element, depth];
        },
        replace_ending_clause: function(domain, clause) {
            var results = [];
            var i, len;
            for (i = 0, len=domain.length - 1; i < len; i++) {
                results.push(domain[i]);
            }
            if (this.is_subdomain(domain[i])) {
                results.push(
                    this.replace_ending_clause(domain[i], clause));
            } else {
                results.push(clause);
            }
            return results;
        },
        append_ending_clause: function(domain, clause, depth) {
            if (domain.length === 0) {
                return [clause];
            }
            var results = domain.slice(0, -1);
            var last_element = domain[domain.length - 1];
            if (this.is_subdomain(last_element)) {
                results.push(this.append_ending_clause(last_element, clause,
                            depth - 1));
            } else {
                results.push(last_element);
                if (depth === 0) {
                    results.push(clause);
                }
            }
            return results;
        },
        complete_value: function(field, value) {
            var complete_boolean = function() {
                if ((value === null) || (value === undefined)) {
                    return [true, false];
                } else if (value) {
                    return [false];
                } else {
                    return [true];
                }
            };

            var complete_selection = function() {
                var results = [];
                var test_value = value !== null ? value : '';
                if (value instanceof Array) {
                    test_value = value[value.length - 1] || '';
                }
                test_value = test_value.replace(/^%*|%*$/g, '');
                var i, len, svalue, test;
                for (i=0, len=field.selection.length; i<len; i++) {
                    svalue = field.selection[i][0];
                    test = field.selection[i][1].toLowerCase();
                    if (test.startsWith(test_value.toLowerCase())) {
                        if (value instanceof Array) {
                            results.push(value.slice(0, -1).concat([svalue]));
                        } else {
                            results.push(svalue);
                        }
                    }
                }
                return results;
            };

            const complete_reference = () => {
                var results = [];
                var test_value = value !== null ? value : '';
                if (value instanceof Array) {
                    test_value = value[value.length - 1];
                }
                test_value = test_value.replace(/^%*|%*$/g, '');
                var i, len, svalue, test;
                for (i=0, len=field.selection.length; i<len; i++) {
                    svalue = field.selection[i][0];
                    test = field.selection[i][1].toLowerCase();
                    if (test.startsWith(test_value.toLowerCase())) {
                        if (value instanceof Array) {
                            results.push(value.slice(0, -1).concat([svalue]));
                        } else {
                            results.push(this.likify(svalue));
                        }
                    }
                }
                return results;
            };

            var complete_datetime = function() {
                return [Sao.Date(), Sao.DateTime().utc()];
            };

            var complete_date = function() {
                return [Sao.Date()];
            };

            var complete_time = function() {
                return [Sao.Time()];
            };

            var completes = {
                'boolean': complete_boolean,
                'selection': complete_selection,
                'multiselection': complete_selection,
                'reference': complete_reference,
                'datetime': complete_datetime,
                'timestamp': complete_datetime,
                'date': complete_date,
                'time': complete_time
            };

            if (field.type in completes) {
                return completes[field.type]();
            }
            return [];
        },
        group_operator: function(tokens) {
            var cur = tokens[0];
            var result = [];
            for (const nex of tokens.slice(1)) {
                if ((nex == '=') && cur &&
                    ~this.OPERATORS.indexOf(cur + nex)) {
                    result.push(cur + nex);
                    cur = null;
                } else {
                    if (cur !== null) {
                        result.push(cur);
                    }
                    cur = nex;
                }
            }
            if (cur !== null) {
                result.push(cur);
            }
            return result;
        },
        parenthesize: function(tokens) {
            var result = [];
            var current = result;
            var parent = [];
            for (const token of tokens) {
                if (current === undefined) {
                    continue;
                }
                if (token == '(') {
                    parent.push(current);
                    current = current[current.push([]) - 1];
                } else if (token == ')') {
                    current = parent.pop();
                } else {
                    current.push(token);
                }
            }
            return result;
        },
        group: function(tokens) {
            var result = [];

            const _group = parts => {
                var result = [];
                var push_result = function(part) {
                    var clause = [part];
                    clause.clause = true;
                    result.push(clause);
                };
                var i = parts.indexOf(':');
                if (!~i) {
                    parts.forEach(push_result);
                    return result;
                }
                var sub_group = function(name, lvalue) {
                    return function(part) {
                        if (!jQuery.isEmptyObject(name)) {
                            var clause;
                            if (!jQuery.isEmptyObject(lvalue)) {
                                if (part[0] !== null) {
                                    lvalue.push(part[0]);
                                }
                                clause = name.concat([lvalue]);
                                clause.clause = true;
                                result.push(clause);
                            } else {
                                clause = name.concat(part);
                                clause.clause = true;
                                result.push(clause);
                            }
                            name.splice(0, name.length);
                        } else {
                            result.push(part);
                        }
                    };
                };
                for (var j = 0; j < i; j++) {
                    var name = parts.slice(j, i).join(' ');
                    if (name.toLowerCase() in this.strings) {
                        if (!jQuery.isEmptyObject(parts.slice(0, j))) {
                            parts.slice(0, j).forEach(push_result);
                        } else {
                            push_result(null);
                        }
                        name = [name];
                        // empty string is also the default operator
                        var operators = [''].concat(this.OPERATORS);
                        if (((i + 1) < parts.length) &&
                                (~operators.indexOf(parts[i + 1]))) {
                            name = name.concat([parts[i + 1]]);
                            i += 1;
                        } else {
                            name = name.concat([null]);
                        }
                        var lvalue = [];
                        while ((i + 2) < parts.length) {
                            if (parts[i + 2] == ';') {
                                lvalue.push(parts[i + 1]);
                                i += 2;
                            } else {
                                break;
                            }
                        }
                        _group(parts.slice(i + 1)).forEach(
                                sub_group(name, lvalue));
                        if (!jQuery.isEmptyObject(name)) {
                            var clause;
                            if (!jQuery.isEmptyObject(lvalue)) {
                                clause = name.concat([lvalue]);
                                clause.clause = true;
                                result.push(clause);
                            } else {
                                clause = name.concat([null]);
                                clause.clause = true;
                                result.push(clause);
                            }
                        }
                        break;
                    }
                }
                return result;
            };

            var parts = [];
            for (const token of tokens) {
                if (this.is_generator(token)) {
                    for (const group of _group(parts)) {
                        if (!Sao.common.compare(group, [null])) {
                            result.push(group);
                        }
                    }
                    parts = [];
                    result.push(this.group(token));
                } else {
                    parts.push(token);
                }
            }
            for (const group of _group(parts)) {
                if (!Sao.common.compare(group, [null])) {
                    result.push(group);
                }
            }
            return result;
        },
        is_generator: function(value) {
            return (value instanceof Array) && (value.clause === undefined);
        },
        operatorize: function(tokens, operator) {
            var result = [];
            operator = operator || 'or';
            tokens = jQuery.extend([], tokens);
            var notation = {'or': '|', 'and': '&'}[operator];
            var test = function(value) {
                if (value instanceof Array) {
                    return Sao.common.compare(value, [notation]);
                } else {
                    return value == notation;
                }
            };
            var cur = tokens.shift();
            while (test(cur)) {
                cur = tokens.shift();
            }
            if (cur === undefined) {
                return result;
            }
            if (this.is_generator(cur)) {
                cur = this.operatorize(cur, operator);
            }
            var nex = null;
            while (!jQuery.isEmptyObject(tokens)) {
                nex = tokens.shift();
                if ((this.is_generator(nex)) && !test(nex)) {
                    nex = this.operatorize(nex, operator);
                }
                if (test(nex)) {
                    nex = tokens.shift();
                    while (test(nex)) {
                        nex = tokens.shift();
                    }
                    if (this.is_generator(nex)) {
                        nex = this.operatorize(nex, operator);
                    }
                    if (nex !== undefined) {
                        cur = [operator.toUpperCase(), cur, nex];
                    } else {
                        if (!test(cur)) {
                            result.push([operator.toUpperCase(), cur]);
                            cur = null;
                        }
                    }
                    nex = null;
                } else {
                    if (!test(cur)) {
                        result.push(cur);
                    }
                    cur = nex;
                }
            }
            if (jQuery.isEmptyObject(tokens)) {
                if ((nex !== null) && !test(nex)) {
                    result.push(nex);
                } else if ((cur !== null) && !test(cur)) {
                    result.push(cur);
                }
            }
            return result;
        },
        _clausify: function(e) {
            e.clause = true;
            return e;
        },
        parse_clause: function(tokens) {
            var result = [];
            tokens.forEach(clause => {
                if (this.is_generator(clause)) {
                    result.push(this.parse_clause(clause));
                } else if ((clause === 'OR') || (clause === 'AND')) {
                    result.push(clause);
                } else if ((clause.length == 1) &&
                    !(clause[0] instanceof Array)) {
                    result.push(this._clausify(['rec_name', 'ilike',
                                this.likify(clause[0])]));
                } else if ((clause.length == 3) &&
                    (clause[0].toLowerCase() in this.strings)) {
                    var operator = clause[1];
                    var value = clause[2];
                    var field = this.strings[clause[0].toLowerCase()];
                    var field_name = field.name;

                    var target = null;
                    if (field.type == 'reference') {
                        var split = this.split_target_value(field, value);
                        target = split[0];
                        value = split[1];
                        if (target) {
                            field_name += '.rec_name';
                        }
                    } else if (field.type == 'multiselection') {
                        if ((value !== null) && !(value instanceof Array)) {
                            value = [value];
                        }
                    }

                    if (!operator) {
                        operator = this.default_operator(field);
                    }
                    if ((value instanceof Array) &&
                        (field.type != 'multiselection')) {
                        if (operator == '!') {
                            operator = 'not in';
                        } else {
                            operator = 'in';
                        }
                    }
                    if (operator == '!') {
                        operator = this.negate_operator(
                                this.default_operator(field));
                    }
                    if ((value === null) && operator.endsWith('in')) {
                        if (operator.startsWith('not')) {
                            operator = '!=';
                        } else {
                            operator = '=';
                        }
                    }
                    if (~[
                        'integer', 'float', 'numeric',
                        'datetime', 'timestamp', 'date',
                        'time'].indexOf(field.type)) {
                        if ((typeof value == 'string') && value.contains('..')) {
                            var values = value.split('..', 2);
                            var lvalue = this.convert_value(field, values[0], this.context);
                            var rvalue = this.convert_value(field, values[1], this.context);
                            result.push([
                                    this._clausify([field_name, '>=', lvalue]),
                                    this._clausify([field_name, '<=', rvalue])
                                    ]);
                            return;
                        }
                    }
                    if (value instanceof Array) {
                        value = value.map(
                            v => this.convert_value(field, v, this.context));
                        if (~['many2one', 'one2many', 'many2many', 'one2one',
                            'many2many', 'one2one'].indexOf(field.type)) {
                            field_name += '.rec_name';
                        }
                    } else {
                        value = this.convert_value(field, value, this.context);
                    }
                    if (operator.contains('like')) {
                        value = this.likify(value);
                    }
                    if (target) {
                        result.push(this._clausify(
                            [field_name, operator, value, target]));
                    } else {
                        result.push(this._clausify(
                            [field_name, operator, value]));
                    }
                }
            });
            return result;
        },
        likify: function(value, escape) {
            escape = escape || '\\';
            if (!value) {
                return '%';
            }
            var escaped = value
                .replace(escape + '%', '')
                .replace(escape + '_', '');
            if (escaped.contains('%') || escaped.contains('_')) {
                return value;
            } else {
                return '%' + value + '%';
            }
        },
        is_full_text: function(value, escape) {
            escape = escape || '\\';
            var escaped = value;
            if ((escaped.charAt(0) == '%') &&
                (escaped.charAt(escaped.length - 1) == '%')) {
                escaped = escaped.slice(1, -1);
            }
            escaped = escaped
                .replace(escape + '%', '')
                .replace(escape + '_', '');
            if (escaped.contains('%') || escaped.contains('_')) {
                return false;
            }
            return value.startsWith('%') && value.endsWith('%');
        },
        is_like: function(value, escape) {
            escape = escape || '\\';
            var escaped = value
                .replace(escape + '%', '')
                .replace(escape + '_', '');
            return escaped.contains('%') || escaped.contains('_');
        },
        unescape: function(value, escape) {
            escape = escape || '\\';
            return value
                .replace(escape + '%', '%')
                .replace(escape + '_', '_');
        },
        quote: function(value) {
            if (typeof value != 'string') {
                return value;
            }
            if (value.contains('\\')) {
                value = value.replace(new RegExp('\\\\', 'g'), '\\\\');
            }
            if (value.contains('"')) {
                value = value.replace(new RegExp('"', 'g'), '\\"');
            }
            var tests = [':', ' ', '(', ')'].concat(this.OPERATORS);
            for (var i = 0; i < tests.length; i++) {
                var test = tests[i];
                if (value.contains(test)) {
                    return '"' + value + '"';
                }
            }
            return value;
        },
        default_operator: function(field) {
            if (~['char', 'text', 'many2one', 'many2many', 'one2many',
                    'reference', 'one2one'].indexOf(field.type)) {
                return 'ilike';
            } else if (field.type == 'multiselection') {
                return 'in';
            } else {
                return '=';
            }
        },
        negate_operator: function(operator) {
            switch (operator) {
                case 'ilike':
                    return 'not ilike';
                case '=':
                    return '!=';
                case 'in':
                    return 'not in';
            }
        },
        time_format: function(field) {
            return new Sao.PYSON.Decoder({}).decode(field.format);
        },
        split_target_value: function(field, value) {
            var target = null;
            if (typeof value == 'string') {
                for (var i = 0; i < field.selection.length; i++) {
                    var selection = field.selection[i];
                    var key = selection[0];
                    var text = selection[1];
                    if (value.toLowerCase().startsWith(
                                text.toLowerCase() + ',')) {
                        target = key;
                        value = value.slice(text.length + 1);
                        break;
                    }
                }
            }
            return [target, value];
        },
        convert_value: function(field, value, context) {
            if (!context) {
                context = {};
            }
            var convert_selection = function() {
                if (typeof value == 'string') {
                    for (var i = 0; i < field.selection.length; i++) {
                        var selection = field.selection[i];
                        var key = selection[0];
                        var text = selection[1];
                        if (value.toLowerCase() == text.toLowerCase()) {
                            return key;
                        }
                    }
                }
                return value;
            };

            var converts = {
                'boolean': function() {
                    if (typeof value == 'string') {
                        return [Sao.i18n.gettext('y'),
                            Sao.i18n.gettext('Yes'),
                            Sao.i18n.gettext('True'),
                            Sao.i18n.gettext('t'),
                            '1'].some(
                                function(test) {
                                    return test.toLowerCase().startsWith(
                                        value.toLowerCase());
                                });
                    }
                    return null;
                },
                'float': function() {
                    var factor = Number(field.factor || 1);
                    var result = Number(value);
                    if (isNaN(result) || value === '' || value === null) {
                        return null;
                    } else {
                        return result / factor;
                    }
                },
                'integer': function() {
                    var factor = Number(field.factor || 1, 10);
                    var result = parseInt(value, 10);
                    if (isNaN(result)) {
                        return null;
                    } else {
                        return result / factor;
                    }
                },
                'numeric': function() {
                    var factor = Number(field.factor || 1);
                    var result = Number(value);
                    if (isNaN(result.valueOf()) ||
                            value === '' || value === null) {
                        return null;
                    } else {
                        return new Sao.Decimal(result / factor);
                    }
                },
                'selection': convert_selection,
                'multiselection': convert_selection,
                'reference': convert_selection,
                'datetime': () => Sao.common.parse_datetime(
                    Sao.common.date_format(context.date_format) + ' ' +
                    this.time_format(field), value),
                'date': function() {
                    return Sao.common.parse_date(
                            Sao.common.date_format(context.date_format),
                            value);
                },
                'time': () => {
                    try {
                        return Sao.common.parse_time(this.time_format(field),
                                value);
                    } catch (e) {
                        return null;
                    }
                },
                'timedelta': () => {
                    var converter = null;
                    if (field.converter) {
                        converter = this.context[field.converter];
                    }
                    return Sao.common.timedelta.parse(value, converter);
                },
                'many2one': function() {
                    if (value === '') {
                        return null;
                    } else {
                        return value;
                    }
                }
            };
            converts.timestamp = converts.datetime;
            var func = converts[field.type];
            if (func) {
                return func();
            } else {
                return value;
            }
        },
        format_value: function(field, value, target=null, context={}) {
            var format_float = function() {
                if (!value && value !== 0 && value !== new Sao.Decimal(0)) {
                    return '';
                }
                var digit = 0;
                var factor = Number(field.factor || 1);
                var string = String(value * factor);
                if (string.contains('e')) {
                    var exp = string.split('e')[1];
                    string = string.split('e')[0];
                    digit -= parseInt(exp);
                }
                if (string.contains('.')) {
                    digit += string.replace(/0+$/, '').split('.')[1].length;
                }
                return (value * factor).toFixed(digit);
            };
            var format_selection = function() {
                if (field.selection instanceof Array) {
                    for (var i = 0; i < field.selection.length; i++) {
                        if (field.selection[i][0] == value) {
                            return field.selection[i][1];
                        }
                    }
                }
                return value || '';
            };

            var format_reference = function() {
                if (!target) {
                    return format_selection();
                }
                for (var i = 0; i < field.selection.length; i++) {
                    if (field.selection[i][0] == target) {
                        target = field.selection[i][1];
                        break;
                    }
                }
                return target + ',' + value;
            };

            var converts = {
                'boolean': function() {
                    if (value === false) {
                        return Sao.i18n.gettext('False');
                    } else if (value) {
                        return Sao.i18n.gettext('True');
                    } else {
                        return '';
                    }
                },
                'integer': function() {
                    var factor = Number(field.factor || 1);
                    if (value || value === 0) {
                        return '' + parseInt(parseInt(value, 10) * factor, 10);
                    } else {
                        return '';
                    }
                },
                'float': format_float,
                'numeric': format_float,
                'selection': format_selection,
                'multiselection': format_selection,
                'reference': format_reference,
                'datetime': () => {
                    if (!value) {
                        return '';
                    }
                    if (value.isDate ||
                            !(value.hour() ||
                                value.minute() ||
                                value.second())) {
                        return Sao.common.format_date(
                                Sao.common.date_format(context.date_format),
                                value);
                    }
                    return Sao.common.format_datetime(
                        Sao.common.date_format(context.date_format) + ' ' +
                        this.time_format(field), value);
                },
                'date': () => Sao.common.format_date(
                    Sao.common.date_format(context.date_format), value),
                'time': () => {
                    if (!value) {
                        return '';
                    }
                    return Sao.common.format_time(
                            this.time_format(field),
                            value);
                },
                'timedelta': () => {
                    if (!value || !value.valueOf()) {
                        return '';
                    }
                    var converter = null;
                    if (field.converter) {
                        converter = this.context[field.converter];
                    }
                    return Sao.common.timedelta.format(value, converter);
                },
                'many2one': function() {
                    if (value === null) {
                        return '';
                    } else {
                        return value;
                    }
                }
            };
            converts.timestamp = converts.datetime;
            if (value instanceof Array) {
                return value.map(v => this.format_value(field, v)).join(';');
            } else {
                var func = converts[field.type];
                if (func) {
                    return this.quote(func(value));
                } else if (value === null) {
                    return '';
                } else {
                    return this.quote(value);
                }
            }
        },
        simplify: function(value) {
            if (this.is_subdomain(value)) {
                if ((value.length == 1) && this.is_subdomain(value[0])) {
                    return this.simplify(value[0]);
                } else if ((value.length == 2) &&
                    ((value[0] == 'AND') || (value[0] == 'OR')) &&
                    this.is_subdomain(value[1])) {
                    return this.simplify(value[1]);
                } else if ((value.length == 3) &&
                    ((value[0] == 'AND') || (value[0] == 'OR')) &&
                    this.is_subdomain(value[1]) &&
                    (value[0] == value[1][0])) {
                    value = this.simplify(value[1]).concat([value[2]]);
                }
                return value.map(v => this.simplify(v));
            }
            return value;
        }
    });

    Sao.common.DomainInversion = Sao.class_(Object, {
        and: function(a, b) {return a && b;},
        or: function(a, b) {return a || b;},
        OPERATORS: {
            '=': function(a, b) {
                return Sao.common.DomainInversion.equals(a, b);
            },
            '>': function(a, b) {return (a > b);},
            '<': function(a, b) {return (a < b);},
            '<=': function(a, b) {return (a <= b);},
            '>=': function(a, b) {return (a >= b);},
            '!=': function(a, b) {
                return !Sao.common.DomainInversion.equals(a, b);
            },
            'in': function(a, b) {
                return Sao.common.DomainInversion.in_(a, b);
            },
            'not in': function(a, b) {
                return !Sao.common.DomainInversion.in_(a, b);
            },
            'like': function(a, b) {
                return Sao.common.DomainInversion.sql_like(a, b, false);
            },
            'ilike': function(a, b) {
                return Sao.common.DomainInversion.sql_like(a, b, true);
            },
            'not like': function(a, b) {
                return !Sao.common.DomainInversion.sql_like(a, b, false);
            },
            'not ilike': function(a, b) {
                return !Sao.common.DomainInversion.sql_like(a, b, true);
            },
            // Those operators are not supported (yet ?)
            'child_of': function() {return true;},
            'not child_of': function() {return true;}
        },
        locale_part: function(expression, field_name, locale_name='id') {
            if (expression === field_name) {
                return locale_name;
            }
            if (expression.contains('.')) {
                return expression.split('.').slice(1).join('.');
            }
            return expression;
        },
        is_leaf: function(expression) {
            return ((expression instanceof Array) &&
                (expression.length > 2) &&
                (typeof expression[1] == 'string'));
        },
        constrained_leaf: function(part, boolop) {
            if (boolop === undefined) {
                boolop = this.and;
            }
            var operand = part[1];
            if ((operand === '=') & (boolop === this.and)) {
                // We should consider that other domain inversion will set a
                // correct value to this field
                return true;
            }
            return false;
        },
        eval_leaf: function(part, context, boolop) {
            if (boolop === undefined) {
                boolop = this.and;
            }
            var field = part[0];
            var operand = part[1];
            var value = part[2];
            if (field.contains('.')) {
                // In the case where the leaf concerns a m2o then having a
                // value in the evaluation context is deemed suffisant
                return Boolean(context[field.split('.')[0]]);
            }
            var context_field = context[field];
            if (!~['=', '!='].indexOf(operand) &&
                ((context_field === null) ||
                    (context_field === undefined) ||
                    (value === null) ||
                    (value === undefined)) &&
                !(~['in', 'not in'].indexOf(operand) &&
                    ((context_field === null) ||
                        (context_field === undefined)) &&
                    ((value instanceof Array) && ~value.indexOf(null)))) {
                return;
            }
            if (moment.isMoment(context_field) && !value) {
                if (context_field.isDateTime) {
                    value = Sao.DateTime.min;
                } else {
                    value = Sao.Date.min;
                }
            }
            if (moment.isMoment(value) && !context_field) {
                if (value.isDateTime) {
                    context_field = Sao.DateTime.min;
                } else {
                    context_field = Sao.Date.min;
                }
            }
            if ((context_field instanceof Array) & (value === null)) {
                value = [];
            }
            if ((typeof context_field == 'string') &&
                    (value instanceof Array) && value.length == 2) {
                value = value.join(',');
            } else if ((context_field instanceof Array) &&
                    (typeof value == 'string') && context_field.length == 2) {
                context_field = context_field.join(',');
            }
            if (~['=', '!='].indexOf(operand) &&
                    context_field instanceof Array &&
                    typeof value == 'number') {
                operand = {
                    '=': 'in',
                    '!=': 'not in'
                }[operand];
            }
            if (operand in this.OPERATORS) {
                return this.OPERATORS[operand](context_field, value);
            } else {
                return true;
            }
        },
        inverse_leaf: function(domain) {
            if (~['AND', 'OR'].indexOf(domain)) {
                return domain;
            } else if (this.is_leaf(domain)) {
                if (domain[1].contains('child_of') && !domain[0].contains('.')) {
                    if (domain.length == 3) {
                        return domain;
                    } else {
                        return [domain[3]].concat(domain.slice(1));
                    }
                }
                return domain;
            } else {
                return domain.map(d => this.inverse_leaf(d));
            }
        },
        filter_leaf: function(domain, field, model) {
            if (~['AND', 'OR'].indexOf(domain)) {
                return domain;
            } else if (this.is_leaf(domain)) {
                if (domain[0].startsWith(field) && (domain.length > 3)) {
                    if (domain[3] !== model) {
                        return ['id', '=', null];
                    }
                }
                return domain;
            } else {
                return domain.map(d => this.filter_leaf(d, field, model));
            }
        },
        eval_domain: function(domain, context, boolop) {
            if (boolop === undefined) {
                boolop = this.and;
            }
            if (this.is_leaf(domain)) {
                return this.eval_leaf(domain, context, boolop);
            } else if (jQuery.isEmptyObject(domain) && boolop == this.and) {
                return true;
            } else if (jQuery.isEmptyObject(domain) && boolop == this.or) {
                return false;
            } else if (domain[0] == 'AND') {
                return this.eval_domain(domain.slice(1), context);
            } else if (domain[0] == 'OR') {
                return this.eval_domain(domain.slice(1), context, this.or);
            } else {
                return boolop(Boolean(this.eval_domain(domain[0], context)),
                    Boolean(this.eval_domain(domain.slice(1), context, boolop))
                );
            }
        },
        localize_domain: function(domain, field_name, strip_target) {
            if (~['AND', 'OR', true, false].indexOf(domain)) {
                return domain;
            } else if (this.is_leaf(domain)) {
                if (domain[1].contains('child_of')) {
                    if (domain[0].split('.').length > 1) {
                        var target = domain[0].split('.').slice(1).join('.');
                        return [target].concat(domain.slice(1));
                    }
                    if (domain.length == 3) {
                        return domain;
                    } else {
                        return [domain[3]].concat(domain.slice(1, -1));
                    }
                }
                var local_name = 'id';
                if (typeof domain[2] == 'string') {
                    local_name = 'rec_name';
                }
                var n = strip_target ? 3 : 4;
                return [this.locale_part(domain[0], field_name, local_name)]
                    .concat(domain.slice(1, n)).concat(domain.slice(4));
            } else {
                return domain.map(
                    e => this.localize_domain(e, field_name, strip_target));
            }
        },

        _sort_key: function(domain) {
            if (!domain.length) {
                return [0, domain];
            } else if (this.is_leaf(domain)) {
                return [1, domain];
            } else if (~['AND', 'OR'].indexOf(domain)) {
                return [0, domain];
            } else {
                var content = domain.map(this._sort_key.bind(this));
                var nestedness = Math.max(...content.map(e => e[0]));
                return [nestedness + 1, content];
            }
        },

        _domain_compare: function(d1, d2) {
            if ((d1 instanceof Array) && (d2 instanceof Array)) {
                var elem_comparison;
                var min_len = Math.min(d1.length, d2.length);
                for (var i = 0; i < min_len; i++) {
                    elem_comparison = this._domain_compare(d1[i], d2[i]);
                    if (elem_comparison != 0) {
                        return elem_comparison;
                    }
                }
                if (d1.length == d2.length) {
                    return 0;
                } else {
                    return d1.length < d2.length ? -1 : 1;
                }
            } else if (d1 == d2) {
                return 0;
            } else {
                return d1 < d2 ? -1 : 1;
            }
        },

        sort: function(domain) {
            if (!domain.length) {
                return [];
            } else if (this.is_leaf(domain)) {
                return domain;
            } else if (~['AND', 'OR'].indexOf(domain)) {
                return domain;
            } else {
                var sorted_elements = domain.map(this.sort.bind(this));
                sorted_elements.sort(
                    (d1, d2) => this._domain_compare(this._sort_key(d1), this._sort_key(d2))
                );
                return sorted_elements;
            }
        },

        prepare_reference_domain: function(domain, reference) {

            var value2reference = function(value) {
                var model = null;
                var ref_id = null;
                if ((typeof(value) == 'string') && value.contains(',')) {
                    var split = value.split(',');
                    var result = split.splice(0, 1);
                    result.push(split.join(','));
                    model = result[0];
                    ref_id = result[1];
                    if (ref_id != '%') {
                        ref_id = parseInt(ref_id, 10);
                        if (isNaN(ref_id)) {
                            model = null;
                            ref_id = value;
                        }
                    }
                } else if ((value instanceof Array) &&
                        (value.length == 2) &&
                        (typeof(value[0]) == 'string') &&
                        ((typeof(value[1]) == 'number') ||
                            (value[1] == '%'))) {
                    model = value[0];
                    ref_id = value[1];
                } else {
                    ref_id = value;
                }
                return [model, ref_id];
            };

            if (~['AND', 'OR'].indexOf(domain)) {
                return domain;
            } else if (this.is_leaf(domain)) {
                if (domain[0] == reference) {
                    var model, ref_id, splitted;
                    if ((domain[1] == '=') || (domain[1] ==  '!=')) {
                        splitted = value2reference(domain[2]);
                        model = splitted[0];
                        ref_id = splitted[1];
                        if (model) {
                            if (ref_id == '%') {
                                if (domain[1] == '=') {
                                    return [
                                        reference + '.id', '!=', null, model];
                                } else {
                                    return [reference, 'not like', domain[2]];
                                }
                            }
                            return [
                                reference + '.id', domain[1], ref_id, model];
                        }
                    } else if ((domain[1] == 'in') || (domain[1] == 'not in')) {
                        var model_values = {};
                        var break_p = false;
                        for (var i=0; i < domain[2].length; i++) {
                            splitted = value2reference(domain[2][i]);
                            model = splitted[0];
                            ref_id = splitted[1];
                            if (!model) {
                                break_p = true;
                                break;
                            }
                            if (!(model in model_values)) {
                                model_values[model] = [];
                            }
                            model_values[model].push(ref_id);
                        }

                        if (!break_p) {
                            var ref_ids;
                            var new_domain;
                            if (domain[1] == 'in') {
                                new_domain = ['OR'];
                            } else {
                                new_domain = ['AND'];
                            }
                            for (model in model_values) {
                                ref_ids = model_values[model];
                                if (~ref_ids.indexOf('%')) {
                                    if (domain[1] == 'in') {
                                        new_domain.push(
                                            [reference + '.id', '!=', null,
                                                model]);
                                    } else {
                                        new_domain.push(
                                            [reference, 'not like',
                                                model + ',%']);
                                    }
                                } else {
                                    new_domain.push(
                                        [reference + '.id', domain[1],
                                            ref_ids.map(Number), model]);
                                }
                            }
                            return new_domain;
                        }
                    }
                    return [];
                }
                return domain;
            } else {
                return domain.map(
                    d => this.prepare_reference_domain(d, reference));
            }
        },
        extract_reference_models: function(domain, field_name) {
            if (~['AND', 'OR'].indexOf(domain)) {
                return [];
            } else if (this.is_leaf(domain)) {
                var local_part = domain[0].split('.', 1)[0];
                if ((local_part == field_name) &&
                        (domain.length > 3)) {
                    return [domain[3]];
                }
                return [];
            } else {
                var models = [];
                domain.map(d => {
                    var new_models = this.extract_reference_models(
                        d, field_name);
                    for (var i=0, len=new_models.length; i < len; i++) {
                        var model = new_models[i];
                        if (!~models.indexOf(model)) {
                            models.push(model);
                        }
                    }
                });
                return models;
            }
        },
        _bool_operator: function(domain) {
            var bool_op = 'AND';
            if ((domain.length > 0) &&
                ((domain[0] == 'AND') || (domain[0] == 'OR'))) {
                bool_op = domain[0];
            }
            return bool_op;
        },
        simplify_nested: function(domain) {
            if (!domain.length) {
                return [];
            } else if (this.is_leaf(domain)) {
                return [domain];
            } else if ((domain == 'AND') || (domain == 'OR')) {
                return [domain];
            } else if ((domain instanceof Array) && (domain.length == 1)) {
                return this.simplify_nested(domain[0]);
            } else {
                var simplified = [];
                for (var branch of domain) {
                    var simplified_branch = this.simplify_nested(branch);
                    if ((this._bool_operator(simplified_branch) ==
                                this._bool_operator(simplified)) ||
                            (simplified_branch.length == 1)) {
                        if ((simplified.length > 0) &&
                            (simplified_branch.length > 0) &&
                            ((simplified_branch[0] == 'AND') ||
                                (simplified_branch[0] == 'OR'))) {
                            simplified.push(...simplified_branch.slice(1));
                        } else {
                            simplified.push(...simplified_branch);
                        }
                    } else {
                        simplified.push(simplified_branch);
                    }
                }
                return simplified;
            }
        },
        simplify_duplicate: function(domain) {
            var dedup_branches = [];
            var bool_op = null;
            if (~['AND', 'OR'].indexOf(domain[0])) {
                bool_op = domain[0];
                domain = domain.slice(1);
            }
            for (var branch of domain) {
                var simplified_branch = this.simplify(branch);
                if (simplified_branch.length == 0) {
                    if (bool_op === 'OR') {
                        return [];
                    } else {
                        continue;
                    }
                }
                var found_branch = false;
                for (var duped_branch of dedup_branches) {
                    if (Sao.common.compare(
                        simplified_branch, duped_branch)) {
                        found_branch = true;
                        break;
                    }
                }
                if (!found_branch) {
                    dedup_branches.push(simplified_branch);
                }
            }

            if (bool_op && (dedup_branches.length > 1)) {
                dedup_branches.unshift(bool_op);
            }
            return dedup_branches;
        },
        simplify: function(domain) {
            if (this.is_leaf(domain)) {
                return [domain];
            } else if (!domain.length) {
                return [];
            } else {
                return this.simplify_nested(this.simplify_duplicate(domain));
            }
        },
        simplify_AND: function(domain) {
            if (this.is_leaf(domain)) {
                return domain;
            } else if (domain == 'OR') {
                return domain;
            } else {
                var simplified = [];
                for (const e of domain) {
                    if (e == 'AND') {
                        continue;
                    }
                    simplified.push(this.simplify_AND(e));
                }
                return simplified;
            }
        },
        canonicalize: function(domain) {
            return this.simplify_AND(this.sort(this.simplify(domain)));
        },
        merge: function(domain, domoperator) {
            if (jQuery.isEmptyObject(domain) ||
                    ~['AND', 'OR'].indexOf(domain)) {
                return [];
            }
            var domain_type = domain[0] == 'OR' ? 'OR' : 'AND';
            if (this.is_leaf(domain)) {
                return [domain];
            } else if (domoperator === undefined) {
                return [domain_type].concat([].concat.apply(
                    [], domain.map(e => this.merge(e, domain_type))));
            } else if (domain_type == domoperator) {
                return [].concat.apply(
                    [], domain.map(e => this.merge(e, domain_type)));
            } else {
                // without setting the domoperator
                return [this.merge(domain)];
            }
        },
        concat: function(domains, domoperator) {
            var result = [];
            if (domoperator) {
                result.push(domoperator);
            }
            for (const domain of domains) {
                if (!jQuery.isEmptyObject(domain)) {
                    result.push(domain);
                }
            }
            return this.simplify(this.merge(result));
        },
        unique_value: function(domain, single_value=true) {
            if ((domain instanceof Array) &&
                    (domain.length == 1)) {
                let [name, operator, value, ...model] = domain[0];
                const count = name.split('.').length - 1;
                if (
                    (operator == '=' ||
                        (single_value && operator == 'in' && value.length == 1)) &&
                    (!count ||
                        ((count === 1) && model.length && name.endsWith('.id')))) {
                    value = operator == '=' ? value : value[0];
                    if (model.length && name.endsWith('.id')) {
                        model = model[0];
                        value = [model, value];
                    }
                    return [true, name, value];
                }
            }
            return [false, null, null];
        },
        parse: function(domain) {
            var And = Sao.common.DomainInversion.And;
            var Or = Sao.common.DomainInversion.Or;
            if (this.is_leaf(domain)) {
                return domain;
            } else if (jQuery.isEmptyObject(domain)) {
                return new And([]);
            } else if (domain[0] === 'OR') {
                return new Or(domain.slice(1));
            } else {
                var begin = 0;
                if (domain[0] === 'AND') {
                    begin = 1;
                }
                return new And(domain.slice(begin));
            }
        },
        domain_inversion: function(domain, symbol, context={}) {
            var expression = this.parse(domain);
            if (!~expression.variables.indexOf(symbol)) {
                return true;
            }
            return expression.inverse(symbol, context);
        }
    });
    Sao.common.DomainInversion.equals = function(a, b) {
        if ((a instanceof Array) && (b instanceof Array)) {
            return Sao.common.compare(a, b);
        } else if (moment.isMoment(a) && moment.isMoment(b)) {
            return ((a.isDate == b.isDate) &&
                (a.isDateTime == b.isDateTime) &&
                (a.valueOf() == b.valueOf()));
        } else if ((a instanceof Number) || (b instanceof Number)) {
            return (Number(a) === Number(b));
        } else {
            return (a === b);
        }
    };
    Sao.common.DomainInversion.in_ = function(a, b) {
        if (a instanceof Array) {
            if (b instanceof Array) {
                for (var i = 0, len = a.length; i < len; i++) {
                    if (~b.indexOf(a[i])) {
                        return true;
                    }
                }
                return false;
            } else {
                return Boolean(~a.indexOf(b));
            }
        } else {
            return Boolean(~b.indexOf(a));
        }
    };
    Sao.common.DomainInversion.sql_like = function(value, pattern, ignore_case)
    {
        var escape = false;
        var chars = [];
        var splitted = pattern.split(/(.|\\)/);
        var char;
        for (var i=1, len=splitted.length; i < len; i = i+2) {
            char = splitted[i];
            if (escape) {
                if ((char == '%') || (char == '_')) {
                    chars.push(char);
                } else {
                    chars.push('\\', char);
                }
                escape = false;
            } else if (char == '\\') {
                escape = true;
            } else if (char == '_') {
                chars.push('.');
            } else if (char == '%') {
                chars.push('.*');
            } else {
                chars.push(char);
            }
        }

        if (!pattern.startsWith('%')) {
            chars.splice(0, 0, '^');
        }
        if (!pattern.endsWith('%')) {
            chars.push('$');
        }

        var flags = ignore_case ? 'i' : '';
        var regexp = new RegExp(chars.join(''), flags);
        return regexp.test(value);
    };
    Sao.common.DomainInversion.And = Sao.class_(Object, {
        init: function(expressions) {
            this.domain_inversion = new Sao.common.DomainInversion();
            this.branches = expressions.map(this.domain_inversion.parse.bind(
                    this.domain_inversion));
            this.variables = [];
            for (var i = 0, len = this.branches.length; i < len; i++) {
                var expression = this.branches[i];
                if (this.domain_inversion.is_leaf(expression)) {
                    this.variables.push(this.base(expression[0]));
                } else if (expression instanceof
                    Sao.common.DomainInversion.And) {
                    this.variables = this.variables.concat(
                        expression.variables);
                }
            }
        },
        base: function(expression) {
            if (!expression.contains('.')) {
                return expression;
            } else {
                return expression.split('.')[0];
            }
        },
        inverse: function(symbol, context) {
            var DomainInversion = Sao.common.DomainInversion;
            var result = [];
            for (var i = 0, len = this.branches.length; i < len; i++) {
                var part = this.branches[i];
                if (part instanceof DomainInversion.And) {
                    var part_inversion = part.inverse(symbol, context);
                    var evaluated = typeof part_inversion == 'boolean';
                    if (!~part.variables.indexOf(symbol)) {
                        continue;
                    }
                    if (!evaluated) {
                        result.push(part_inversion);
                    } else if (part_inversion) {
                        continue;
                    } else {
                        return false;
                    }
                } else if (this.domain_inversion.is_leaf(part) &&
                        (this.base(part[0]) === symbol)) {
                    result.push(part);
                } else {
                    var field = part[0];
                    if ((!(field in context)) ||
                        ((field in context) &&
                            (this.domain_inversion.eval_leaf(
                                part, context, this.domain_inversion.and) ||
                                this.domain_inversion.constrained_leaf(
                                    part, this.domain_inversion.and)))) {
                        result.push(true);
                    } else {
                        return false;
                    }
                }
            }
            result = result.filter(function(e) {
                return e !== true;
            });
            if (jQuery.isEmptyObject(result)) {
                return true;
            } else {
                return this.domain_inversion.simplify(result);
            }
        }
    });
    Sao.common.DomainInversion.Or = Sao.class_(Sao.common.DomainInversion.And, {
        inverse: function(symbol, context) {
            var DomainInversion = Sao.common.DomainInversion;
            var result = [];
            if (!jQuery.isEmptyObject(this.variables.filter(function(e) {
                    return (!(e in context)) && (e != symbol);
                }))) {
                // In this case we don't know enough about this OR part, we
                // consider it to be True (because people will have the
                // constraint on this part later).
                return true;
            }
            for (var i = 0, len = this.branches.length; i < len; i++) {
                var part = this.branches[i];
                if (part instanceof DomainInversion.And) {
                    var part_inversion = part.inverse(symbol, context);
                    var evaluated = typeof part_inversion == 'boolean';
                    if (!~part.variables.indexOf(symbol)) {
                        if (evaluated && part_inversion) {
                            return true;
                        }
                        continue;
                    }
                    if (!evaluated) {
                        result.push(part_inversion);
                    } else if (part_inversion) {
                        return true;
                    } else {
                        continue;
                    }
                } else if (this.domain_inversion.is_leaf(part) &&
                        (this.base(part[0]) == symbol)) {
                    result.push(part);
                } else {
                    var field = part[0];
                    field = this.base(field);
                    if ((field in context) &&
                        (this.domain_inversion.eval_leaf(
                            part, context, this.domain_inversion.or)) ||
                        this.domain_inversion.constrained_leaf(
                            part, this.domain_inversion.or)) {
                        return true;
                    } else if ((field in context) &&
                            !this.domain_inversion.eval_leaf(part, context,
                                this.domain_inversion.or)) {
                        result.push(false);
                    }
                }
            }
            result = result.filter(function(e) {
                return e !== false;
            });
            if (jQuery.isEmptyObject(result)) {
                return false;
            } else {
                return this.domain_inversion.simplify(['OR'].concat(result));
            }
        }
    });

    Sao.common.mimetypes = {
        'csv': 'text/csv',
        'doc': 'application/msword',
        'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'gif': 'image/gif',
        'html': 'text/html',
        'jpeg': 'image/jpeg',
        'jpg': 'image/jpeg',
        'mpeg': 'video/mpeg',
        'mpg': 'video/mpeg',
        'ods': 'application/vnd.oasis.opendocument.spreadsheet',
        'odt': 'application/vnd.oasis.opendocument.text',
        'ogg': 'audio/ogg',
        'pdf': 'application/pdf',
        'png': 'image/png',
        'svg': 'image/svg+xml',
        'text': 'text/plain',
        'tif': 'image/tif',
        'tiff': 'image/tif',
        'txt': 'text/plain',
        'webp': 'image/webp',
        'xls': 'application/vnd.ms-excel',
        'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'xml': 'application/xml',
        'xpm': 'image/x-xpixmap',
    };

    Sao.common.guess_mimetype = function(filename) {
        for (var ext in Sao.common.mimetypes) {
            var re = new RegExp('.*.' + ext + '$', 'i');
            if (re.test(filename)) {
                return Sao.common.mimetypes[ext];
            }
        }
        return 'application/octet-binary';
    };

    Sao.common.LOCAL_ICONS = [
        'tryton-add',
        'tryton-archive',
        'tryton-arrow-down',
        'tryton-arrow-left',
        'tryton-arrow-right',
        'tryton-arrow-up',
        'tryton-attach',
        'tryton-back',
        'tryton-barcode-scanner',
        'tryton-bookmark-border',
        'tryton-bookmarks',
        'tryton-bookmark',
        'tryton-cancel',
        'tryton-clear',
        'tryton-close',
        'tryton-copy',
        'tryton-create',
        'tryton-date',
        'tryton-delete',
        'tryton-download',
        'tryton-drag',
        'tryton-email',
        'tryton-error',
        'tryton-exit',
        'tryton-export',
        'tryton-filter',
        'tryton-format-align-center',
        'tryton-format-align-justify',
        'tryton-format-align-left',
        'tryton-format-align-right',
        'tryton-format-bold',
        'tryton-format-color-text',
        'tryton-format-italic',
        'tryton-format-underline',
        'tryton-forward',
        'tryton-history',
        'tryton-import',
        'tryton-info',
        'tryton-launch',
        'tryton-link',
        'tryton-log',
        'tryton-menu',
        'tryton-note',
        'tryton-ok',
        'tryton-open',
        'tryton-print',
        'tryton-public',
        'tryton-question',
        'tryton-refresh',
        'tryton-remove',
        'tryton-save',
        'tryton-search',
        'tryton-send',
        'tryton-sound-off',
        'tryton-sound-on',
        'tryton-star-border',
        'tryton-star',
        'tryton-switch',
        'tryton-translate',
        'tryton-unarchive',
        'tryton-undo',
        'tryton-unfold-less',
        'tryton-unfold-more',
        'tryton-warning',
    ];

    Sao.common.IconFactory = Sao.class_(Object, {
        batchnum: 10,
        _name2id: {},
        _icons: {},
        load_icons: function(refresh=false) {
            const icon_model = new Sao.Model('ir.ui.icon');
            var icons;
            try {
                icons = icon_model.execute('list_icons', [], {}, false);
            } catch (e) {
                icons = [];
            }
            const name2id = {};
            for (const icon of icons) {
                name2id[icon[1]] = icon[0];
            }
            this._name2id = name2id;
            if (!refresh) {
                for (const icon_name in this._icons) {
                    window.URL.revokeObjectURL(this._icons[icon_name]);
                }
                this._icons = {};
            }
            return name2id;
        },
        _get_icon: function(icon_name) {
            var url = this._icons[icon_name];
            if (url !== undefined) {
                return jQuery.when(url);
            }
            if (~Sao.common.LOCAL_ICONS.indexOf(icon_name)) {
                return jQuery.get('images/' + icon_name + '.svg', null, null, 'text')
                    .then(icon => {
                        var img_url = this._convert(icon);
                        this._icons[icon_name] = img_url;
                        return img_url;
                    })
                    .fail(() => {
                        Sao.Logger.error("Unknown icon %s", icon_name);
                        this._icons[icon_name] = null;
                    });
            }
            var name2id = this._name2id;
            if (!(icon_name in name2id)) {
                name2id = this.load_icons(true);
                if (!(icon_name in name2id)) {
                    Sao.Logger.error("Unknown icon %s", icon_name);
                    this._icons[icon_name] = null;
                    return jQuery.when();
                }
            }
            var ids = [];
            for (const name in name2id) {
                if ((!(name in this._icons)) || (name == icon_name)) {
                    ids.push(name2id[name]);
                }
            }
            const idx = ids.indexOf(name2id[icon_name]);
            const from = Math.max(Math.round(idx - this.batchnum / 2), 0);
            const to = Math.round(idx + this.batchnum / 2);
            ids = ids.slice(from, to);

            var icon_model = new Sao.Model('ir.ui.icon');
            var icons;
            try {
                icons = icon_model.execute(
                    'read', [ids, ['name', 'icon']], {}, false);
            } catch(e) {
                icons = [];
            }
            for (const icon of icons) {
                const icon_url = this._convert(icon.icon);
                this._icons[icon.name] = icon_url;
                if (icon.name == icon_name) {
                    url = icon_url;
                }
            }
            return jQuery.when(url);
        },
        _convert: function(data) {
            var xml = jQuery.parseXML(data);
            jQuery(xml).find('svg').attr('fill', Sao.config.icon_colors[0]);
            data = new XMLSerializer().serializeToString(xml);
            var blob = new Blob([data],
                {type: 'image/svg+xml'});
            return window.URL.createObjectURL(blob);
        },
        get_icon_url: function(icon_name) {
            if (!icon_name) {
                return jQuery.when('');
            }
            return this._get_icon(icon_name);
        },
        get_icon_img: function(icon_name, attrs) {
            attrs = attrs || {};
            if (!attrs['class']) {
                attrs['class'] = 'icon';
            }
            var img = jQuery('<img/>', attrs);
            if (icon_name) {
                this.get_icon_url(icon_name).then(function(url) {
                    img.attr('src', url);
                });
            }
            return img;
        },
    });

    Sao.common.ICONFACTORY = new Sao.common.IconFactory();

    Sao.common.UniqueDialog = Sao.class_(Object, {
        size: undefined,
        init: function() {
            this.running = false;
        },
        build_dialog: function() {
            var dialog = new Sao.Dialog('', this.class_, this.size, false);
            return dialog;
        },
        run: function() {
            if (this.running) {
                return jQuery.when();
            }
            var args = Array.prototype.slice.call(arguments);
            var prm = jQuery.Deferred();
            args.push(prm);
            var dialog = this.build_dialog.apply(this, args);
            dialog.content.submit(evt => {
                evt.preventDefault();
                dialog.footer.find('button.btn-primary').first().click();
            });
            this.running = true;
            dialog.modal.modal('show');
            dialog.modal.on('shown.bs.modal', function() {
                dialog.modal.find('input,select')
                    .filter(':visible').first().focus();
            });
            dialog.modal.on('keydown', e => {
                if (e.which == Sao.common.ESC_KEYCODE) {
                    this.close(dialog);
                    prm.reject();
                }
            });
            return prm;
        },
        close: function(dialog) {
            dialog.modal.on('hidden.bs.modal', function(event) {
                jQuery(this).remove();
            });
            dialog.modal.modal('hide');
            this.running = false;
        }
    });

    Sao.common.MessageDialog = Sao.class_(Sao.common.UniqueDialog, {
        class_: 'message-dialog',
        build_dialog: function(message, icon, prm) {
            var dialog = Sao.common.MessageDialog._super.build_dialog.call(
                this);
            dialog.header.remove();
            dialog.body.append(jQuery('<div/>', {
                'class': 'alert alert-info',
                role: 'alert'
            }).append(jQuery('<span/>')
                .text(message)
                .css('white-space', 'pre-wrap')));
            jQuery('<button/>', {
                'class': 'btn btn-primary',
                'type': 'button',
                'title': Sao.i18n.gettext("OK"),
            }).text(Sao.i18n.gettext('OK')).click(() => {
                this.close(dialog);
                prm.resolve('ok');
            }).appendTo(dialog.footer);
            return dialog;
        },
        run: function(message, icon) {
            return Sao.common.MessageDialog._super.run.call(
                    this, message, icon || 'tryton-info');
        }
    });
    Sao.common.message = new Sao.common.MessageDialog();

    Sao.common.WarningDialog = Sao.class_(Sao.common.UniqueDialog, {
        class_: 'warning-dialog',
        size: 'md',
        build_dialog: function(message, title, prm) {
            var dialog = Sao.common.WarningDialog._super.build_dialog.call(
                this);
            var content = jQuery('<div/>', {
                'class': 'alert alert-warning',
                role: 'alert'
            }).append(jQuery('<h4/>')
                .text(title)
                .css('white-space', 'pre-wrap'));
            if (message) {
                content.append(jQuery('<span/>')
                    .text(message)
                    .css('white-space', 'pre-wrap'));
            }
            dialog.body.append(content);
            jQuery('<button/>', {
                'class': 'btn btn-primary',
                'type': 'button',
                'title': Sao.i18n.gettext("OK"),
            }).text(Sao.i18n.gettext('OK')).click(() => {
                this.close(dialog);
                prm.resolve('ok');
            }).appendTo(dialog.footer);
            return dialog;
        }
    });
    Sao.common.warning = new Sao.common.WarningDialog();

    Sao.common.UserWarningDialog = Sao.class_(Sao.common.WarningDialog, {
        class_: 'user-warning-dialog',
        size: 'md',
        build_dialog: function(message, title, prm) {
            var dialog = Sao.common.UserWarningDialog._super.build_dialog.call(
                this, message, title, prm);
            var always = jQuery('<input/>', {
                'type': 'checkbox'
            });
            dialog.body.append(jQuery('<div/>', {
                'class': 'checkbox',
            }).append(jQuery('<label/>')
                .text(Sao.i18n.gettext("Always ignore this warning."))
                .prepend(always))
            );
            dialog.body.append(jQuery('<p/>')
                    .text(Sao.i18n.gettext('Do you want to proceed?')));
            dialog.footer.empty();
            jQuery('<button/>', {
                'class': 'btn btn-link',
                'type': 'button',
                'title': Sao.i18n.gettext("No"),
            }).text(Sao.i18n.gettext('No')).click(() => {
                this.close(dialog);
                prm.reject();
            }).appendTo(dialog.footer);
            jQuery('<button/>', {
                'class': 'btn btn-primary',
                'type': 'button',
                'title': Sao.i18n.gettext("Yes"),
            }).text(Sao.i18n.gettext('Yes')).click(() => {
                this.close(dialog);
                if (always.prop('checked')) {
                    prm.resolve('always');
                }
                prm.resolve('ok');
            }).appendTo(dialog.footer);
            return dialog;
        }
    });
    Sao.common.userwarning = new Sao.common.UserWarningDialog();

    Sao.common.ConfirmationDialog = Sao.class_(Sao.common.UniqueDialog, {
        class_: 'confirmation-dialog',
        build_dialog: function(message) {
            var dialog = Sao.common.ConfirmationDialog._super.build_dialog.call(
                this);
            dialog.header.remove();
            dialog.body.append(jQuery('<div/>', {
                'class': 'alert alert-info',
                role: 'alert'
            }).append(jQuery('<span/>')
                .text(message)
                .css('white-space', 'pre-wrap')));
            return dialog;
        }
    });

    Sao.common.SurDialog = Sao.class_(Sao.common.ConfirmationDialog, {
        build_dialog: function(message, prm) {
            var dialog = Sao.common.SurDialog._super.build_dialog.call(
                this, message);
            jQuery('<button/>', {
                'class': 'btn btn-link',
                'type': 'button',
                'title': Sao.i18n.gettext("Cancel"),
            }).text(Sao.i18n.gettext('Cancel')).click(() => {
                this.close(dialog);
                prm.reject();
            }).appendTo(dialog.footer);
            jQuery('<button/>', {
                'class': 'btn btn-primary',
                'type': 'button',
                'title': Sao.i18n.gettext("OK"),
            }).text(Sao.i18n.gettext('OK')).click(() => {
                this.close(dialog);
                prm.resolve();
            }).appendTo(dialog.footer);
            return dialog;
        }
    });
    Sao.common.sur = new Sao.common.SurDialog();

    Sao.common.Sur3BDialog = Sao.class_(Sao.common.ConfirmationDialog, {
        build_dialog: function(message, prm) {
            var dialog = Sao.common.SurDialog._super.build_dialog.call(
                this, message);
            jQuery('<button/>', {
                'class': 'btn btn-link',
                'type': 'button',
                'title': Sao.i18n.gettext("Cancel"),
            }).text(Sao.i18n.gettext('Cancel')).click(() => {
                this.close(dialog);
                prm.resolve('cancel');
            }).appendTo(dialog.footer);
            jQuery('<button/>', {
                'class': 'btn btn-default',
                'type': 'button',
                'title': Sao.i18n.gettext("No"),
            }).text(Sao.i18n.gettext('No')).click(() => {
                this.close(dialog);
                prm.resolve('ko');
            }).appendTo(dialog.footer);
            jQuery('<button/>', {
                'class': 'btn btn-primary',
                'type': 'button',
                'title': Sao.i18n.gettext("Yes"),
            }).text(Sao.i18n.gettext('Yes')).click(() => {
                this.close(dialog);
                prm.resolve('ok');
            }).appendTo(dialog.footer);
            return dialog;
        }
    });
    Sao.common.sur_3b = new Sao.common.Sur3BDialog();

    Sao.common.AskDialog = Sao.class_(Sao.common.UniqueDialog, {
        class_: 'ask-dialog',
        run: function() {
            var args = Array.prototype.slice.call(arguments);
            if (args.length == 2) {
                args.push(true);
            }
            return Sao.common.AskDialog._super.run.apply(this, args);
        },
        build_dialog: function(question, name, visibility, prm) {
            var dialog = Sao.common.AskDialog._super.build_dialog.call(this);
            dialog.header.remove();
            var entry = jQuery('<input/>', {
                'class': 'form-control',
                'type': visibility ? 'input' : 'password',
                'id': 'ask-dialog-entry',
                'name': name,
            });
            dialog.body.append(jQuery('<div/>', {
                'class': 'form-group'
            }).append(jQuery('<label/>', {
                'for': 'ask-dialog-entry'
            }).text(question)).append(entry));
            jQuery('<button/>', {
                'class': 'btn btn-link',
                'type': 'button',
                'title': Sao.i18n.gettext("Cancel"),
            }).text(Sao.i18n.gettext('Cancel')).click(() => {
                this.close(dialog);
                prm.reject();
            }).appendTo(dialog.footer);
            jQuery('<button/>', {
                'class': 'btn btn-primary',
                'type': 'button',
                'title': Sao.i18n.gettext("OK"),
            }).text(Sao.i18n.gettext('OK')).click(() => {
                this.close(dialog);
                prm.resolve(entry.val());
            }).appendTo(dialog.footer);
            return dialog;
        }
    });
    Sao.common.ask = new Sao.common.AskDialog();

    Sao.common.ConcurrencyDialog = Sao.class_(Sao.common.UniqueDialog, {
        class_: 'ask-dialog',
        size: 'md',
        build_dialog: function(model, record_id, context, prm) {
            var dialog = Sao.common.ConcurrencyDialog._super.build_dialog.call(
                this);
            dialog.add_title(Sao.i18n.gettext("Concurrency Warning"));
            dialog.body.append(jQuery('<div/>', {
                'class': 'alert alert-info',
                role: 'alert'
            }).append(jQuery('<p/>')
                .text(Sao.i18n.gettext('This record has been modified ' +
                'while you were editing it.')))
                .append(jQuery('<p/>').text(Sao.i18n.gettext('Choose:')))
                .append(jQuery('<ul/>')
                    .append(jQuery('<li/>')
                        .text(Sao.i18n.gettext('"Cancel" to cancel saving;')))
                    .append(jQuery('<li/>')
                        .text(Sao.i18n.gettext(
                                '"Compare" to see the modified version;')))
                    .append(jQuery('<li/>')
                        .text(Sao.i18n.gettext(
                                '"Write Anyway" to save your current version.'))))
                );
            jQuery('<button/>', {
                'class': 'btn btn-link',
                'type': 'button',
                'title': Sao.i18n.gettext("Cancel"),
            }).text(Sao.i18n.gettext('Cancel')).click(() => {
                this.close(dialog);
                prm.reject();
            }).appendTo(dialog.footer);
            jQuery('<button/>', {
                'class': 'btn btn-default',
                'type': 'button',
                'title': Sao.i18n.gettext("Compare"),
            }).text(Sao.i18n.gettext('Compare')).click(() => {
                this.close(dialog);
                Sao.rpc({
                    'method': 'model.' + model + '.read',
                    'params': [[record_id], ['rec_name'], context],
                }, Sao.Session.current_session).then(function(result) {
                    var name = result[0].rec_name;
                    Sao.Tab.create({
                        'model': model,
                        'res_id': record_id,
                        name: Sao.i18n.gettext("Compare: %1", name),
                        'domain': [['id', '=', record_id]],
                        'context': context,
                        'mode': ['form'],
                    });
                    prm.reject();
                });
            }).appendTo(dialog.footer);
            jQuery('<button/>', {
                'class': 'btn btn-default',
                'type': 'button',
                'title': Sao.i18n.gettext("Write Anyway"),
            }).text(Sao.i18n.gettext('Write Anyway')).click(() => {
                this.close(dialog);
                prm.resolve();
            }).appendTo(dialog.footer);
            return dialog;
        }
    });
    Sao.common.concurrency = new Sao.common.ConcurrencyDialog();

    Sao.common.ErrorDialog = Sao.class_(Sao.common.UniqueDialog, {
        class_: 'error-dialog',
        size: 'md',
        build_dialog: function(title, details, prm) {
            var dialog = Sao.common.ConcurrencyDialog._super.build_dialog.call(
                this);
            dialog.add_title(Sao.i18n.gettext('Application Error'));
            const alert_ = jQuery('<div/>', {
                'class': 'alert alert-danger',
                role: 'alert'
            }).appendTo(dialog.body);
            alert_.append(jQuery('<h4/>')
                .text(title)
                .css('white-space', 'pre-wrap'));
            alert_.append(jQuery('<p/>').append(jQuery('<a/>', {
                'class': 'btn btn-default',
                role: 'button',
                'data-toggle': 'collapse',
                'data-target': '#error-detail',
                'aria-expanded': false,
                'aria-controls': '#error-detail',
            }).text(Sao.i18n.gettext("Details"))));
            alert_.append(jQuery('<p/>', {
                'class': 'collapse',
                id: 'error-detail',
            }).append(jQuery('<pre/>', {
                'class': 'pre-scrollable',
            }).text(details)));
            jQuery('<a/>', {
                'class': 'btn btn-link',
                href: Sao.config.bug_url,
                target: '_blank',
                rel: 'noreferrer noopener',
            }).text(Sao.i18n.gettext('Report Bug')).appendTo(dialog.footer);
            jQuery('<button/>', {
                'class': 'btn btn-primary',
                'type': 'button',
                'title': Sao.i18n.gettext("Close"),
            }).text(Sao.i18n.gettext('Close')).click(() => {
                this.close(dialog);
                prm.resolve();
            }).appendTo(dialog.footer);
            return dialog;
        }
    });
    Sao.common.error = new Sao.common.ErrorDialog();

    Sao.common.Processing = Sao.class_(Object, {
        queries: 0,
        timeout: 3000,
        init: function() {
            this.el = jQuery('<div/>', {
                'id': 'processing',
                'class': 'text-center'
            });
            var label = jQuery('<span/>', {
                'class': 'label label-info',
                'text': Sao.i18n.gettext('Processing'),
            }).appendTo(this.el);
            for (var i = 0; i < 3; i ++) {
                label.append(jQuery('<span/>', {
                    'class': 'dot',
                    'text': '.',
                }));
            }
            this.el.hide();
            jQuery(() => {
                this.el.appendTo('body');
            });
        },
        show: function() {
            return window.setTimeout(() => {
                this.queries += 1;
                this.el.show();
            }, this.timeout);
        },
        hide: function(timeoutID) {
            window.clearTimeout(timeoutID);
            if (this.queries > 0) {
                this.queries -= 1;
            }
            if (this.queries <= 0) {
                this.queries = 0;
                this.el.hide();
            }
        }
    });
    Sao.common.processing = new Sao.common.Processing();

    Sao.common.set_overflow = function set_overflow(el, state) {
        // We must set the overflow of the treeview and modal-body
        // containing the input to visible to prevent vertical scrollbar
        // inherited from the auto overflow-x
        // Idem when in navbar collapse for the overflow-y
        // (see http://www.w3.org/TR/css-overflow-3/#overflow-properties)
        var overflow, height;
        if (state == 'hide') {
            overflow = '';
            height = '';
        } else {
            overflow = 'visible';
            height = 'none';
        }
        el.closest('.treeview')
            .css('overflow', overflow)
            .css('max-height', height);
        el.closest('.modal-body').css('overflow', overflow);
        el.closest('.navbar-collapse.in').css('overflow-y', overflow);
        el.closest('.content-box').css('overflow-y', overflow);
        el.parents('fieldset.form-group_').css('overflow', overflow);
        Sao.common.scrollIntoViewIfNeeded(el);
    };

    Sao.common.InputCompletion = Sao.class_(Object, {
        init: function(el, source, match_selected, format) {
            if (!el.is('input')) {
                el.addClass('dropdown');
                this.dropdown = el;
            } else {
                el.wrap('<div class="dropdown"/>');
                this.dropdown = el.parent();
            }
            this.input = el.find('input').add(el.filter('input')).first();
            this.input.attr('autocomplete', 'off');
            // bootstrap requires an element with data-toggle
            jQuery('<span/>', {
                'data-toggle': 'dropdown'
            }).appendTo(this.dropdown);
            this.menu = jQuery('<ul/>', {
                'class': 'dropdown-menu',
                'role': 'listbox'
            }).appendTo(this.dropdown);
            this.separator = jQuery('<li/>', {
                'role': 'separator',
                'class': 'divider'
            }).appendTo(this.menu);
            this.separator.hide();

            this.source = source;
            this.match_selected = match_selected;
            this.format = format;
            this.action_activated = null;

            this._search_text = null;

            this.input.on('input', () => {
                window.setTimeout(this._input.bind(this), 300,
                        this.input.val());
            });
            this.input.keydown(evt => {
                if (evt.which == Sao.common.ESC_KEYCODE) {
                    if (this.dropdown.hasClass('open')) {
                        evt.preventDefault();
                        evt.stopPropagation();
                        this.menu.dropdown('toggle');
                    }
                } else if (evt.which == Sao.common.DOWN_KEYCODE) {
                    if (this.dropdown.hasClass('open')) {
                        evt.preventDefault();
                        evt.stopPropagation();
                        this.menu.find('li > a').first().focus();
                    }
                }
            });
            this.menu.keydown(evt => {
                if (evt.which == Sao.common.ESC_KEYCODE) {
                    evt.preventDefault();
                    evt.stopPropagation();
                    this.menu.dropdown('toggle');
                }
            });
            this.dropdown.on('hide.bs.dropdown', () => {
                this.input.focus();
                Sao.common.set_overflow(this.input, 'hide');
            });
            this.dropdown.on('show.bs.dropdown', () => {
                Sao.common.set_overflow(this.input, 'show');
            });
        },
        set_actions: function(action_activated, search=true, create=true) {
            if (action_activated !== undefined) {
                this.action_activated = action_activated;
            }
            var actions = [];
            if (search) {
                actions.push(['search', Sao.i18n.gettext('Search...')]);
            }
            if (create) {
                actions.push(['create', Sao.i18n.gettext('Create...')]);
            }
            this.menu.find('li.action').remove();
            if (jQuery.isEmptyObject(actions)) {
                this.separator.hide();
                return;
            }
            this.separator.show();
            actions.forEach(function(action) {
                var action_id = action[0];
                var content = action[1];
                jQuery('<li/>', {
                    'class': 'action action-' + action_id
                }).append(jQuery('<a/>', {
                    'href': '#'
                }).text(this._format_action(content)))
                .click(evt => {
                    evt.preventDefault();
                    if (this.action_activated) {
                        this.action_activated(action_id);
                    }
                    this.input.val('');
                })
                .appendTo(this.menu);
            }, this);
        },
        _format: function(content) {
            if (this.format) {
                return this.format(content);
            }
            return jQuery('<span/>').text(content);
        },
        _format_action: function(content) {
            if (this.format_action) {
                return this.format_action(content);
            }
            return content;
        },
        _input: function(text) {
            if (text != this.input.val()) {
                return;
            }
            var prm;
            if (this.source instanceof Array) {
                prm = jQuery.when(this.source.filter(function(value) {
                    return value.toLowerCase().startsWith(text.toLowerCase());
                }));
            } else {
                prm = this.source(text);
            }
            prm.then(values => {
                if (text != this.input.val()) {
                    return;
                }
                this._set_selection(values);
            });
        },
        _set_selection: function(values) {
            if (values === undefined) {
                values = [];
            }
            this.menu.find('li.completion').remove();
            values.reverse().forEach(function(value) {
                jQuery('<li/>', {
                    'class': 'completion'
                }).append(jQuery('<a/>', {
                    'href': '#'
                }).append(this._format(value)))
                .click(evt => {
                    evt.preventDefault();
                    if (this.match_selected) {
                        this.match_selected(value);
                    }
                    this.input.focus();
                }).prependTo(this.menu);
            }, this);
            if (!this.input.val() || (
                !this.menu.find('li.completion').length &&
                !this.menu.find('li.action').length)) {
                if (this.dropdown.hasClass('open')) {
                    this.menu.dropdown('toggle');
                }
            } else {
                if (!this.dropdown.hasClass('open')) {
                    this.menu.dropdown('toggle');
                }
            }
        }
    });

    Sao.common.get_completion = function(el, source,
            match_selected, action_activated, search=true, create=true) {
        var format = function(content) {
            return content.name;
        };
        var completion = new Sao.common.InputCompletion(
                el, source, match_selected, format);
        if (action_activated) {
            completion.set_actions(action_activated, search, create);
        }
        completion._allow_create = create;
        return completion;
    };

    Sao.common.update_completion = function(
            entry, record, field, model, domain) {
        var search_text = entry.val();
        if (!search_text || !model) {
            return jQuery.when();
        }
        if (domain === undefined) {
            domain = field.get_domain(record);
        }
        var context = field.get_search_context(record);

        var order = field.get_search_order(record);
        var sao_model = new Sao.Model(model);
        return sao_model.execute(
            'autocomplete',
            [search_text, domain, Sao.config.limit, order], context)
        .then(
            function(result) {
                return result.filter((value) => {
                    return value.id || entry.completion._allow_create;
                }).map((value) => {
                    if (value.id === null) {
                        value.name = Sao.i18n.gettext(
                            'Create "%1"...', value.name);
                    }
                    return value;
                });
            },
            function() {
                Sao.Logger.warn(
                    "Unable to search for completion of %s", model);
            });
    };

    Sao.common.Paned = Sao.class_(Object, {
        init: function(orientation) {
            var row;
            this._orientation = orientation;
            this.el = jQuery('<div/>');
            if (orientation == 'horizontal') {
                row = jQuery('<div/>', {
                    'class': 'row'
                }).appendTo(this.el);
                this.child1 = jQuery('<div/>', {
                    'class': 'col-md-6'
                }).appendTo(row);
                this.child2 = jQuery('<div/>', {
                    'class': 'col-md-6'
                }).appendTo(row);
            } else if (orientation == 'vertical') {
                this.child1 = jQuery('<div/>', {
                    'class': 'row'
                }).appendTo(this.el);
                this.child2 = jQuery('<div/>', {
                    'class': 'row'
                }).appendTo(this.el);
            }
        },
        get_child1: function() {
            return this.child1;
        },
        get_child2: function() {
            return this.child2;
        }
    });

    Sao.common.get_focus_chain = function(element) {
        var elements = element.find('input,select,textarea');
        elements.sort(function(a, b) {
            if (('tabindex' in a.attributes) && ('tabindex' in b.attributes)) {
                var a_tabindex = parseInt(a.attributes.tabindex.value);
                var b_tabindex = parseInt(b.attributes.tabindex.value);
                return a_tabindex - b_tabindex;
            } else if ('tabindex' in a.attributes) {
                return -1;
            } else if ('tabindex' in b.attributes) {
                return 1;
            } else {
                return 0;
            }
        });
        return elements;
    };

    Sao.common.find_focusable_child = function(element) {
        var i, len, children, focusable;

        if (!element.is(':visible')) {
            return null;
        }
        if (~['input', 'select', 'textarea'].indexOf(
            element[0].tagName.toLowerCase()) &&
            !element.prop('readonly')) {
            return element;
        }

        children = Sao.common.get_focus_chain(element);
        for (i = 0, len = children.length; i < len; i++) {
            focusable = Sao.common.find_focusable_child(jQuery(children[i]));
            if (focusable) {
                return focusable;
            }
        }
    };

    Sao.common.find_first_focus_widget = function(ancestor, widgets) {
        var i, j;
        var children, commons, is_common;

        if (widgets.length == 1) {
            return jQuery(widgets[0]);
        }
        children = Sao.common.get_focus_chain(ancestor);
        for (i = 0; i < children.length; i++) {
            commons = [];
            for (j = 0; j < widgets.length; j++) {
                is_common = jQuery(widgets[j]).closest(children[i]).length > 0;
                if (is_common) {
                    commons.push(widgets[j]);
                }
            }
            if (commons.length > 0) {
                return Sao.common.find_first_focus_widget(jQuery(children[i]),
                        commons);
            }
        }
    };

    Sao.common.apply_label_attributes = function(label, readonly, required) {
        if (!readonly) {
            label.addClass('editable');
            if (required) {
                label.addClass('required');
            } else {
                label.removeClass('required');
            }
        } else {
            label.removeClass('editable required');
        }
    };

    Sao.common.download_file = function(data, name, options) {
        if (options === undefined) {
            var type = Sao.common.guess_mimetype(name);
            options = {type: type};
        }
        var blob = new Blob([data], options);

        if (window.navigator && window.navigator.msSaveOrOpenBlob) {
            window.navigator.msSaveOrOpenBlob(blob, name);
            return;
        }

        var blob_url = window.URL.createObjectURL(blob);

        var dialog = new Sao.Dialog(Sao.i18n.gettext('Download'));
        var close = function() {
            dialog.modal.modal('hide');
        };
        var a = jQuery('<a/>', {
                'href': blob_url,
                'download': name,
                'text': name,
                'target': '_blank'
                }).appendTo(dialog.body)
                .click(close);
        jQuery('<button/>', {
            'class': 'btn btn-default',
            'type': 'button',
            'title': Sao.i18n.gettext("Close"),
        }).text(Sao.i18n.gettext('Close')).click(close)
            .appendTo(dialog.footer);
        dialog.modal.on('shown.bs.modal', function() {
            // Force the click trigger
            a[0].click();
        });
        dialog.modal.modal('show');

        dialog.modal.on('hidden.bs.modal', function() {
            jQuery(this).remove();
            window.URL.revokeObjectURL(this.blob_url);
        });

    };

    Sao.common.get_input_data = function(input, callback, char_) {
        for (var i = 0; i < input[0].files.length; i++) {
            Sao.common.get_file_data(input[0].files[i], callback, char_);
        }
    };

    Sao.common.get_file_data = function(file, callback, char_) {
        var reader = new FileReader();
        reader.onload = function() {
            var value = new Uint8Array(reader.result);
            if (char_) {
                value = String.fromCharCode.apply(null, value);
            }
            callback(value, file.name);
        };
        reader.readAsArrayBuffer(file);
    };

    Sao.common.ellipsize = function(string, length) {
        if (string.length <= length) {
            return string;
        }
        var ellipsis = Sao.i18n.gettext('...');
        return string.slice(0, length - ellipsis.length) + ellipsis;
    };

    Sao.common.accesskey = function(string) {
        for (var i=0; i < string.length; i++) {
            var c = string.charAt(i).toLowerCase();
            // Skip sao and browser shortcuts
            if (!~['d', 'e', 'f', 'i', 'n', 't', 'w'].indexOf(c)) {
                return c;
            }
        }
    };

    Sao.common.debounce = function(func, wait) {
        return (...args) => {
            clearTimeout(func._debounceTimeout);
            func._debounceTimeout = setTimeout(() => {
                func.apply(this, args);
            }, wait);
        };
    };

    Sao.common.uuid4 = function() {
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g,
            function(c) {
                var r = Math.random() * 16 | 0;
                var v = c == 'x' ? r : (r & 0x3 | 0x8);
                return v.toString(16);
            });
    };

    Sao.common.COLOR_SCHEMES = {
        'red': '#cf1d1d',
        'green': '#3fb41b',
        'blue': '#224565',
        'grey': '#444444',
        'black': '#000000',
        'darkcyan': '#305755',
    };

    Sao.common.hex2rgb = function(hexstring, digits) {
        digits = digits || 2;
        var top = parseInt('f'.repeat(digits), 16);
        var r = parseInt(
            hexstring.substring(1, digits + 1), 16);
        var g = parseInt(
            hexstring.substring(digits + 1, digits * 2 + 1), 16);
        var b = parseInt(
            hexstring.substring(digits * 2 + 1, digits * 3 + 1), 16);
        return [r / top, g / top, b / top];
    };

    Sao.common.rgb2hex = function(rgb, digits) {
        digits = digits || 2;
        var top = parseInt('f'.repeat(digits), 16);
        return '#' + rgb
            .map(function(i) { return Math.round(i * top).toString(16); })
            .join('');
    };

    Sao.common.rgb2hsv = function(rgb) {
        var r = rgb[0],
            g = rgb[1],
            b = rgb[2];
        var maxc = Math.max.apply(null, rgb);
        var minc = Math.min.apply(null, rgb);
        var v = maxc;
        if (minc == maxc) return [0, 0, v];
        var s = (maxc - minc) / maxc;
        var rc = (maxc - r) / (maxc - minc);
        var gc = (maxc - g) / (maxc - minc);
        var bc = (maxc - b) / (maxc - minc);
        var h;
        if (r == maxc) {
            h = bc - gc;
        } else if (g == maxc) {
            h = 2 + rc - bc;
        } else {
            h = 4 + gc - rc;
        }
        h = (h / 6) % 1;
        return [h, s, v];
    };

    Sao.common.hsv2rgb = function(hsv) {
        var h = hsv[0],
            s = hsv[1],
            v = hsv[2];
        if (s == 0) return [v, v, v];
        var i = Math.trunc(h * 6);
        var f = (h * 6) - i;
        var p = v * (1 - s);
        var q = v * (1 - s * f);
        var t = v * (1 - s * (1 - f));
        i = i % 6;

        if (i == 0) return [v, t, p];
        else if (i == 1) return [q, v, p];
        else if (i == 2) return [p, v, t];
        else if (i == 3) return [p, q, v];
        else if (i == 4) return [t, p, v];
        else if (i == 5) return [v, p, q];
    };

    Sao.common.generateColorscheme = function(masterColor, keys, light=0.1) {
        var rgb = Sao.common.hex2rgb(
            Sao.common.COLOR_SCHEMES[masterColor] || masterColor);
        var hsv = Sao.common.rgb2hsv(rgb);
        var h = hsv[0],
            s = hsv[1],
            v = hsv[2];
        if (keys.length) {
            light = Math.min(light, (1 - v) / keys.length);
        }
        var golden_angle = 0.618033988749895;
        var colors = {};
        for (var i = 0; i < keys.length; i++) {
            var key = keys[i];
            colors[key] = Sao.common.rgb2hex(Sao.common.hsv2rgb(
                [(h + golden_angle * i) % 1, s, (v + light * i) % 1]));
        }
        return colors;
    };

    Sao.common.richtext_toolbar = function() {
        var toolbar = jQuery('<div/>', {
            'class': 'btn-toolbar',
            'role': 'toolbar',
        });

        var button_apply_command = function(evt) {
            document.execCommand(evt.data);
        };

        var add_buttons = function(buttons) {
            var group = jQuery('<div/>', {
                'class': 'btn-group',
                'role': 'group'
            }).appendTo(toolbar);
            for (const properties of buttons) {
                const button = jQuery('<button/>', {
                    'class': 'btn btn-default',
                    'type': 'button',
                    'title': properties.label,
                }).append(Sao.common.ICONFACTORY.get_icon_img(
                    'tryton-format-' + properties.icon)
                ).appendTo(group);
                button.click(properties.command, button_apply_command);
            }
        };

        add_buttons([
            {
                'icon': 'bold',
                'command': 'bold',
                'label': Sao.i18n.gettext("Bold"),
            }, {
                'icon': 'italic',
                'command': 'italic',
                'label': Sao.i18n.gettext("Italic"),
            }, {
                'icon': 'underline',
                'command': 'underline',
                'label': Sao.i18n.gettext("Underline"),
            }]);

        var selections = [
            {
                'heading': Sao.i18n.gettext('Font'),
                'options': ['Normal', 'Serif', 'Sans', 'Monospace'],  // XXX
                'command': 'fontname'
            }, {
                'heading': Sao.i18n.gettext('Size'),
                'options': [1, 2, 3, 4, 5, 6, 7],
                'command': 'fontsize'
            }];
        var add_option = function(dropdown, properties) {
            return function(option) {
                dropdown.append(jQuery('<li/>').append(jQuery('<a/>', {
                    'href': '#'
                }).text(option).click(function(evt) {
                    evt.preventDefault();
                    document.execCommand(properties.command, false, option);
                })));
            };
        };
        for (var properties of selections) {
            var group = jQuery('<div/>', {
                'class': 'btn-group',
                'role': 'group'
            }).appendTo(toolbar);
            jQuery('<button/>', {
                'class': 'btn btn-default dropdown-toggle',
                'type': 'button',
                'data-toggle': 'dropdown',
                'aria-expanded': false,
                'aria-haspopup': true
            }).append(properties.heading)
                .append(jQuery('<span/>', {
                    'class': 'caret'
                })).appendTo(group);
            var dropdown = jQuery('<ul/>', {
                'class': 'dropdown-menu'
            }).appendTo(group);
            properties.options.forEach(add_option(dropdown, properties));
        }

        add_buttons([
            {
                'icon': 'align-left',
                'command': Sao.i18n.rtl? 'justifyRight' : 'justifyLeft',
                'label': (Sao.i18n.rtl?
                    Sao.i18n.gettext("Justify Right") :
                    Sao.i18n.gettext("Justify Left")),
            }, {
                'icon': 'align-center',
                'command': 'justifyCenter',
                'label': Sao.i18n.gettext("Justify Center"),
            }, {
                'icon': 'align-right',
                'command': Sao.i18n.rtl? 'justifyLeft': 'justifyRight',
                'label': (Sao.i18n.rtl?
                    Sao.i18n.gettext("Justify Left") :
                    Sao.i18n.gettext("Justify Right")),
            }, {
                'icon': 'align-justify',
                'command': 'justifyFull',
                'label': Sao.i18n.gettext("Justify Full"),
            }]);

        // TODO backColor
        [['foreColor', '#000000']].forEach(
            function(e) {
                var command = e[0];
                var color = e[1];
                jQuery('<input/>', {
                    'class': 'btn btn-default',
                    'type': 'color'
                }).appendTo(toolbar)
                    .change(function() {
                        document.execCommand(command, false, jQuery(this).val());
                    }).focusin(function() {
                        document.execCommand(command, false, jQuery(this).val());
                    }).val(color);
            });
        return toolbar;
    };

    Sao.common.richtext_normalize = function(html) {
        var el = jQuery('<div/>').html(html);
        // TODO order attributes
        el.find('div').each(function(i, el) {
            el = jQuery(el);
            // Not all browsers respect the styleWithCSS
            if (el.css('text-align')) {
                // Remove browser specific prefix
                var align = el.css('text-align').split('-').pop();
                el.attr('align', align);
                el.css('text-align', '');
            }
            // Some browsers set start as default align
            if (el.attr('align') == 'start') {
                if (Sao.i18n.rtl) {
                    el.attr('align', 'right');
                } else {
                    el.attr('align', 'left');
                }
            }
        });
        return el.html();
    };

    Sao.common.image_url = function(data) {
        if (!data) {
            return null;
        }
        var type = '';
        try {
            var xml = data;
            if (xml instanceof Uint8Array) {
                xml = new TextDecoder().decode(data);
            }
            if (jQuery.parseXML(xml)) {
                type = 'image/svg+xml';
            }
        } catch (e) {
            // continue
        }
        var blob = new Blob([data], {type: type});
        return window.URL.createObjectURL(blob);
    };

    Sao.common.play_sound = function(sound='success') {
        var snd = new Audio('sounds/' + sound + '.wav');
        snd.volume = localStorage.getItem('sao_sound_volume') || 0.5;
        snd.play();
    };

}());
