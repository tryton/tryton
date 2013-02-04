/* This file is part of Tryton.  The COPYRIGHT file at the top level of
   this repository contains the full copyright notices and license terms. */
(function() {
    'use strict';

    Sao.View = Sao.class_(Object, {
        init: function(screen, xml) {
            this.screen = screen;
            this.view_type = null;
            this.el = null;
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
            case 'one2many':
                return Sao.View.Tree.One2ManyColumn;
            case 'many2many':
                return Sao.View.Tree.Many2ManyColumn;
            case 'selection':
                return Sao.View.Tree.SelectionColumn;
            case 'float':
                return Sao.View.Tree.FloatColumn;
            case 'numeric':
                return Sao.View.Tree.FloatColumn;
            case 'float_time':
                return Sao.View.Tree.FloatTimeColumn;
            case 'integer':
                return Sao.View.Tree.IntegerColumn;
            case 'biginteger':
                return Sao.View.Tree.IntegerColumn;
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
            this.table = jQuery('<table/>', {
                'class': 'tree'
            });
            this.el.append(this.table);
            var thead = jQuery('<thead/>');
            this.table.append(thead);
            var tr = jQuery('<tr/>');
            thead.append(tr);
            this.columns.forEach(function(column) {
                var th = jQuery('<th/>', {
                    'text': column.attributes.string
                });
                tr.append(th);
            });
            this.tbody = jQuery('<tbody/>');
            this.table.append(this.tbody);

            // Footer with pagination stuff
            var footer = jQuery('<div/>', {
                'class': 'treefooter'
            });
            this.previous_button = jQuery('<button/>').button({
                'disabled': true,
                'icons': {
                    primary: 'ui-icon-triangle-1-w'
                },
                'text': false,
                'label': 'Previous' //TODO translation
            });
            footer.append(this.previous_button);
            this.pagination = jQuery('<span/>', {
                text: '0 / 0'
            });
            footer.append(this.pagination);
            this.next_button = jQuery('<button/>').button({
                'disabled': true,
                'icons': {
                    primary: 'ui-icon-triangle-1-e'
                },
                'text': false,
                'label': 'Next' //TODO translation
            });
            this.pagination.append(this.next_button);
            this.el.append(footer);
        },
        create_columns: function(model, xml) {
            var self = this;
            xml.find('tree').children().each(function(pos, child) {
                var attributes, column;
                if (child.tagName == 'field') {
                    var name = child.getAttribute('name');
                    attributes = {
                        'name': child.getAttribute('name'),
                        'readonly': child.getAttribute('readonly') == 1,
                        'widget': child.getAttribute('widget'),
                        'tree_invisible': child.getAttribute(
                            'tree_invisible') == 1,
                        'expand': child.getAttribute('expand') == 1,
                        'icon': child.getAttribute('icon'),
                        'sum': child.getAttribute('sum'),
                        'width': child.getAttribute('width'),
                        'orientation': child.getAttribute('orientation'),
                        'float_time': child.getAttribute('float_time'),
                        'pre_validate': child.getAttribute('pre_validate') == 1,
                        'completion': child.getAttribute('completion') == 1
                    };
                    if (attributes.widget === null) {
                        attributes.widget = model.fields[name].description.type;
                    }
                    var attribute_names = ['relation', 'domain', 'selection',
                        'relation_field', 'string', 'views', 'invisible',
                        'add_remove', 'sort', 'context', 'filename'];
                    for (var i in attribute_names) {
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
                } else if (child.tagName == 'button') {
                    attributes = {
                        'help': child.getAttribute('help'),
                        'string': child.getAttribute('string'),
                        'confirm': child.getAttribute('confirm'),
                        'name': child.getAttribute('name')
                    };
                    column = new Sao.View.Tree.ButtonColumn(attributes);
                }
                self.columns.push(column);
            });
        },
        display: function() {
            this.tbody.empty();
            var add_row = function(record, pos, group) {
                var tree_row = new Sao.View.Tree.Row(this, record, pos);
                tree_row.display();
            };
            this.screen.group.forEach(add_row.bind(this));
        },
        switch_: function(path) {
            this.screen.row_activate();
        },
        select_changed: function(record) {
            this.screen.current_record = record;
            // TODO validate if editable
            // TODO update_children
        }
    });

    Sao.View.Tree.Row = Sao.class_(Object, {
        init: function(tree, record, pos, parent) {
            this.tree = tree;
            this.record = record;
            this.children_field = tree.children_field;
            this.expander = null;
            this.expander_icon = null;
            var path = [];
            if (parent) {
                path = jQuery.extend([], parent.path.split('.'));
            }
            path.push(pos);
            this.path = path.join('.');
            this.el = jQuery('<tr/>');
            this.el.click(this.select_row.bind(this));
            var switch_ = function() {
                this.el.addClass('ui-state-highlight');
                this.tree.select_changed(this.record);
                this.tree.switch_(path);
            };
            this.el.dblclick(switch_.bind(this));
        },
        is_expanded: function() {
            return (this.path in this.tree.expanded);
        },
        display: function() {
            var depth = this.path.split('.').length;
            var update_expander = function() {
                if (jQuery.isEmptyObject(
                            this.record.field_get(
                                this.children_field))) {

                    this.expander_icon.hide();
                }
            };
            for (var i = 0; i < this.tree.columns.length; i++) {
                var td = jQuery('<td/>');
                if ((i === 0) && this.children_field) {
                    var expanded = 'ui-icon-plus';
                    if (this.is_expanded()) {
                        expanded = 'ui-icon-minus';
                    }
                    this.expander = jQuery('<span/>', {
                        'class': 'expander'
                    });
                    this.expander.html('&nbsp;');
                    // 16 == minimum width of icon
                    this.expander.css('width', ((depth * 10) + 16) + 'px');
                    this.expander.css('float', 'left');
                    this.expander.click(this.toggle_row.bind(this));
                    this.expander_icon = jQuery('<i/>', {
                        'class': 'ui-icon ' + expanded
                    });
                    this.expander.append(this.expander_icon);
                    this.expander_icon.css('float', 'right');
                    td.append(this.expander);
                    this.record.load(this.children_field).done(
                            update_expander.bind(this));
                }
                var column = this.tree.columns[i];
                td.append(column.render(this.record));
                this.el.append(td);
            }
            this.tree.tbody.append(this.el);
            if (this.is_expanded()) {
                var add_children = function() {
                    var add_row = function(record, pos, group) {
                        var tree_row = new Sao.View.Tree.Row(this.tree, record,
                                pos, this);
                        tree_row.display();
                    };
                    var children = this.record.field_get_client(children_field);
                    children.forEach(add_row.bind(this));
                };
                var children_field = this.children_field;
                this.record.load(this.children_field).done(
                        add_children.bind(this));
            }
        },
        toggle_row: function() {
            if (this.is_expanded()) {
                this.expander_icon.removeClass('ui-icon-minus');
                this.expander_icon.addClass('ui-icon-plus');
                delete this.tree.expanded[this.path];
            } else {
                this.expander_icon.removeClass('ui-icon-plus');
                this.expander_icon.addClass('ui-icon-minus');
                this.tree.expanded[this.path] = this;
            }
            this.tree.display();
        },
        select_row: function() {
            this.el.toggleClass('ui-state-highlight');
            if (this.el.hasClass('ui-state-highlight')) {
                this.tree.select_changed(this.record);
            } else {
                this.tree.select_changed(null);
            }
        }
    });

    Sao.View.Tree.CharColumn = Sao.class_(Object, {
        init: function(model, attributes) {
            this.type = 'field';
            this.field = model.fields[attributes.name];
            this.attributes = attributes;
        },
        get_cell: function() {
            var cell = jQuery('<div/>');
            cell.css('text-overflow', 'ellipsis');
            cell.css('overflow', 'hidden');
            cell.css('white-space', 'nowrap');
            cell.addClass('column-char');
            return cell;
        },
        update_text: function(cell, record) {
            cell.text(this.field.get_client(record));
        },
        render: function(record) {
            var cell = this.get_cell();
            record.load(this.attributes.name).done(function() {
                this.update_text(cell, record);
            }.bind(this));
            return cell;
        }
    });

    Sao.View.Tree.IntegerColumn = Sao.class_(Sao.View.Tree.CharColumn, {
        get_cell: function() {
            var cell = Sao.View.Tree.IntegerColumn._super.get_cell.call(this);
            cell.css('text-align', 'right');
            cell.removeClass('column-char');
            cell.addClass('column-integer');
            return cell;
        }
    });

    Sao.View.Tree.FloatColumn = Sao.class_(Sao.View.Tree.IntegerColumn, {
        init: function(model, attributes) {
            Sao.View.Tree.FloatColumn._super.init.call(this, model, attributes);
        },
        get_cell: function() {
            var cell = Sao.View.Tree.FloatColumn._super.get_cell.call(this);
            cell.removeClass('column-integer');
            cell.addClass('column-float');
            return cell;
        }
    });

    Sao.View.Tree.Many2OneColumn = Sao.class_(Sao.View.Tree.CharColumn, {
        get_cell: function() {
            var cell = Sao.View.Tree.Many2OneColumn._super.get_cell.call(this);
            cell.removeClass('column-char');
            cell.addClass('column-many2one');
            return cell;
        }
    });

    Sao.View.Tree.SelectionColumn = Sao.class_(Sao.View.Tree.CharColumn, {
        init: function(model, attributes) {
            Sao.View.Tree.SelectionColumn._super.init.call(this, model,
                attributes);
            var selection = attributes.selection || [];
            var store_selection = function(selection) {
                this.selection = {};
                for (var idx in selection) {
                    var choice = selection[idx];
                    this.selection[choice[0]] = choice[1];
                }
            };
            if (typeof(selection) == 'string') {
                var prm = Sao.rpc({
                    'method': 'model.' + model.name + '.' + selection,
                    'params': []
                }, model.session);
                prm.done(store_selection.bind(this));
            } else {
                store_selection.call(this, selection);
            }
        },
        get_cell: function() {
            var cell = Sao.View.Tree.Many2OneColumn._super.get_cell.call(this);
            cell.removeClass('column-char');
            cell.addClass('column-selection');
            return cell;
        },
        update_text: function(cell, record) {
            var value = this.field.get_client(record);
            cell.text(this.selection[value]);
        }
    });

    Sao.View.Tree.DateColumn = Sao.class_(Sao.View.Tree.CharColumn, {
        init: function(model, attributes) {
            Sao.View.Tree.DateColumn._super.init.call(this, model, attributes);
            this.date_format = Sao.common.date_format();
        },
        update_text: function(cell, record) {
            var text;
            var value = this.field.get_client(record);
            var pad = function(txt) {
                return (txt.toString().length < 2) ? '0' + txt : txt;
            };
            if (value) {
                text = this.date_format.replace('%d', pad(value.getDate()));
                text = text.replace('%m', pad(value.getMonth() + 1));
                text = text.replace('%Y', value.getFullYear());
                text = text.replace('%y', value.getFullYear().toString()
                    .substring(2, 4));
            } else {
                text = '';
            }
            cell.text(text);
        }
    });

    Sao.View.Tree.One2ManyColumn = Sao.class_(Sao.View.Tree.CharColumn, {
        update_text: function(cell, record) {
            cell.text('( ' + this.field.get_client(record).length + ' )');
        }
    });

    Sao.View.Tree.Many2ManyColumn = Sao.class_(Sao.View.Tree.One2ManyColumn, {
    });

    Sao.View.Tree.FloatTimeColumn = Sao.class_(Sao.View.Tree.CharColumn, {
        init: function(model, attributes) {
            Sao.View.Tree.FloatTimeColumn._super_.init.call(this, model,
                attributes);
            this.conv = null;
        },
        update_text: function(cell, record) {
            cell.text(Sao.common.text_to_float_time(
                    this.field.get_client(record), this.conv));
        }
    });

    Sao.View.Tree.ButtonColumn = Sao.class_(Object, {
        init: function(attributes) {
            this.type = 'button';
            this.attributes = attributes;
        },
        render: function() {
            var button = jQuery('<button/>', {
                'class': 'button',
                'label': this.attributes.string
            });
            return button;
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
            var container = this.parse(screen.model, xml);
            this.el.append(container.el);
        },
        parse: function(model, xml, container) {
            var root = xml.children()[0];
            container = new Sao.View.Form.Container(root.getAttribute('col'));
            var _parse = function(index, child) {
                var name = child.getAttribute('name');
                var widget;
                switch (child.tagName) {
                    case 'image':
                        // TODO
                        break;
                    case 'separator':
                        // TODO
                        break;
                    case 'label':
                        var text = child.getAttribute('string');
                        if (name in model.fields) {
                            // TODO exclude field
                            ['states', 'invisible'].forEach(
                                function(attr_name) {
                                    if ((child.getAttribute(attr_name) ===
                                            undefined) && (attr_name in
                                                model.fields[name].description))
                                    {
                                        child.setAttribute(attr_name,
                                            model.fields[name]
                                            .description[attr_name]);
                                    }
                                });
                            if (!text) {
                                // TODO RTL and translation
                                text = model.fields[name]
                                    .description.string + ':';
                            }
                            if (child.getAttribute('xalign') === undefined) {
                                child.setAttribute('xalign', 1.0);
                            }
                        } else if (!text) {
                            // TODO get content
                        }
                        if (text) {
                            widget = new Sao.View.Form.Label(text);
                            this.state_widgets.push(widget);
                        }
                        container.add(
                                Number(child.getAttribute('colspan') || 1),
                                widget);
                        // TODO help
                        break;
                    case 'newline':
                        container.add_row();
                        break;
                    case 'button':
                        // TODO
                        break;
                    case 'notebook':
                        // TODO
                        break;
                    case 'page':
                        // TODO
                        break;
                    case 'field':
                        // TODO exclude field
                        if (!(name in model.fields)) {
                            container.add(
                                    Number(child.getAttribute('colspan') || 1));
                            break;
                        }
                        var attributes = {
                            'name': child.getAttribute('name'),
                            'readonly': child.getAttribute('readonly') == 1,
                            'widget': child.getAttribute('widget')
                        };
                        if (attributes.widget === null) {
                            attributes.widget = model.fields[name]
                                .description.type;
                        }
                        var attribute_names = ['relation', 'domain',
                            'selection', 'relation_field', 'string', 'views',
                            'invisible', 'add_remove', 'sort', 'context',
                            'size', 'filename', 'autocomplete', 'translate',
                            'create', 'delete'];
                        for (var i in attribute_names) {
                            var attr = attribute_names[i];
                            if ((attr in model.fields[name].description) &&
                                    (child.getAttribute(attr) === null)) {
                                attributes[attr] = model.fields[name]
                                    .description[attr];
                            }
                        }
                        var WidgetFactory = Sao.View.form_widget_get(
                                attributes.widget);
                        if (!WidgetFactory) {
                            container.add(
                                Number(child.getAttribute('colspan') || 1));
                            break;
                        }
                        widget = new WidgetFactory(name, model, attributes);
                        widget.position = this.widget_id += 1;
                        // TODO expand, fill, help, height, width
                        container.add(
                                Number(child.getAttribute('colspan') || 1),
                                widget);
                        if (this.widgets[name] === undefined) {
                            this.widgets[name] = [];
                        }
                        this.widgets[name].push(widget);
                        break;
                    case 'group':
                        // TODO
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
            jQuery(root.children).each(_parse.bind(this));
            return container;
        },
        display: function() {
            var record = this.screen.current_record;
            for (var name in this.widgets) {
                var widgets = this.widgets[name];
                var field;
                if (record) {
                    field = record.model.fields[name];
                }
                // TODO set state
                for (var i = 0, len = widgets.length; i < len; i++) {
                    var widget = widgets[i];
                    widget.display(record, field);
                }
            }
            for (var j in this.state_widgets) {
                var state_widget = this.state_widgets[j];
                state_widget.state_set(record);
            }
        }
    });

    Sao.View.Form.Container = Sao.class_(Object, {
        init: function(col) {
            if (col === undefined) col = 4;
            this.col = col;
            this.el = jQuery('<table/>');
            this.add_row();
        },
        add_row: function() {
            this.row = jQuery('<tr/>');
            this.el.append(this.row);
        },
        add: function(colspan, widget) {
            if (colspan === undefined) colspan = 1;
            if (this.row.children().length > this.col + colspan) {
                this.add_row();
            }
            var el;
            if (widget) {
                el = widget.el;
            }
            var cell = this.row.append(jQuery('<td/>', {
                colspan: colspan
            }).append(el));
        }
    });

    var StateWidget = Sao.class_(Object, {
        init: function(attributes) {
            this.attributes = attributes;
        },
        state_set: function(record) {
            // TODO
        }
    });

    Sao.View.Form.Label = Sao.class_(StateWidget, {
        init: function(text, attributes) {
            Sao.View.Form.Label._super.init.call(this, attributes);
            this.el = jQuery('<label/>', {
                text: text,
                'class': 'form-label'
            });
        }
    });

    Sao.View.form_widget_get = function(type) {
        switch (type) {
            case 'char':
                return Sao.View.Form.Char;
            case 'sha':
                return Sao.View.Form.Sha;
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
        },
        display: function(record, field) {
            // TODO set state
        }
    });

    Sao.View.Form.Char = Sao.class_(Sao.View.Form.Widget, {
        init: function(field_name, model, attributes) {
            Sao.View.Form.Char._super.init.call(this, field_name, model,
                attributes);
            this.el = jQuery('<input/>', {
                'type': 'input',
                'class': 'form-char'
            });
        },
        display: function(record, field) {
            Sao.View.Form.Char._super.display.call(this, record, field);
            var set_text = function() {
                var value = record.field_get(this.field_name);
                this.el.val(value || '');
            };
            record.load(this.field_name).done(set_text.bind(this));
        }
    });

    Sao.View.Form.Sha = Sao.class_(Sao.View.Form.Char, {
        init: function(field_name, model, attributes) {
            Sao.View.Form.Sha._super.init.call(this, field_name, model,
                attributes);
            this.el.removeClass('form-char');
            this.el.addClass('form-sha');
            this.el.prop('type', 'password');
        }
    });

}());
