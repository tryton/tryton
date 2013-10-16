/* This file is part of Tryton.  The COPYRIGHT file at the top level of
   this repository contains the full copyright notices and license terms. */
(function() {
    'use strict';

    Sao.View = Sao.class_(Object, {
        init: function(screen, xml) {
            this.screen = screen;
            this.view_type = null;
            this.el = null;
            this.fields = {};
        },
        set_value: function() {
        },
        get_fields: function() {
            return Object.keys(this.fields);
        }
    });

    Sao.View.parse = function(screen, xml, children_field) {
        switch (xml.children().prop('tagName')) {
            case 'tree':
                return new Sao.View.Tree(screen, xml, children_field);
            case 'form':
                return new Sao.View.Form(screen, xml);
        }
    };

    Sao.View.tree_column_get = function(type) {
        switch (type) {
            case 'char':
                return Sao.View.Tree.CharColumn;
            case 'many2one':
                return Sao.View.Tree.Many2OneColumn;
            case 'date':
                return Sao.View.Tree.DateColumn;
            case 'datetime':
                return Sao.View.Tree.DateTimeColumn;
            case 'time':
                return Sao.View.Tree.TimeColumn;
            case 'one2many':
                return Sao.View.Tree.One2ManyColumn;
            case 'many2many':
                return Sao.View.Tree.Many2ManyColumn;
            case 'selection':
                return Sao.View.Tree.SelectionColumn;
            case 'reference':
                return Sao.View.Tree.ReferenceColumn;
            case 'float':
            case 'numeric':
                return Sao.View.Tree.FloatColumn;
            case 'float_time':
                return Sao.View.Tree.FloatTimeColumn;
            case 'integer':
            case 'biginteger':
                return Sao.View.Tree.IntegerColumn;
            case 'boolean':
                return Sao.View.Tree.BooleanColumn;
            default:
                return Sao.View.Tree.CharColumn;
        }
    };

    Sao.View.Tree = Sao.class_(Sao.View, {
        init: function(screen, xml, children_field) {
            Sao.View.Tree._super.init.call(this, screen, xml);
            this.view_type = 'tree';
            this.el = jQuery('<div/>', {
                'class': 'treeview'
            });
            this.expanded = {};
            this.children_field = children_field;
            this.keyword_open = xml.children()[0].getAttribute('keyword_open');

            // Columns
            this.columns = [];
            this.create_columns(screen.model, xml);

            // Table of records
            this.rows = [];
            this.table = jQuery('<table/>', {
                'class': 'tree'
            });
            this.el.append(this.table);
            var thead = jQuery('<thead/>');
            this.table.append(thead);
            var tr = jQuery('<tr/>');
            var th = jQuery('<th/>');
            this.selection = jQuery('<input/>', {
                'type': 'checkbox',
                'class': 'selection'
            });
            this.selection.change(this.selection_changed.bind(this));
            th.append(this.selection);
            tr.append(th);
            thead.append(tr);
            this.columns.forEach(function(column) {
                th = jQuery('<th/>', {
                    'text': column.attributes.string
                });
                if (column.attributes.tree_invisible) {
                    th.hide();
                }
                tr.append(th);
            });
            this.tbody = jQuery('<tbody/>');
            this.table.append(this.tbody);

            // Footer for more
            var footer = jQuery('<div/>', {
                'class': 'treefooter'
            });
            this.more = jQuery('<button/>').button({
                'label': 'More' // TODO translation
            }).click(function() {
                this.display_size += Sao.config.display_size;
                this.display();
            }.bind(this));
            footer.append(this.more);
            this.display_size = Sao.config.display_size;
            this.el.append(footer);
        },
        create_columns: function(model, xml) {
            xml.find('tree').children().each(function(pos, child) {
                var column, attribute;
                var attributes = {};
                for (var i = 0, len = child.attributes.length; i < len; i++) {
                    attribute = child.attributes[i];
                    attributes[attribute.name] = attribute.value;
                }
                ['readonly', 'tree_invisible', 'expand', 'completion'].forEach(
                    function(name) {
                        if (attributes[name]) {
                            attributes[name] = attributes[name] == 1;
                        }
                    });
                if (child.tagName == 'field') {
                    var name = child.getAttribute('name');
                    if (name == this.screen.exclude_field) {
                        // TODO is it really the way to do it
                        return;
                    }
                    if (!attributes.widget) {
                        attributes.widget = model.fields[name].description.type;
                    }
                    var attribute_names = ['relation', 'domain', 'selection',
                        'relation_field', 'string', 'views', 'invisible',
                        'add_remove', 'sort', 'context', 'filename'];
                    for (i in attribute_names) {
                        var attr = attribute_names[i];
                        if ((attr in model.fields[name].description) &&
                            (child.getAttribute(attr) === null)) {
                            attributes[attr] = model.fields[name]
                                .description[attr];
                        }
                    }
                    var ColumnFactory = Sao.View.tree_column_get(
                        attributes.widget);
                    column = new ColumnFactory(model, attributes);

                    var prefixes = [], suffixes = [];
                    // TODO support for url/email/callto/sip
                    if ('icon' in attributes) {
                        column.prefixes.push(new Sao.View.Tree.Affix(this,
                                    attributes));
                    }
                    var affix, affix_attributes;
                    var affixes = child.childNodes;
                    for (i = 0; i < affixes.length; i++) {
                        affix = affixes[i];
                        affix_attributes = {};
                        for (i = 0, len = affix.attributes.length; i < len;
                                i++) {
                            attribute = affix.attributes[i];
                            affix_attributes[attribute.name] = attribute.value;
                        }
                        if (affix.tagName == 'prefix') {
                            column.prefixes.push(new Sao.View.Tree.Affix(name,
                                        affix_attributes));
                        } else {
                            column.suffixes.push(new Sao.View.Tree.Affix(name,
                                        affix_attributes));
                        }
                    }

                    this.fields[name] = true;
                    // TODO sum
                } else if (child.tagName == 'button') {
                    column = new Sao.View.Tree.ButtonColumn(this.screen,
                            attributes);
                }
                this.columns.push(column);
            }.bind(this));
        },
        display: function() {
            var selected = this.selected_records();
            var current_record = this.screen.current_record;
            if (current_record && !~selected.indexOf(current_record)) {
                selected = [current_record];
            }
            this.rows = [];
            this.tbody.empty();
            var add_row = function(record, pos, group) {
                var tree_row = new Sao.View.Tree.Row(this, record, pos);
                this.rows.push(tree_row);
                tree_row.display(selected);
            };
            this.screen.group.slice(0, this.display_size).forEach(add_row.bind(this));
            if (this.display_size >= this.screen.group.length) {
                this.more.hide();
            } else {
                this.more.show();
            }
        },
        switch_: function(path) {
            this.screen.row_activate();
        },
        select_changed: function(record) {
            this.screen.set_current_record(record);
            // TODO validate if editable
            // TODO update_children
        },
        selected_records: function() {
            var records = [];
            var add_record = function(row) {
                if (row.is_selected()) {
                    records.push(row.record);
                }
                row.rows.forEach(add_record);
            };
            this.rows.forEach(add_record);
            if (this.selection.prop('checked') &&
                    !this.selection.prop('indeterminate')) {
                this.screen.group.slice(this.rows.length)
                    .forEach(function(record) {
                        records.push(record);
                    });
            }
            return records;
        },
        selection_changed: function() {
            var value = this.selection.prop('checked');
            var set_checked = function(row) {
                row.set_selection(value);
                row.rows.forEach(set_checked);
            };
            this.rows.forEach(set_checked);
            if (value && this.rows[0]) {
                this.select_changed(this.rows[0].record);
            } else {
                this.select_changed(null);
            }
        },
        update_selection: function() {
            if (this.selection.prop('checked')) {
                return;
            }
            var selected_records = this.selected_records();
            this.selection.prop('indeterminate', false);
            if (jQuery.isEmptyObject(selected_records)) {
                this.selection.prop('checked', false);
            } else if (selected_records.length ==
                    this.tbody.children().length &&
                    this.display_size >= this.screen.group.length) {
                this.selection.prop('checked', true);
            } else {
                this.selection.prop('indeterminate', true);
                // Set checked to go first unchecked after first click
                this.selection.prop('checked', true);
            }
        }
    });

    Sao.View.Tree.Row = Sao.class_(Object, {
        init: function(tree, record, pos, parent) {
            this.tree = tree;
            this.rows = [];
            this.record = record;
            this.children_field = tree.children_field;
            this.expander = null;
            var path = [];
            if (parent) {
                path = jQuery.extend([], parent.path.split('.'));
            }
            path.push(pos);
            this.path = path.join('.');
            this.el = jQuery('<tr/>');
            var td = jQuery('<td/>');
            this.el.append(td);
            this.selection = jQuery('<input/>', {
                'type': 'checkbox',
                'class': 'selection'
            });
            this.selection.change(this.selection_changed.bind(this));
            td.append(this.selection);
        },
        is_expanded: function() {
            return (this.path in this.tree.expanded);
        },
        display: function(selected) {
            selected = selected || [];
            var depth = this.path.split('.').length;
            var update_expander = function() {
                if (jQuery.isEmptyObject(
                            this.record.field_get(
                                this.children_field))) {

                    this.expander.css('background', 'none');
                }
            };
            // Use this handler to allow customization of select_row for the
            // menu
            var click_handler = function(event_) {
                this.select_row(event_);
            };
            for (var i = 0; i < this.tree.columns.length; i++) {
                var td = jQuery('<td/>');
                td.click(click_handler.bind(this));
                var table = jQuery('<table/>');
                table.css('width', '100%');
                td.append(table);
                var row = jQuery('<tr/>');
                table.append(row);
                if ((i === 0) && this.children_field) {
                    var expanded = 'ui-icon-plus';
                    if (this.is_expanded()) {
                        expanded = 'ui-icon-minus';
                    }
                    this.expander = jQuery('<span/>', {
                        'class': 'ui-icon ' + expanded
                    });
                    this.expander.html('&nbsp;');
                    this.expander.css('margin-left', (depth - 1) + 'em');
                    this.expander.css('float', 'left');
                    this.expander.click(this.toggle_row.bind(this));
                    row.append(jQuery('<td/>').append(this.expander
                                ).css('width', 1));
                    this.record.load(this.children_field).done(
                            update_expander.bind(this));
                }
                var column = this.tree.columns[i];
                var j;
                for (j = 0; j < column.prefixes.length; j++) {
                    var prefix = column.prefixes[j];
                    row.append(jQuery('<td/>').append(
                                prefix.render(this.record)).css('width', 1));
                }
                row.append(jQuery('<td/>').append(
                            column.render(this.record)));
                for (j = 0; j < column.suffixes.length; j++) {
                    var suffix = column.suffixes[j];
                    row.append(jQuery('<td/>').append(
                                suffix.render(this.record)).css('width', 1));
                }
                if (column.attributes.tree_invisible) {
                    td.hide();
                }
                this.el.append(td);
            }
            this.set_selection(~selected.indexOf(this.record));
            this.tree.tbody.append(this.el);
            if (this.is_expanded()) {
                var add_children = function() {
                    var add_row = function(record, pos, group) {
                        var tree_row = new Sao.View.Tree.Row(this.tree, record,
                                pos, this);
                        this.rows.push(tree_row);
                        tree_row.display(selected);
                    };
                    var children = this.record.field_get_client(children_field);
                    children.forEach(add_row.bind(this));
                };
                var children_field = this.children_field;
                this.record.load(this.children_field).done(
                        add_children.bind(this));
            }
            if (this.record.deleted() || this.record.removed()) {
                this.el.css('text-decoration', 'line-through');
            } else {
                this.el.css('text-decoration', 'inherit');
            }
        },
        toggle_row: function() {
            if (this.is_expanded()) {
                this.expander.removeClass('ui-icon-minus');
                this.expander.addClass('ui-icon-plus');
                delete this.tree.expanded[this.path];
            } else {
                this.expander.removeClass('ui-icon-plus');
                this.expander.addClass('ui-icon-minus');
                this.tree.expanded[this.path] = this;
            }
            this.tree.display();
        },
        select_row: function(event_) {
            if (!event_.ctrlKey) {
                this.tree.rows.forEach(function(row) {
                    if (row != this) {
                        row.set_selection(false);
                    }
                }.bind(this));
                this.selection_changed();
                if (this.is_selected()) {
                    this.tree.switch_(this.path);
                    return;
                }
            }
            this.set_selection(!this.is_selected());
            this.selection_changed();
        },
        is_selected: function() {
            return this.selection.prop('checked');
        },
        set_selection: function(value) {
            this.selection.prop('checked', value);
            if (!value) {
                this.tree.selection.prop('checked', false);
            }
        },
        selection_changed: function() {
            var is_selected = this.is_selected();
            this.set_selection(is_selected);
            if (is_selected) {
                this.tree.select_changed(this.record);
            } else {
                this.tree.select_changed(
                        this.tree.selected_records()[0] || null);
            }
            this.tree.update_selection();
        }
    });

    Sao.View.Tree.Affix = Sao.class_(Object, {
        init: function(name, attributes, protocol) {
            this.name = attributes.name || name;
            this.attributes = attributes;
            this.protocol = protocol || null;
            this.icon = attributes.icon;
            if (this.protocol && !this.icon) {
                this.icon = 'tryton-web-browser';
            }
        },
        get_cell: function() {
            var cell;
            if (this.protocol) {
                cell = jQuery('<a/>');
                cell.append(jQuery('<img/>'));
            } else if (this.icon) {
                cell = jQuery('<img/>');
            } else {
                cell = jQuery('<span/>');
            }
            cell.addClass('column-affix');
            return cell;
        },
        render: function(record) {
            var cell = this.get_cell();
            record.load(this.name).done(function() {
                var value, icon_prm;
                var field = record.model.fields[this.name];
                //TODO set_state
                if (this.icon) {
                    if (this.icon in record.model.fields) {
                        var icon_field = record.model.fields[this.icon];
                        value = icon_field.get_client(record);
                    }
                    else {
                        value = this.icon;
                    }
                    icon_prm = Sao.common.ICONFACTORY.register_icon(value);
                    icon_prm.done(function(url) {
                        var img_tag;
                        if (cell.children('img').length) {
                            img_tag = cell.children('img');
                        } else {
                            img_tag = cell;
                        }
                        img_tag.attr('src', url);
                    }.bind(this));
                } else {
                    value = this.attributes.string || '';
                    if (!value) {
                        value = field.get_client(record) || '';
                    }
                    cell.text(value);
                }
            }.bind(this));
            return cell;
        }
    });

    Sao.View.Tree.CharColumn = Sao.class_(Object, {
        class_: 'column-char',
        init: function(model, attributes) {
            this.type = 'field';
            this.model = model;
            this.field = model.fields[attributes.name];
            this.attributes = attributes;
            this.prefixes = [];
            this.suffixes = [];
        },
        get_cell: function() {
            var cell = jQuery('<div/>');
            cell.addClass(this.class_);
            return cell;
        },
        update_text: function(cell, record) {
            cell.text(this.field.get_client(record));
        },
        render: function(record) {
            var cell = this.get_cell();
            record.load(this.attributes.name).done(function() {
                this.update_text(cell, record);
                this.field.set_state(record);
                var state_attrs = this.field.get_state_attrs(record);
                if (state_attrs.invisible) {
                    cell.hide();
                } else {
                    cell.show();
                }
                // TODO editable: readonly and required
            }.bind(this));
            return cell;
        }
    });

    Sao.View.Tree.IntegerColumn = Sao.class_(Sao.View.Tree.CharColumn, {
        class_: 'column-integer',
        get_cell: function() {
            var cell = Sao.View.Tree.IntegerColumn._super.get_cell.call(this);
            cell.css('text-align', 'right');
            return cell;
        }
    });

    Sao.View.Tree.FloatColumn = Sao.class_(Sao.View.Tree.IntegerColumn, {
        class_: 'column-float'
    });

    Sao.View.Tree.BooleanColumn = Sao.class_(Sao.View.Tree.IntegerColumn, {
        class_: 'column-boolean',
        get_cell: function() {
            return jQuery('<input/>', {
                'type': 'checkbox',
                'disabled': true,
                'class': this.class_
            });
        },
        update_text: function(cell, record) {
            cell.prop('checked', this.field.get(record));
        }
    });

    Sao.View.Tree.Many2OneColumn = Sao.class_(Sao.View.Tree.CharColumn, {
        class_: 'column-many2one'
    });

    Sao.View.Tree.SelectionColumn = Sao.class_(Sao.View.Tree.CharColumn, {
        class_: 'column-selection',
        init: function(model, attributes) {
            Sao.View.Tree.SelectionColumn._super.init.call(this, model,
                attributes);
            Sao.common.selection_mixin.init.call(this);
            this.init_selection();
        },
        init_selection: function(key) {
            Sao.common.selection_mixin.init_selection.call(this, key);
        },
        update_selection: function(record, callback) {
            Sao.common.selection_mixin.update_selection.call(this, record,
                this.field, callback);
        },
        update_text: function(cell, record) {
            this.update_selection(record, function() {
                var value = this.field.get(record);
                var prm, text, found = false;
                for (var i = 0, len = this.selection.length; i < len; i++) {
                    if (this.selection[i][0] === value) {
                        found = true;
                        text = this.selection[i][1];
                        break;
                    }
                }
                if (!found) {
                    prm = Sao.common.selection_mixin.get_inactive_selection
                        .call(this, value).then(function(inactive) {
                            return inactive[1];
                        });
                } else {
                    prm = jQuery.when(text);
                }
                prm.done(function(text_value) {
                    cell.text(text_value);
                }.bind(this));
            }.bind(this));
        }
    });

    Sao.View.Tree.ReferenceColumn = Sao.class_(Sao.View.Tree.CharColumn, {
        class_: 'column-reference',
        init: function(model, attributes) {
            Sao.View.Tree.ReferenceColumn._super.init.call(this, model,
                attributes);
            Sao.common.selection_mixin.init.call(this);
            this.init_selection();
        },
        init_selection: function(key) {
            Sao.common.selection_mixin.init_selection.call(this, key);
        },
        update_text: function(cell, record) {
            var value = this.field.get_client(record);
            var model, name;
            if (!value) {
                model = '';
                name = '';
            } else {
                model = value[0];
                name = value[1];
            }
            if (model) {
                cell.text(this.selection[model] || model + ',' + name);
            } else {
                cell.text(name);
            }
        }
    });

    Sao.View.Tree.DateColumn = Sao.class_(Sao.View.Tree.CharColumn, {
        class_: 'column-date'
    });

    Sao.View.Tree.DateTimeColumn = Sao.class_(Sao.View.Tree.CharColumn, {
        class_: 'column-datetime'
    });

    Sao.View.Tree.TimeColumn = Sao.class_(Sao.View.Tree.CharColumn, {
        class_: 'column-time'
    });

    Sao.View.Tree.One2ManyColumn = Sao.class_(Sao.View.Tree.CharColumn, {
        class_: 'column-one2many',
        update_text: function(cell, record) {
            cell.text('( ' + this.field.get_client(record).length + ' )');
        }
    });

    Sao.View.Tree.Many2ManyColumn = Sao.class_(Sao.View.Tree.One2ManyColumn, {
        class_: 'column-many2many'
    });

    Sao.View.Tree.FloatTimeColumn = Sao.class_(Sao.View.Tree.CharColumn, {
        class_: 'column-float_time',
        init: function(model, attributes) {
            Sao.View.Tree.FloatTimeColumn._super.init.call(this, model,
                attributes);
            this.conv = null; // TODO
        },
        update_text: function(cell, record) {
            cell.text(Sao.common.text_to_float_time(
                    this.field.get_client(record), this.conv));
        }
    });

    Sao.View.Tree.ButtonColumn = Sao.class_(Object, {
        init: function(screen, attributes) {
            this.screen = screen;
            this.type = 'button';
            this.attributes = attributes;
        },
        render: function(record) {
            var button = new Sao.common.Button(this.attributes);
            button.el.click(record, this.button_clicked.bind(this));
            var fields = jQuery.map(this.screen.model.fields,
                function(field, name) {
                    if ((field.description.loading || 'eager') ==
                        'eager') {
                        return name;
                    } else {
                        return undefined;
                    }
                });
            // Wait at least one eager field is loaded before evaluating states
            record.load(fields[0]).done(function() {
                button.set_state(record);
            });
            return button.el;
        },
        button_clicked: function(event) {
            var record = event.data;
            if (record != this.screen.current_record) {
                return;
            }
            // TODO check state
            this.screen.button(this.attributes);
        }
    });

    Sao.View.Form = Sao.class_(Sao.View, {
        init: function(screen, xml) {
            Sao.View.Form._super.init.call(this, screen, xml);
            this.view_type = 'form';
            this.el = jQuery('<div/>', {
                'class': 'form'
            });
            this.widgets = {};
            this.widget_id = 0;
            this.state_widgets = [];
            this.containers = [];
            var root = xml.children()[0];
            var container = this.parse(screen.model, root);
            this.el.append(container.el);
        },
        parse: function(model, node, container) {
            if (container === undefined) {
                container = new Sao.View.Form.Container(
                    Number(node.getAttribute('col') || 4));
                this.containers.push(container);
            }
            var _parse = function(index, child) {
                var attributes = {};
                for (var i = 0, len = child.attributes.length; i < len; i++) {
                    var attribute = child.attributes[i];
                    attributes[attribute.name] = attribute.value;
                }
                ['readonly', 'invisible'].forEach(function(name) {
                    if (attributes[name]) {
                        attributes[name] = attributes[name] == 1;
                    }
                });
                ['yexpand', 'yfill', 'xexpand', 'xfill', 'colspan'].forEach(
                        function(name) {
                            if (attributes[name]) {
                                attributes[name] = Number(attributes[name]);
                            }
                        });
                switch (child.tagName) {
                    case 'image':
                        // TODO
                        break;
                    case 'separator':
                        this._parse_separator(
                                model, child, container, attributes);
                        break;
                    case 'label':
                        this._parse_label(model, child, container, attributes);
                        break;
                    case 'newline':
                        container.add_row();
                        break;
                    case 'button':
                        this._parse_button(child, container, attributes);
                        break;
                    case 'notebook':
                        this._parse_notebook(
                                model, child, container, attributes);
                        break;
                    case 'page':
                        this._parse_page(model, child, container, attributes);
                        break;
                    case 'field':
                        this._parse_field(model, child, container, attributes);
                        break;
                    case 'group':
                        this._parse_group(model, child, container, attributes);
                        break;
                    case 'hpaned':
                        // TODO
                        break;
                    case 'vpaned':
                        // TODO
                        break;
                    case 'child':
                        // TODO
                        break;
                }
            };
            jQuery(node).children().each(_parse.bind(this));
            return container;
        },
        _parse_separator: function(model, node, container, attributes) {
            var name = attributes.name;
            var text = attributes.string;
            if (name in model.fields) {
                if (!attributes.states && (name in model.fields)) {
                    attributes.states = model.fields[name].description.states;
                }
                if (!text) {
                    text = model.fields[name].description.string;
                }
            }
            var separator = new Sao.View.Form.Separator(text, attributes);
            this.state_widgets.push(separator);
            container.add(attributes, separator);
        },
        _parse_label: function(model, node, container, attributes) {
            var name = attributes.name;
            var text = attributes.string;
            if (attributes.xexpand === undefined) {
                attributes.xexpand = 0;
            }
            if (name in model.fields) {
                if (name == this.screen.exclude_field) {
                    container.add(attributes);
                    return;
                }
                if (!attributes.states && (name in model.fields)) {
                    attributes.states = model.fields[name].description.states;
                }
                if (!text) {
                    // TODO RTL and translation
                    text = model.fields[name]
                        .description.string + ':';
                }
                if (node.getAttribute('xalign') === undefined) {
                    node.setAttribute('xalign', 1.0);
                }
            } else if (!text) {
                // TODO get content
            }
            var label;
            if (text) {
                label = new Sao.View.Form.Label(text, attributes);
                this.state_widgets.push(label);
            }
            container.add(attributes, label);
            // TODO help
        },
        _parse_button: function(node, container, attributes) {
            var button = new Sao.common.Button(attributes);
            this.state_widgets.push(button);
            container.add(attributes, button);
            button.el.click(button, this.button_clicked.bind(this));
            // TODO help
        },
        _parse_notebook: function(model, node, container, attributes) {
            if (attributes.colspan === undefined) {
                attributes.colspan = 4;
            }
            var notebook = new Sao.View.Form.Notebook(attributes);
            this.state_widgets.push(notebook);
            container.add(attributes, notebook);
            this.parse(model, node, notebook);
        },
        _parse_page: function(model, node, container, attributes) {
            var text = attributes.string;
            if (attributes.name in model.fields) {
                // TODO check exclude
                // sync attributes
                if (!text) {
                    text = model.fields[attributes.name]
                        .description.string;
                }
            }
            if (!text) {
                text = 'No String Attr.'; // TODO translate
            }
            var page = this.parse(model, node);
            page = new Sao.View.Form.Page(container.add(page.el, text),
                    attributes);
            this.state_widgets.push(page);
        },
        _parse_field: function(model, node, container, attributes) {
            var name = attributes.name;
            if (!(name in model.fields) || name == this.screen.exclude_field) {
                container.add(attributes);
                return;
            }
            if (!attributes.widget) {
                attributes.widget = model.fields[name]
                    .description.type;
            }
            var attribute_names = ['relation', 'domain', 'selection',
                'relation_field', 'string', 'views', 'add_remove', 'sort',
                'context', 'size', 'filename', 'autocomplete', 'translate',
                'create', 'delete'];
            for (var i in attribute_names) {
                var attr = attribute_names[i];
                if ((attr in model.fields[name].description) &&
                        (node.getAttribute(attr) === null)) {
                    attributes[attr] = model.fields[name]
                        .description[attr];
                }
            }
            var WidgetFactory = Sao.View.form_widget_get(
                    attributes.widget);
            if (!WidgetFactory) {
                container.add(attributes);
                return;
            }
            var widget = new WidgetFactory(name, model, attributes);
            widget.position = this.widget_id += 1;
            widget.view = this;
            // TODO expand, fill, help, height, width
            container.add(attributes, widget);
            if (this.widgets[name] === undefined) {
                this.widgets[name] = [];
            }
            this.widgets[name].push(widget);
            this.fields[name] = true;
        },
        _parse_group: function(model, node, container, attributes) {
            var group = new Sao.View.Form.Group(attributes);
            group.add(this.parse(model, node));
            this.state_widgets.push(group);
            container.add(attributes, group);
        },
        display: function() {
            var record = this.screen.current_record;
            var field;
            var name;
            var promesses = {};
            if (record) {
                // Force to set fields in record
                // Get first the lazy one to reduce number of requests
                var fields = [];
                for (name in record.model.fields) {
                    field = record.model.fields[name];
                    fields.push([name, field.description.loading || 'eager']);
                }
                fields.sort(function(a, b) {
                    return a[1].localeCompare(b[1]);
                });
                fields.forEach(function(e) {
                    var name = e[0];
                    promesses[name] = record.load(name);
                });
            }
            var set_state = function(record, field, name) {
                var prm = jQuery.when();
                if (name in promesses) {
                    prm = promesses[name];
                }
                prm.done(function() {
                    field.set_state(record);
                });
            };
            var display = function(record, field, name) {
                return function(widget) {
                    var prm = jQuery.when();
                    if (name in promesses) {
                        prm = promesses[name];
                    }
                    prm.done(function() {
                        widget.display(record, field);
                    });
                };
            };
            for (name in this.widgets) {
                var widgets = this.widgets[name];
                field = null;
                if (record) {
                    field = record.model.fields[name];
                }
                if (field) {
                    set_state(record, field, name);
                }
                widgets.forEach(display(record, field, name));
            }
            jQuery.when.apply(jQuery,
                    jQuery.map(promesses, function(p) {
                        return p;
                    })
                ).done(function() {
                    var j;
                    for (j in this.state_widgets) {
                        var state_widget = this.state_widgets[j];
                        state_widget.set_state(record);
                    }
                    for (j in this.containers) {
                        var container = this.containers[j];
                        container.resize();
                    }
                }.bind(this));
        },
        set_value: function() {
            var record = this.screen.current_record;
            if (record) {
                var set_value = function(widget) {
                    widget.set_value(record, this);
                };
                for (var name in this.widgets) {
                    if (name in record.model.fields) {
                        var widgets = this.widgets[name];
                        var field = record.model.fields[name];
                        widgets.forEach(set_value, field);
                    }
                }
            }
        },
        button_clicked: function(event) {
            var button = event.data;
            var record = this.screen.current_record;
            var fields = Object.keys(this.fields);
            record.validate(fields).then(function(validate) {
                if (!validate) {
                    this.screen.display();
                    return;
                } else {
                    this.screen.button(button.attributes);
                }
            }.bind(this));
        },
        selected_records: function() {
            if (this.screen.current_record) {
                return [this.screen.current_record];
            }
            return [];
        }
    });

    Sao.View.Form.Container = Sao.class_(Object, {
        init: function(col) {
            if (col === undefined) col = 4;
            this.col = col;
            this.el = jQuery('<table/>', {
                'class': 'form-container'
            });
            this.add_row();
        },
        add_row: function() {
            this.el.append(jQuery('<tr/>'));
        },
        rows: function() {
            return this.el.children().children('tr');
        },
        row: function() {
            return this.rows().last();
        },
        add: function(attributes, widget) {
            var colspan = attributes.colspan;
            if (colspan === undefined) colspan = 1;
            var xfill = attributes.xfill;
            if (xfill === undefined) xfill = 1;
            var xexpand = attributes.xexpand;
            if (xexpand === undefined) xexpand = 1;
            var len = 0;
            var row = this.row();
            row.children().map(function(i, e) {
                len += Number(jQuery(e).attr('colspan') || 1);
            });
            if (len + colspan > this.col) {
                this.add_row();
                row = this.row();
            }
            var el;
            if (widget) {
                el = widget.el;
            }
            var cell = jQuery('<td/>', {
                'colspan': colspan,
                'class': widget ? widget.class_ || '' : ''
            }).append(el);
            if (xexpand) {
                cell.addClass('xexpand');
                cell.css('width', '100%');
            }
            if (xfill) {
                cell.addClass('xfill');
                if (xexpand && el) {
                    el.css('width', '100%');
                }
            }
            row.append(cell);
        },
        resize: function() {
            var rows = this.rows();
            var widths = [];
            var col = this.col;
            var has_expand = false;
            rows.map(function() {
                var row = jQuery(this);
                var xexpands = [];
                row.children().map(function(i) {
                    var cell = jQuery(this);
                    if (cell.hasClass('xexpand') &&
                        (cell.children().css('display') != 'none')) {
                        xexpands.push(cell);
                        has_expand = true;
                    }
                });
                var width = 100 / xexpands.length;
                for (var i = 0; i < col; i++) {
                    if (!widths[i]) {
                        widths[i] = width;
                    } else {
                        widths[i] = Math.min(widths[i], width);
                    }
                }
            });
            rows.map(function() {
                var row = jQuery(this);
                row.children().map(function(i) {
                    var cell = jQuery(this);
                    if (cell.hasClass('xexpand') &&
                        (cell.children().css('display') != 'none')) {
                        cell.css('width', widths[i] + '%');
                    }
                    if (cell.children().css('display') == 'none') {
                        cell.hide();
                    } else {
                        cell.show();
                    }
                });
            });
            if (has_expand) {
                this.el.css('width', '100%');
            } else {
                this.el.css('width', '');
            }
        }
    });

    var StateWidget = Sao.class_(Object, {
        init: function(attributes) {
            this.attributes = attributes;
        },
        set_state: function(record) {
            var state_changes;
            if (record) {
                state_changes = record.expr_eval(this.attributes.states || {});
            } else {
                state_changes = {};
            }
            var invisible = state_changes.invisible;
            if (invisible === undefined) {
                invisible = this.attributes.invisible;
            }
            if (invisible) {
                this.hide();
            } else {
                this.show();
            }
        },
        show: function() {
            this.el.show();
        },
        hide: function() {
            this.el.hide();
        }
    });

    Sao.View.Form.Separator = Sao.class_(StateWidget, {
        init: function(text, attributes) {
            Sao.View.Form.Separator._super.init.call(this, attributes);
            this.el = jQuery('<div/>', {
                'class': 'form-separator'
            });
            if (text) {
                this.el.append(jQuery('<p/>', {
                    'text': text
                }));
            }
            this.el.append(jQuery('<hr/>'));
        }
    });

    Sao.View.Form.Label = Sao.class_(StateWidget, {
        class_: 'form-label',
        init: function(text, attributes) {
            Sao.View.Form.Label._super.init.call(this, attributes);
            this.el = jQuery('<label/>', {
                text: text,
                'class': this.class_
            });
        },
        set_state: function(record) {
            Sao.View.Form.Label._super.set_state.call(this, record);
            if ((this.attributes.string === undefined) &&
                    this.attributes.name) {
                var text = '';
                if (record) {
                    text = record.field_get_client(this.attributes.name) || '';
                }
                this.el.val(text);
            }
        }
    });

    Sao.View.Form.Notebook = Sao.class_(StateWidget, {
        class_: 'form-notebook',
        init: function(attributes) {
            Sao.View.Form.Notebook._super.init.call(this, attributes);
            this.el = jQuery('<div/>', {
                'class': this.class_
            });
            this.el.append(jQuery('<ul/>'));
            this.el.tabs();
            this.selected = false;
            this.counter = 0;
        },
        add: function(tab, text) {
            var tab_id = '#tab-form-' + this.counter++;
            this.el.tabs('add', tab_id, text);
            this.el.children(tab_id).html(tab);
            if (!this.selected) {
                this.el.tabs('select', tab_id);
                this.selected = true;
            }
            return jQuery('> ul li', this.el).last();
        }
    });

    Sao.View.Form.Page = Sao.class_(StateWidget, {
        init: function(el, attributes) {
            Sao.View.Form.Page._super.init.call(this, attributes);
            this.el = el;
        }
    });

    Sao.View.Form.Group = Sao.class_(StateWidget, {
        class_: 'form-group',
        init: function(attributes) {
            Sao.View.Form.Group._super.init.call(this, attributes);
            this.el = jQuery('<div/>', {
                'class': this.class_
            });
        },
        add: function(widget) {
            this.el.append(widget.el);
        }
    });

    Sao.View.form_widget_get = function(type) {
        switch (type) {
            case 'char':
                return Sao.View.Form.Char;
            case 'sha':
                return Sao.View.Form.Sha;
            case 'date':
                return Sao.View.Form.Date;
            case 'datetime':
                return Sao.View.Form.DateTime;
            case 'integer':
            case 'biginteger':
                return Sao.View.Form.Integer;
            case 'float':
            case 'numeric':
                return Sao.View.Form.Float;
            case 'selection':
                return Sao.View.Form.Selection;
            case 'float_time':
                return Sao.View.Form.FloatTime;
            case 'boolean':
                return Sao.View.Form.Boolean;
            case 'text':
                return Sao.View.Form.Text;
            case 'many2one':
                return Sao.View.Form.Many2One;
            case 'reference':
                return Sao.View.Form.Reference;
            case 'one2many':
                return Sao.View.Form.One2Many;
            case 'many2many':
                return Sao.View.Form.Many2Many;
            case 'binary':
                return Sao.View.Form.Binary;
        }
    };


    Sao.View.Form.Widget = Sao.class_(Object, {
        init: function(field_name, model, attributes) {
            this.field_name = field_name;
            this.model = model;
            this.view = null;  // Filled later
            this.attributes = attributes;
            this.el = null;
            this.position = 0;
            this.visible = true;
        },
        display: function(record, field) {
            var readonly = this.attributes.readonly;
            var invisible = this.attributes.invisible;
            if (!field) {
                if (readonly === undefined) {
                    readonly = true;
                }
                if (invisible === undefined) {
                    invisible = false;
                }
                this.set_readonly(readonly);
                this.set_invisible(invisible);
                return;
            }
            var state_attrs = field.get_state_attrs(record);
            if (readonly === undefined) {
                readonly = state_attrs.readonly;
                if (readonly === undefined) {
                    readonly = false;
                }
            }
            this.set_readonly(readonly);
            var valid = true;
            if (state_attrs.valid !== undefined) {
                valid = state_attrs.valid;
            }
            // XXX allow to customize colors
            var color = 'inherit';
            if (readonly) {
            } else if (!valid) {
                color = 'red';
            } else if (state_attrs.required) {
                color = 'lightblue';
            }
            this.set_color(color);
            if (invisible === undefined) {
                invisible = field.get_state_attrs(record).invisible;
                if (invisible === undefined) {
                    invisible = false;
                }
            }
            this.set_invisible(invisible);
        },
        record: function() {
            if (this.view && this.view.screen) {
                return this.view.screen.current_record;
            }
        },
        field: function() {
            var record = this.record();
            if (record) {
                return record.model.fields[this.field_name];
            }
        },
        focus_out: function() {
            if (!this.field()) {
                return;
            }
            if (!this.visible) {
                return;
            }
            this.set_value(this.record(), this.field());
        },
        set_value: function(record, field) {
        },
        set_readonly: function(readonly) {
            this.el.prop('disabled', readonly);
        },
        _get_color_el: function() {
            return this.el;
        },
        set_color: function(color) {
            var el = this._get_color_el();
            el.css('background-color', color);
        },
        set_invisible: function(invisible) {
            this.visible = !invisible;
            if (invisible) {
                this.el.hide();
            } else {
                this.el.show();
            }
        }
    });

    Sao.View.Form.Char = Sao.class_(Sao.View.Form.Widget, {
        class_: 'form-char',
        init: function(field_name, model, attributes) {
            Sao.View.Form.Char._super.init.call(this, field_name, model,
                attributes);
            this.el = jQuery('<input/>', {
                'type': 'input',
                'class': this.class_
            });
            this.el.change(this.focus_out.bind(this));
        },
        display: function(record, field) {
            Sao.View.Form.Char._super.display.call(this, record, field);
            if (record) {
                var value = record.field_get_client(this.field_name);
                this.el.val(value || '');
            } else {
                this.el.val('');
            }
        },
        set_value: function(record, field) {
            field.set_client(record, this.el.val());
        }
    });

    Sao.View.Form.Sha = Sao.class_(Sao.View.Form.Char, {
        class_: 'form-sha',
        init: function(field_name, model, attributes) {
            Sao.View.Form.Sha._super.init.call(this, field_name, model,
                attributes);
            this.el.prop('type', 'password');
        }
    });

    Sao.View.Form.Date = Sao.class_(Sao.View.Form.Widget, {
        class_: 'form-date',
        init: function(field_name, model, attributes) {
            Sao.View.Form.Date._super.init.call(this, field_name, model,
                attributes);
            this.el = jQuery('<div/>', {
                'class': this.class_
            });
            this.date = jQuery('<input/>', {
                'type': 'input'
            });
            this.el.append(this.date);
            this.date.datepicker({
                showOn: 'button'
            });
            this.date.change(this.focus_out.bind(this));
            this._set_button();
        },
        _get_color_el: function() {
            return this.date;
        },
        get_format: function(record, field) {
            return Sao.common.date_format();
        },
        _set_button: function() {
            this.date.next('button').text('').button({
                icons: {
                    primary: 'ui-icon-calendar'
                },
                text: false
            });
        },
        display: function(record, field) {
            if (record && field) {
                this.date.datepicker('option', 'dateFormat',
                        this.get_format(record, field));
                // Button must be set after changing any option
                this._set_button();
            }
            Sao.View.Form.Date._super.display.call(this, record, field);
            if (record) {
                this.date.val(record.field_get_client(this.field_name));
            }
        },
        set_value: function(record, field) {
            field.set_client(record, this.date.val());
        }
    });

    Sao.View.Form.DateTime = Sao.class_(Sao.View.Form.Date, {
        init: function(field_name, model, attributes) {
            Sao.View.Form.DateTime._super.init.call(this, field_name, model,
                attributes);
            this.date.datepicker('option', 'beforeShow', function() {
                var time = ' ' + Sao.common.format_time(
                    this.field().time_format(this.record()),
                    this._get_time());
                this.date.datepicker('option', 'dateFormat',
                    Sao.common.date_format() + time);
                // Button must be set after changing any option
                this._set_button();
                this.date.prop('disabled', true);
            }.bind(this));
            this.date.datepicker('option', 'onClose', function() {
                this.date.prop('disabled', false);
            }.bind(this));
            // Button must be set after changing any option
            this._set_button();
        },
        _get_time: function() {
            return Sao.common.parse_datetime(Sao.common.date_format(),
                this.field().time_format(this.record()), this.date.val());
        },
        get_format: function(record, field) {
            var time = '';
            if (record) {
                var value = record.field_get(this.field_name);
                time = ' ' + Sao.common.format_time(field.time_format(record),
                    value);
            }
            return Sao.common.date_format() + time;
        }
    });

    Sao.View.Form.Time = Sao.class_(Sao.View.Form.Char, {
        class_: 'form-time'
    });

    Sao.View.Form.Integer = Sao.class_(Sao.View.Form.Char, {
        class_: 'form-integer',
        init: function(field_name, model, attributes) {
            Sao.View.Form.Integer._super.init.call(this, field_name, model,
                attributes);
            this.el.css('text-align', 'right');
        },
        set_value: function(record, field) {
            field.set_client(record, this.el.val());
        }
    });

    Sao.View.Form.Float = Sao.class_(Sao.View.Form.Integer, {
        class_: 'form-float'
    });

    Sao.View.Form.Selection = Sao.class_(Sao.View.Form.Widget, {
        class_: 'form-selection',
        init: function(field_name, model, attributes) {
            Sao.View.Form.Selection._super.init.call(this, field_name, model,
                attributes);
            this.el = jQuery('<select/>', {
                'class': this.class_
            });
            this.el.change(this.focus_out.bind(this));
            Sao.common.selection_mixin.init.call(this);
            this.init_selection();
        },
        init_selection: function(key) {
            Sao.common.selection_mixin.init_selection.call(this, key,
                this.set_selection.bind(this));
        },
        update_selection: function(record, field, callbak) {
            Sao.common.selection_mixin.update_selection.call(this, record,
                field, function(selection) {
                    this.set_selection(selection);
                    if (callbak) {
                        callbak();
                    }
                }.bind(this));
        },
        set_selection: function(selection) {
            var select = this.el;
            select.empty();
            selection.forEach(function(e) {
                select.append(jQuery('<option/>', {
                    'value': e[0],
                    'text': e[1]
                }));
            });
        },
        display: function(record, field) {
            Sao.View.Form.Selection._super.display.call(this, record, field);
            this.update_selection(record, field, function() {
                if (!field) {
                    this.el.val('');
                    return;
                }
                var value = field.get(record);
                var prm, found = false;
                for (var i = 0, len = this.selection.length; i < len; i++) {
                    if (this.selection[i][0] === value) {
                        found = true;
                        break;
                    }
                }
                if (!found) {
                    prm = Sao.common.selection_mixin.get_inactive_selection
                        .call(this, value);
                    prm.done(function(inactive) {
                        this.el.append(jQuery('<option/>', {
                            value: inactive[0],
                            text: inactive[1],
                            disabled: true
                        }));
                    }.bind(this));
                } else {
                    prm = jQuery.when();
                }
                prm.done(function() {
                    if (value === null) {
                        value = '';
                    }
                    this.el.val('' + value);
                }.bind(this));
            }.bind(this));
        },
        value_get: function() {
            var val = this.el.val();
            if ('relation' in this.attributes) {
                if (val === '') {
                    return null;
                } else if (val === null) {
                    // The selected value is disabled
                    val = this.el.find(':selected').attr('value');
                }
                return parseInt(val, 10);
            }
            return val;
        },
        set_value: function(record, field) {
            var value = this.value_get();
            field.set_client(record, value);
        }
    });

    Sao.View.Form.FloatTime = Sao.class_(Sao.View.Form.Char, {
        class_: 'form-float-time',
        init: function(field_name, model, attributes) {
            Sao.View.Form.FloatTime._super.init.call(this, field_name, model,
                attributes);
            this.el.css('text-align', 'right');
            this.conv = null; // TODO
        },
        display: function(record, field) {
            Sao.View.Form.FloatTime._super.display.call(this, record, field);
            if (record) {
                var value = record.field_get_client(this.field_name);
                this.el.val(Sao.common.text_to_float_time(value, this.conv));
            } else {
                this.el.val('');
            }
        }
    });

    Sao.View.Form.Boolean = Sao.class_(Sao.View.Form.Widget, {
        class_: 'form-boolean',
        init: function(field_name, model, attributes) {
            Sao.View.Form.Boolean._super.init.call(this, field_name, model,
                attributes);
            this.el = jQuery('<input/>', {
                'type': 'checkbox',
                'class': this.class_
            });
            this.el.change(this.focus_out.bind(this));
        },
        display: function(record, field) {
            Sao.View.Form.Boolean._super.display.call(this, record, field);
            if (record) {
                this.el.prop('checked', record.field_get(this.field_name));
            } else {
                this.el.prop('checked', false);
            }
        },
        set_value: function(record, field) {
            var value = this.el.prop('checked');
            field.set_client(record, value);
        }
    });

    Sao.View.Form.Text = Sao.class_(Sao.View.Form.Widget, {
        class_: 'form-text',
        init: function(field_name, model, attributes) {
            Sao.View.Form.Text._super.init.call(this, field_name, model,
                attributes);
            this.el = jQuery('<textarea/>', {
                'class': this.class_
            });
            this.el.change(this.focus_out.bind(this));
        },
        display: function(record, field) {
            Sao.View.Form.Text._super.display.call(this, record, field);
            if (record) {
                var value = record.field_get_client(this.field_name);
                this.el.val(value);
            } else {
                this.el.val('');
            }
        },
        set_value: function(record, field) {
            var value = this.el.val() || '';
            field.set_client(record, value);
        }
    });

    Sao.View.Form.Many2One = Sao.class_(Sao.View.Form.Widget, {
        class_: 'form-many2one',
        init: function(field_name, model, attributes) {
            Sao.View.Form.Many2One._super.init.call(this, field_name, model,
                attributes);
            this.el = jQuery('<div/>', {
                'class': this.class_
            });
            this.entry = jQuery('<input/>', {
                'type': 'input'
            });
            this.entry.on('keyup', this.key_press.bind(this));
            this.el.append(jQuery('<div/>').append(this.entry));
            this.but_open = jQuery('<button/>').button({
                'icons': {
                    'primary': 'ui-icon-search'
                },
                'text': false
            });
            this.but_open.click(this.edit.bind(this));
            this.el.prepend(this.but_open);
            this.but_new = jQuery('<button/>').button({
                'icons': {
                    'primary': 'ui-icon-document'
                },
                'text': false
            });
            this.but_new.click(this.new_.bind(this));
            this.el.prepend(this.but_new);
            // TODO autocompletion
        },
        _get_color_el: function() {
            return this.entry;
        },
        get_screen: function() {
            var domain = this.field().get_domain(this.record());
            var context = this.field().get_context(this.record());
            return new Sao.Screen(this.get_model(), {
                'context': context,
                'domain': domain,
                'mode': ['form'],
                'view_ids': (this.attributes.view_ids || '').split(','),
                'views_preload': this.attributes.views
            });
        },
        set_text: function(value) {
            if (jQuery.isEmptyObject(value)) {
                value = '';
            }
            this.entry.val(value);
        },
        display: function(record, field) {
            var text_value, value;
            Sao.View.Form.Many2One._super.display.call(this, record, field);

            this._set_button_sensitive();

            if (!record) {
                this.entry.val('');
                return;
            }
            this.set_text(field.get_client(record));
            value = field.get(record);
            if (this.has_target(value)) {
                this.but_open.button({
                    'icons': {
                        'primary': 'ui-icon-folder-open'
                    }});
            } else {
                this.but_open.button({
                    'icons': {
                        'primary': 'ui-icon-search'
                    }});
            }
        },
        set_readonly: function(readonly) {
            this.entry.prop('disabled', readonly);
            this._set_button_sensitive();
        },
        _set_button_sensitive: function() {
            var model = this.get_model();
            var access = {
                create: true,
                read: true
            };
            if (model) {
                access = Sao.common.MODELACCESS.get(model);
            }
            var readonly = this.entry.prop('disabled');
            var create = this.attributes.create;
            if (create === undefined) {
                create = true;
            }
            this.but_new.prop('disabled', readonly || !create || !access.create);
            this.but_open.prop('disabled', !access.read);
        },
        id_from_value: function(value) {
            return value;
        },
        value_from_id: function(id, str) {
            if (str === undefined) {
                str = '';
            }
            return [id, str];
        },
        get_model: function() {
            return this.attributes.relation;
        },
        has_target: function(value) {
            return value !== undefined && value !== null;
        },
        edit: function(evt) {
            var model = this.get_model();
            if (!model || !Sao.common.MODELACCESS.get(model).read) {
                return;
            }
            var win;
            var record = this.record();
            var value = record.field_get(this.field_name);
            if (model && this.has_target(value)) {
                var screen = this.get_screen();
                var m2o_id =
                    this.id_from_value(record.field_get(this.field_name));
                screen.new_group([m2o_id]);
                var callback = function(result) {
                    if (result) {
                        var rec_name_prm = screen.current_record.rec_name();
                        rec_name_prm.done(function(name) {
                            var value = this.value_from_id(
                                screen.current_record.id, name);
                            this.record().field_set_client(this.field_name,
                                value, true);
                        }.bind(this));
                    }
                };
                win = new Sao.Window.Form(screen, callback.bind(this), {
                    save_current: true
                });
            } else if (model) {
                var dom;
                var domain = this.field().get_domain(record);
                var context = this.field().get_context(record);
                var text = this.entry.val();
                if (text) {
                    dom = [['rec_name', 'ilike', '%' + text + '%'], domain];
                } else {
                    dom = domain;
                }
                var sao_model = new Sao.Model(model);
                var ids_prm = sao_model.execute('search',
                        [dom, 0, Sao.config.limit, null], context);
                ids_prm.done(function(ids) {
                    if (ids.length == 1) {
                        this.record().field_set_client(this.field_name,
                            this.id_from_value(ids[0]), true);
                        return;
                    }
                    var callback = function(result) {
                        if (!jQuery.isEmptyObject(result)) {
                            var value = this.value_from_id(result[0][0],
                                result[0][1]);
                            this.record().field_set_client(this.field_name,
                                value, true);
                        }
                    };
                    win = new Sao.Window.Search(model,
                        callback.bind(this), {
                            sel_multi: false,
                            ids: ids,
                            context: context,
                            domain: domain,
                            view_ids: (this.attributes.view_ids ||
                                '').split(','),
                            views_preload: (this.attributes.views || {}),
                            new_: !this.but_new.prop('disabled')
                    });
                }.bind(this));
            }
        },
        new_: function(evt) {
            var model = this.get_model();
            if (!model || ! Sao.common.MODELACCESS.get(model).create) {
                return;
            }
            var screen = this.get_screen();
            var callback = function(result) {
                if (result) {
                    var rec_name_prm = screen.current_record.rec_name();
                    rec_name_prm.done(function(name) {
                        var value = this.value_from_id(
                            screen.current_record.id, name);
                        this.record().field_set_client(this.field_name, value);
                    }.bind(this));
                }
            };
            var win = new Sao.Window.Form(screen, callback.bind(this), {
                new_: true,
                save_current: true
            });
        },
        key_press: function(event_) {
            var editable = true; // TODO compute editable
            var activate_keys = [Sao.common.TAB_KEYCODE];
            var delete_keys = [Sao.common.BACKSPACE_KEYCODE,
                Sao.common.DELETE_KEYCODE];
            if (!this.wid_completion) {
                activate_keys.push(Sao.common.RETURN_KEYCODE);
            }

            if (event_.which == Sao.common.F3_KEYCODE && editable) {
                this.new_();
                event_.preventDefault();
            } else if (event_.which == Sao.common.F2_KEYCODE) {
                this.edit();
                event_.preventDefault();
            } else if (~activate_keys.indexOf(event_.which)) {
                this.activate();
            } else if (this.has_target(this.record().field_get(
                            this.field_name)) && editable) {
                var value = this.record().field_get_client(this.field_name);
                if ((value != this.entry.val()) ||
                        ~delete_keys.indexOf(event_.which)) {
                    this.entry.val('');
                    this.record().field_set_client(this.field_name,
                        this.value_from_id(null, ''));
                }
            }
        },
        activate: function() {
            var model = this.get_model();
            if (!model || !Sao.common.MODELACCESS.get(model).read) {
                return;
            }
            var record = this.record();
            var value = record.field_get(this.field_name);
            var sao_model = new Sao.Model(model);

            if (model && !this.has_target(value)) {
                var text = this.entry.val();
                if (!this._readonly && (text ||
                            this.field().get_state_attrs(this.record())
                            .required)) {
                    var dom;
                    var domain = this.field().get_domain(record);
                    var context = this.field().get_context(record);

                    if (text) {
                        dom = [['rec_name', 'ilike', '%' + text + '%'], domain];
                    } else {
                        dom = domain;
                    }
                    var ids_prm = sao_model.execute('search',
                            [dom, 0, Sao.config.limit, null], context);
                    ids_prm.done(function(ids) {
                        if (ids.length == 1) {
                            Sao.rpc({
                                'method': 'model.' + model + '.read',
                                'params': [[this.id_from_value(ids[0])],
                                ['rec_name'], context]
                            }, this.record().model.session
                            ).then(function(values) {
                                this.record().field_set_client(this.field_name,
                                    this.value_from_id(ids[0],
                                        values[0].rec_name), true);
                            }.bind(this));
                            return;
                        }
                        var callback = function(result) {
                            if (!jQuery.isEmptyObject(result)) {
                                var value = this.value_from_id(result[0][0],
                                    result[0][1]);
                                this.record().field_set_client(this.field_name,
                                    value, true);
                            } else {
                                this.entry.val('');
                            }
                        };
                        var win = new Sao.Window.Search(model,
                                callback.bind(this), {
                                    sel_multi: false,
                                    ids: ids,
                                    context: context,
                                    domain: domain,
                                    view_ids: (this.attributes.view_ids ||
                                        '').split(','),
                                    views_preload: (this.attributes.views ||
                                        {}),
                                    new_: false
                                    // TODO compute from but_new status
                                });
                    }.bind(this));
                }
            }
        }
    });

    Sao.View.Form.Reference = Sao.class_(Sao.View.Form.Many2One, {
        init: function(field_name, model, attributes) {
            Sao.View.Form.Reference._super.init.call(this, field_name, model,
                attributes);
            this.select = jQuery('<select/>');
            this.el.prepend('-');
            this.el.prepend(this.select);
            this.select.change(this.select_changed.bind(this));
            Sao.common.selection_mixin.init.call(this);
            this.init_selection();
        },
        init_selection: function(key) {
            Sao.common.selection_mixin.init_selection.call(this, key,
                this.set_selection.bind(this));
        },
        update_selection: function(record, field, callback) {
            Sao.common.selection_mixin.update_selection.call(this, record,
                field, function(selection) {
                    this.set_selection(selection);
                    if (callback) {
                        callback();
                    }
                }.bind(this));
        },
        set_selection: function(selection) {
            var select = this.select;
            select.empty();
            selection.forEach(function(e) {
                select.append(jQuery('<option/>', {
                    'value': e[0],
                    'text': e[1]
                }));
            });
        },
        id_from_value: function(value) {
            return parseInt(value.split(',')[1], 10);
        },
        value_from_id: function(id, str) {
            if (!str) {
                str = '';
            }
            return [this.get_model(), [id, str]];
        },
        get_model: function() {
            return this.select.val();
        },
        has_target: function(value) {
            if (value === null) {
                return false;
            }
            var model = value.split(',')[0];
            value = value.split(',')[1];
            if (jQuery.isEmptyObject(value)) {
                value = null;
            } else {
                value = parseInt(value, 10);
                if (isNaN(value)) {
                    value = null;
                }
            }
            return (model == this.get_model()) && (value >= 0);
        },
        _set_button_sensitive: function() {
            Sao.View.Form.Reference._super._set_button_sensitive.call(this);
            this.select.prop('disabled', this.entry.prop('disabled'));
        },
        select_changed: function() {
            this.entry.val('');
            var model = this.get_model();
            var value;
            if (model) {
                value = [model, [-1, '']];
            } else {
                value = ['', ''];
            }
            this.record().field_set_client(this.field_name, value);
        },
        set_value: function(record, field) {
            var value;
            if (!this.get_model()) {
                value = this.entry.val();
                if (jQuery.isEmptyObject(value)) {
                    field.set_client(record, this.field_name, null);
                } else {
                    field.set_client(record, this.field_name, ['', value]);
                }
            } else {
                value = field.get_client(record, this.field_name);
                var model, name;
                if (value instanceof Array) {
                    model = value[0];
                    name = value[1];
                } else {
                    model = '';
                    name = '';
                }
                if ((model != this.get_model()) ||
                        (name != this.entry.val())) {
                    field.set_client(record, this.field_name, null);
                    this.entry.val('');
                }
            }
        },
        set_text: function(value) {
            var model;
            if (value) {
                model = value[0];
                value = value[1];
            } else {
                model = null;
                value = null;
            }
            Sao.View.Form.Reference._super.set_text.call(this, value);
            if (model) {
                this.select.val(model);
            } else {
                this.select.val('');
            }
        },
        display: function(record, field) {
            this.update_selection(record, field, function() {
                Sao.View.Form.Reference._super.display.call(this, record, field);
            }.bind(this));
        }
    });

    Sao.View.Form.One2Many = Sao.class_(Sao.View.Form.Widget, {
        class_: 'form-one2many',
        init: function(field_name, model, attributes) {
            Sao.View.Form.One2Many._super.init.call(this, field_name, model,
                attributes);

            this._readonly = true;

            this.el = jQuery('<div/>', {
                'class': this.class_
            });
            this.menu = jQuery('<div/>', {
                'class': this.class_ + '-menu'
            });
            this.el.append(this.menu);

            var label = jQuery('<span/>', {
                'class': this.class_ + '-string',
                text: attributes.string
            });
            this.menu.append(label);

            var toolbar = jQuery('<span/>', {
                'class': this.class_ + '-toolbar'
            });
            this.menu.append(toolbar);

            if (attributes.add_remove) {
                this.wid_text = jQuery('<input/>', {
                    type: 'input'
                });
                // TODO add completion
                toolbar.append(this.wid_text);

                this.but_add = jQuery('<button/>').button({
                    icons: {
                        primary: 'ui-icon-plus'
                    },
                    label: 'Add',
                    text: false
                });
                this.but_add.click(this.add.bind(this));
                toolbar.append(this.but_add);

                this.but_remove = jQuery('<button/>').button({
                    icons: {
                        primary: 'ui-icon-minus'
                    },
                    label: 'Remove',
                    text: false
                });
                this.but_remove.click(this.remove.bind(this));
                toolbar.append(this.but_remove);
            }

            this.but_new = jQuery('<button/>').button({
                icons: {
                    primary: 'ui-icon-document'
                },
                label: 'New',
                text: false
            });
            this.but_new.click(this.new_.bind(this));
            toolbar.append(this.but_new);

            this.but_open = jQuery('<button/>').button({
                icons: {
                    primary: 'ui-icon-folder-open'
                },
                label: 'Open',
                text: false
            });
            this.but_open.click(this.open.bind(this));
            toolbar.append(this.but_open);

            this.but_del = jQuery('<button/>').button({
                icons: {
                    primary: 'ui-icon-trash'
                },
                label: 'Delete',
                text: false
            });
            this.but_del.click(this.delete_.bind(this));
            toolbar.append(this.but_del);

            this.but_undel = jQuery('<button/>').button({
                icons: {
                    primary: 'ui-icon-arrowreturn-1-s'
                },
                label: 'Undelete',
                text: false
            });
            this.but_undel.click(this.undelete.bind(this));
            toolbar.append(this.but_undel);

            this.but_previous = jQuery('<button/>').button({
                icons: {
                    primary: 'ui-icon-arrowthick-1-w'
                },
                label: 'Previous',
                text: false
            });
            this.but_previous.click(this.previous.bind(this));
            toolbar.append(this.but_previous);

            this.label = jQuery('<span/>', {
                'class': this.class_ + '-label'
            });
            this.label.text('(0, 0)');
            toolbar.append(this.label);

            this.but_next = jQuery('<button/>').button({
                icons: {
                    primary: 'ui-icon-arrowthick-1-e'
                },
                label: 'Next',
                text: false
            });
            this.but_next.click(this.next.bind(this));
            toolbar.append(this.but_next);

            this.but_switch = jQuery('<button/>').button({
                icons: {
                    primary: 'ui-icon-arrow-4-diag'
                },
                label: 'Switch',
                text: false
            });
            this.but_switch.click(this.switch_.bind(this));
            toolbar.append(this.but_switch);

            this.content = jQuery('<div/>', {
                'class': this.class_ + '-content'
            });
            this.el.append(this.content);

            var modes = (attributes.mode || 'tree,form').split(',');
            this.screen = new Sao.Screen(attributes.relation, {
                mode: modes,
                view_ids: (attributes.view_ids || '').split(','),
                views_preload: attributes.views || {},
                row_activate: this.activate.bind(this),
                exclude_field: attributes.relation_field || null
            });
            this.prm = this.screen.switch_view(modes[0]).done(function() {
                this.content.append(this.screen.screen_container.el);
            }.bind(this));
            // TODO sensitivity of buttons
        },
        _get_color_el: function() {
            if (this.screen.current_view &&
                    (this.screen.current_view.view_type == 'tree') &&
                    this.screen.current_view.el) {
                return this.screen.current_view.el;
            }
            return Sao.View.Form.One2Many._super._get_color_el.call(this);
        },
        set_readonly: function(readonly) {
            this._readonly = readonly;
            this._set_button_sensitive();
        },
        _set_button_sensitive: function() {
            var access = Sao.common.MODELACCESS.get(this.screen.model_name);
            var size_limit = false;
            if (this.record() && this.field()) {
                // TODO
            }
            var create = this.attributes.create;
            if (create === undefined) {
                create = true;
            }
            this.but_new.prop('disabled', this._readonly || !create ||
                    size_limit || !access.create);

            var delete_ = this.attributes['delete'];
            if (delete_ === undefined) {
                delete_ = true;
            }
            // TODO position
            this.but_del.prop('disabled', this._readonly || !delete_ ||
                    !access['delete']);
            this.but_undel.prop('disabled', this._readonly || size_limit);
            this.but_open.prop('disabled', !access.read);
            // TODO but_next, but_previous
            if (this.attributes.add_remove) {
                this.wid_text.prop('disabled', this._readonly);
                this.but_add.prop('disabled', this._readonly || size_limit ||
                        !access.write || !access.read);
                this.but_remove.prop('disabled', this._readonly ||
                        !access.write || !access.read);
            }
        },
        display: function(record, field) {
            Sao.View.Form.One2Many._super.display.call(this, record, field);

            this._set_button_sensitive();

            this.prm.done(function() {
                if (!record) {
                    return;
                }
                if (field === undefined) {
                    this.screen.new_group();
                    this.screen.set_current_record(null);
                    this.screen.parent = true;
                    this.screen.display();
                    return;
                }

                var new_group = record.field_get_client(this.field_name);
                if (new_group != this.screen.group) {
                    this.screen.set_group(new_group);
                    // TODO handle editable tree
                    // TODO set readonly, domain, size_limit
                }
                this.screen.display();
            }.bind(this));
        },
        activate: function(event_) {
            this.edit();
        },
        add: function(event_) {
            var access = Sao.common.MODELACCESS.get(this.screen.model_name);
            if (!access.write || !access.read) {
                return;
            }
            // TODO
        },
        remove: function(event_) {
            var access = Sao.common.MODELACCESS.get(this.screen.model_name);
            if (!access.write || !access.read) {
                return;
            }
            this.screen.remove(false, true, false);
        },
        new_: function(event_) {
            if (!Sao.common.MODELACCESS.get(this.screen.model_name).create) {
                return;
            }
            this.validate().done(function() {
                var context = jQuery.extend({},
                        this.field().get_context(this.record()));
                // TODO sequence
                if (this.screen.current_view.type == 'form' ||
                        this.screen.current_view.editable) {
                    this.screen.new_();
                    this.screen.current_view.el.prop('disabled', false);
                } else {
                    var record = this.record();
                    var field_size = record.expr_eval(
                        this.attributes.size) || -1;
                    field_size -= this.field().get_eval(record);
                    var win = new Sao.Window.Form(this.screen, function() {}, {
                        new_: true,
                        many: field_size,
                        context: context
                    });
                }
            }.bind(this));
        },
        open: function(event_) {
            this.edit();
        },
        delete_: function(event_) {
            if (!Sao.common.MODELACCESS.get(this.screen.model_name)['delete']) {
                return;
            }
            this.screen.remove(false, false, false);
        },
        undelete: function(event_) {
            this.screen.unremove();
        },
        previous: function(event_) {
            this.validate().done(function() {
                this.screen.display_previous();
            }.bind(this));
        },
        next: function(event_) {
            this.validate().done(function() {
                this.screen.display_next();
            }.bind(this));
        },
        switch_: function(event_) {
            this.screen.switch_view();
            // TODO color_set
        },
        edit: function() {
            if (!Sao.common.MODELACCESS.get(this.screen.model_name).read) {
                return;
            }
            this.validate().done(function() {
                var record = this.screen.current_record;
                if (record) {
                    var win = new Sao.Window.Form(this.screen, function() {});
                }
            }.bind(this));
        },
        validate: function() {
            var prm = jQuery.Deferred();
            this.view.set_value();
            var record = this.screen.current_record;
            if (record) {
                var fields = this.screen.current_view.get_fields();
                record.validate(fields).then(function(validate) {
                    if (!validate) {
                        this.screen.display();
                        prm.reject();
                    }
                    // TODO pre-validate
                    prm.resolve();
                }.bind(this));
            } else {
                prm.resolve();
            }
            return prm;
        }
    });

    Sao.View.Form.Many2Many = Sao.class_(Sao.View.Form.Widget, {
        class_: 'form-many2many',
        init: function(field_name, model, attributes) {
            Sao.View.Form.Many2Many._super.init.call(this, field_name, model,
                attributes);

            this._readonly = true;

            this.el = jQuery('<div/>', {
                'class': this.class_
            });
            this.menu = jQuery('<div/>', {
                'class': this.class_ + '-menu'
            });
            this.el.append(this.menu);

            var label = jQuery('<span/>', {
                'class': this.class_ + '-string',
                text: attributes.string
            });
            this.menu.append(label);

            var toolbar = jQuery('<span/>', {
                'class': this.class_ + '-toolbar'
            });
            this.menu.append(toolbar);

            this.entry = jQuery('<input/>', {
                type: 'input'
            });
            this.entry.on('keyup', this.key_press.bind(this));
            toolbar.append(this.entry);

            // TODO completion

            this.but_add = jQuery('<button/>').button({
                icons: {
                    primary: 'ui-icon-plus'
                },
                label: 'Add',
                text: false
            });
            this.but_add.click(this.add.bind(this));
            toolbar.append(this.but_add);

            this.but_remove = jQuery('<button/>').button({
                icons: {
                    primary: 'ui-icon-minus'
                },
                label: 'Remove',
                text: false
            });
            this.but_remove.click(this.remove.bind(this));
            toolbar.append(this.but_remove);

            this.content = jQuery('<div/>', {
                'class': this.class_ + '-content'
            });
            this.el.append(this.content);

            this.screen = new Sao.Screen(attributes.relation, {
                mode: ['tree'],
                view_ids: (attributes.view_ids || '').split(','),
                views_preload: attributes.views || {},
                row_activate: this.activate.bind(this)
            });
            this.prm = this.screen.switch_view('tree').done(function() {
                this.content.append(this.screen.screen_container.el);
            }.bind(this));
        },
        _get_color_el: function() {
            if (this.screen.current_view &&
                    (this.screen.current_view.view_type == 'tree') &&
                    this.screen.current_view.el) {
                return this.screen.current_view.el;
            }
            return Sao.View.Form.Many2Many._super._get_color_el.call(this);
        },
        set_readonly: function(readonly) {
            this._readonly = readonly;
            this._set_button_sensitive();
        },
        _set_button_sensitive: function() {
            var size_limit = false;
            if (this.record() && this.field()) {
                // TODO
            }

            this.entry.prop('disabled', this._readonly);
            this.but_add.prop('disabled', this._readonly || size_limit);
            // TODO position
            this.but_remove.prop('disabled', this._readonly);
        },
        display: function(record, field) {
            Sao.View.Form.Many2Many._super.display.call(this, record, field);

            this.prm.done(function() {
                if (!record) {
                    return;
                }
                if (field === undefined) {
                    this.screen.new_group();
                    this.screen.set_current_record(null);
                    this.screen.parent = true;
                    this.screen.display();
                    return;
                }
                var new_group = record.field_get_client(this.field_name);
                if (new_group != this.screen.group) {
                    this.screen.set_group(new_group);
                }
                this.screen.display();
            }.bind(this));
        },
        activate: function() {
            this.edit();
        },
        add: function() {
            var dom;
            var domain = this.field().get_domain(this.record());
            var context = this.field().get_context(this.record());
            var value = this.entry.val();
            if (value) {
                dom = [['rec_name', 'ilike', '%' + value + '%']].concat(domain);
            } else {
                dom = domain;
            }

            var callback = function(result) {
                if (!jQuery.isEmptyObject(result)) {
                    var ids = [];
                    var i, len;
                    for (i = 0, len = result.length; i < len; i++) {
                        ids.push(result[i][0]);
                    }
                    this.screen.group.load(ids, true);
                    this.screen.display();
                }
                this.entry.val('');
            }.bind(this);
            var model = new Sao.Model(this.attributes.relation);
            var ids_prm = model.execute('search',
                    [dom, 0, Sao.config.limit, null], context);
            ids_prm.done(function(ids) {
               if (ids.length != 1) {
                   var win = new Sao.Window.Search(this.attributes.relation,
                       callback, {
                           sel_multi: true,
                           ids: ids,
                           context: context,
                           domain: domain,
                           view_ids: (this.attributes.view_ids ||
                               '').split(','),
                           views_preload: this.attributes.views || {},
                           new_: this.attributes.create
                   });
               } else {
                   callback([[ids[0], null]]);
               }
            }.bind(this));
        },
        remove: function() {
            this.screen.remove(false, true, false);
        },
        key_press: function(event_) {
            var editable = true; // TODO compute editable
            var activate_keys = [Sao.common.TAB_KEYCODE];
            if (!this.wid_completion) {
                activate_keys.push(Sao.common.RETURN_KEYCODE);
            }

            if (event_.which == Sao.common.F3_KEYCODE) {
                this.add();
                event_.preventDefault();
            } else if (~activate_keys.indexOf(event_.which) && editable) {
                if (this.entry.val()) {
                    this.add();
                }

            }
        },
        edit: function() {
            if (this.screen.current_record) {
                var callback = function(result) {
                    if (result) {
                        this.screen.current_record.save().done(function() {
                            this.screen.display();
                        }.bind(this));
                    } else {
                        this.screen.current_record.cancel();
                    }
                };
                var win = new Sao.Window.Form(this.screen,
                        callback.bind(this));
            }
        }
    });

    Sao.View.Form.Binary = Sao.class_(Sao.View.Form.Widget, {
        class_: 'form-binary',
        blob_url: '',
        init: function(field_name, model, attributes) {
            Sao.View.Form.Binary._super.init.call(this, field_name, model,
                attributes);
            this.filename = attributes.filename || null;

            this.el = jQuery('<div/>', {
                'class': this.class_
            });

            if (this.filename && attributes.filename_visible) {
                this.text = jQuery('<input/>', {
                    type: 'input'
                });
                this.text.change(this.focus_out.bind(this));
                this.text.on('keyup', this.key_press.bind(this));
                this.el.append(this.text);
            }
            this.size = jQuery('<input/>', {
                type: 'input'
            });
            this.el.append(this.size);

            this.but_new = jQuery('<button/>').button({
                icons: {
                    primary: 'ui-icon-document'
                },
                text: false
            });
            this.but_new.click(this.new_.bind(this));
            this.el.append(this.but_new);

            if (this.filename) {
                this.but_open = jQuery('<a/>').button({
                    icons: {
                        primary: 'ui-icon-folder-open'
                    },
                    text: false
                });
                this.but_open.click(this.open.bind(this));
                this.el.append(this.but_open);
            }

            this.but_save_as = jQuery('<button/>').button({
                icons: {
                    primary: 'ui-icon-disk'
                },
                text: false
            });
            this.but_save_as.click(this.save_as.bind(this));
            this.el.append(this.but_save_as);

            this.but_remove = jQuery('<button/>').button({
                icons: {
                    primary: 'ui-icon-trash'
                },
                text: false
            });
            this.but_remove.click(this.remove.bind(this));
            this.el.append(this.but_remove);
        },
        filename_field: function() {
            var record = this.record();
            if (record) {
                return record.model.fields[this.filename];
            }
        },
        display: function(record, field) {
            Sao.View.Form.Binary._super.display.call(this, record, field);
            if (!field) {
                this.size.val('');
                if (this.filename) {
                    this.but_open.button('disable');
                }
                if (this.text) {
                    this.text.val('');
                }
                this.but_save_as.button('disable');
                return;
            }
            var size = field.get_size(record);
            var button_sensitive;
            if (size) {
                button_sensitive = 'enable';
            } else {
                button_sensitive = 'disable';
            }

            if (this.filename) {
                if (this.text) {
                    this.text.val(this.filename_field().get(record) || '');
                }
                this.but_open.button(button_sensitive);
            }
            this.size.val(Sao.common.humanize(size));
            this.but_save_as.button(button_sensitive);
        },
        save_as: function(evt) {
            var field = this.field();
            var record = this.record();
            field.get_data(record).done(function(data) {
                var blob = new Blob([data[0].binary],
                        {type: 'application/octet-binary'});
                var blob_url = window.URL.createObjectURL(blob);
                if (this.blob_url) {
                    window.URL.revokeObjectURL(this.blob_url);
                }
                this.blob_url = blob_url;
                window.open(blob_url);
            }.bind(this));
        },
        open: function(evt) {
            // TODO find a way to make the difference between downloading and
            // opening
            this.save_as(evt);
        },
        new_: function(evt) {
            var record = this.record();
            var file_dialog = jQuery('<div/>', {
                'class': 'file-dialog'
            });
            var file_selector = jQuery('<input/>', {
                type: 'file'
            });
            file_dialog.append(file_selector);
            var save_file = function() {
                var reader = new FileReader();
                reader.onload = function(evt) {
                    var uint_array = new Uint8Array(reader.result);
                    this.field().set_client(record, uint_array);
                }.bind(this);
                reader.onloadend = function(evt) {
                    file_dialog.dialog('close');
                };
                var file = file_selector[0].files[0];
                reader.readAsArrayBuffer(file);
                if (this.filename) {
                    this.filename_field().set_client(record, file.name);
                }
            };
            file_dialog.dialog({
                modal: true,
                title: 'Select a file', // TODO translation
                buttons: {
                    Cancel: function() {
                        $(this).dialog('close');
                    },
                    OK: save_file.bind(this)
                }
            });
            file_dialog.dialog('open');
        },
        remove: function(evt) {
            this.field().set_client(this.record(), null);
        },
        key_press: function(evt) {
            var editable = true; // TODO compute editable
            if (evt.which == Sao.common.F3_KEYCODE && editable) {
                this.new_();
                evt.preventDefault();
            } else if (evt.which == Sao.common.F2_KEYCODE) {
                this.open();
                evt.preventDefault();
            }
        },
        set_value: function(record, field) {
            if (this.text) {
                this.filename_field().set_client(record,
                        this.text.val() || '');
            }
        },
        _get_color_el: function() {
            if (this.text) {
                return this.text;
            } else {
                return this.size;
            }
        },
        set_readonly: function(readonly) {
            if (readonly) {
                this.but_new.hide();
                this.but_remove.hide();

            } else {
                this.but_new.show();
                this.but_remove.show();
            }
        }
    });
}());
