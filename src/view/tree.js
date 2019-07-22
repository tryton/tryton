/* This file is part of Tryton.  The COPYRIGHT file at the top level of
   this repository contains the full copyright notices and license terms. */
(function() {
    'use strict';

    Sao.View.TreeXMLViewParser = Sao.class_(Sao.View.XMLViewParser, {
        _parse_tree: function(node, attributes) {
            [].forEach.call(node.childNodes, function(child) {
                this.parse(child);
            }.bind(this));
        },
        _parse_field: function(node, attributes) {
            var name = attributes.name;
            var ColumnFactory = Sao.View.TreeXMLViewParser.WIDGETS[
                attributes.widget];
            var column = new ColumnFactory(this.view.screen.model, attributes);
            if (!this.view.widgets[name]) {
                this.view.widgets[name] = [];
            }
            this.view.widgets[name].push(column);

            var prefixes = [], suffixes = [];
            if (~['url', 'email', 'callto', 'sip'
                    ].indexOf(attributes.widget)) {
                column.prefixes.push(
                    new Sao.View.Tree.Affix(attributes, attributes.widget));
            }
            if ('icon' in attributes) {
                column.prefixes.push(new Sao.View.Tree.Affix(attributes));
            }
            var affix, affix_attributes;
            var affixes = node.childNodes;
            for (var i = 0; i < affixes.length; i++) {
                affix = affixes[i];
                affix_attributes = {};
                for (var j = 0, len = affix.attributes.length; j < len; j++) {
                    var attribute = affix.attributes[j];
                    affix_attributes[attribute.name] = attribute.value;
                }
                if (!affix_attributes.name) {
                    affix_attributes.name = name;
                }
                var list;
                if (affix.tagName == 'prefix') {
                    list = column.prefixes;
                } else {
                    list = column.suffixes;
                }
                list.push(new Sao.View.Tree.Affix(affix_attributes));
            }
            if (!this.view.attributes.sequence &&
                    !this.view.children_field &&
                    this.field_attrs[name].sortable !== false){
                column.sortable = true;
            }
            this.view.columns.push(column);

            if (attributes.sum) {
                var label = attributes.sum + Sao.i18n.gettext(': ');
                var sum = jQuery('<label/>', {
                    'text': label,
                });
                var aggregate = jQuery('<span/>', {
                    'class': 'value',
                });
                this.view.sum_widgets[name] = [sum, aggregate];
            }
        },
        _parse_button: function(node, attributes) {
            var column = new Sao.View.Tree.ButtonColumn(
                this.view, attributes);
            this.view.columns.push(column);
        }
    });

    Sao.View.Tree = Sao.class_(Sao.View, {
        view_type: 'tree',
        xml_parser: Sao.View.TreeXMLViewParser,
        init: function(view_id, screen, xml, children_field) {
            this.children_field = children_field;
            this.sum_widgets = {};
            this.columns = [];
            this.selection_mode = (screen.attributes.selection_mode ||
                Sao.common.SELECTION_MULTIPLE);
            this.el = jQuery('<div/>');
            this.scrollbar = jQuery('<div/>')
                .appendTo(jQuery('<div/>', {
                    'class': 'scrollbar responsive',
                }).appendTo(this.el));
            this.treeview = jQuery('<div/>', {
                'class': 'treeview responsive'
            }).appendTo(this.el);

            // Synchronize both scrollbars
            this.treeview.scroll(function() {
                this.scrollbar.parent().scrollLeft(this.treeview.scrollLeft());
            }.bind(this));
            this.scrollbar.parent().scroll(function() {
                this.treeview.scrollLeft(this.scrollbar.parent().scrollLeft());
            }.bind(this));

            this.expanded = {};

            Sao.View.Tree._super.init.call(this, view_id, screen, xml);

            // Table of records
            this.rows = [];
            this.edited_row = null;
            this.table = jQuery('<table/>', {
                'class': 'tree table table-hover table-striped table-condensed'
            });
            if (this.editable) {
                this.table.addClass('table-bordered');
            }
            this.treeview.append(this.table);
            var colgroup = jQuery('<colgroup/>').appendTo(this.table);
            var col = jQuery('<col/>', {
                'class': 'selection-state',
            }).appendTo(colgroup);
            if (this.selection_mode == Sao.common.SELECTION_NONE) {
                col.css('width', 0);
            }
            this.thead = jQuery('<thead/>').appendTo(this.table);
            var tr = jQuery('<tr/>');
            var th = jQuery('<th/>', {
                'class': 'selection-state'
            });
            this.selection = jQuery('<input/>', {
                'type': 'checkbox',
            });
            this.selection.change(this.selection_changed.bind(this));
            th.append(this.selection);
            tr.append(th);
            this.thead.append(tr);

            this.tfoot = null;
            var sum_row;
            if (!jQuery.isEmptyObject(this.sum_widgets)) {
                sum_row = jQuery('<tr/>');
                sum_row.append(jQuery('<td/>'));
                this.tfoot = jQuery('<tfoot/>');
                this.tfoot.append(sum_row);
                this.table.append(this.tfoot);
            }

            this.columns.forEach(function(column) {
                col = jQuery('<col/>', {
                    'class': column.attributes.widget,
                }).appendTo(colgroup);
                th = jQuery('<th/>', {
                    'class': column.attributes.widget,
                });
                var label = jQuery('<label/>')
                    .text(column.attributes.string)
                    .attr('title', column.attributes.string);
                if (this.editable) {
                    if (column.attributes.required) {
                        label.addClass('required');
                    }
                    if (!column.attributes.readonly) {
                        label.addClass('editable');
                    }
                }
                if (column.attributes.help) {
                    label.attr('title', column.attributes.help);
                }
                if (column.sortable) {
                    var arrow = jQuery('<img/>', {
                        'class': 'icon',
                    });
                    label.append(arrow);
                    column.arrow = arrow;
                    th.click(column, this.sort_model.bind(this));
                    label.addClass('sortable');
                }
                tr.append(th.append(label));
                column.header = th;
                column.col = col;

                column.footers = [];
                if (!jQuery.isEmptyObject(this.sum_widgets)) {
                    var field_name = column.attributes.name;
                    var total_cell = jQuery('<td/>', {
                        'class': column.class_,
                    });
                    if (field_name in this.sum_widgets) {
                        var sum_label = this.sum_widgets[field_name][0];
                        var sum_value = this.sum_widgets[field_name][1];
                        total_cell.append(sum_label);
                        total_cell.append(sum_value);
                        total_cell.attr('data-title', sum_label.text());
                    }
                    sum_row.append(total_cell);
                    column.footers.push(total_cell);
                }
            }, this);
            this.tbody = jQuery('<tbody/>');
            this.table.append(this.tbody);

            this.display_size = Sao.config.display_size;
        },
        get editable() {
            return (Boolean(this.attributes.editable) &&
                !this.screen.attributes.readonly);
        },
        sort_model: function(e){
            var column = e.data;
            var arrow = column.arrow;
            this.columns.forEach(function(col) {
                if (col.arrow){
                    if (col != column && col.arrow.attr('src')) {
                        col.arrow.attr('src', '');
                    }
                }
            });
            this.screen.order = this.screen.default_order;
            if (arrow.data('order') == 'ASC') {
                arrow.data('order', 'DESC');
                Sao.common.ICONFACTORY.get_icon_url('tryton-arrow-up')
                    .then(function(url) {
                        arrow.attr('src', url);
                    });
                this.screen.order = [[column.attributes.name, 'DESC']];
            } else if (arrow.data('order') == 'DESC') {
                arrow.data('order', '');
                arrow.attr('src', '');
            } else {
                arrow.data('order', 'ASC');
                Sao.common.ICONFACTORY.get_icon_url('tryton-arrow-down')
                    .then(function(url) {
                        arrow.attr('src', url);
                    });
                this.screen.order = [[column.attributes.name, 'ASC']];
            }
            var unsaved_records = [];
            this.group.forEach(function(unsaved_record) {
                    if (unsaved_record.id < 0) {
                        unsaved_records = unsaved_record.group;
                }
            });
            var search_string = this.screen.screen_container.get_text();
            if ((!jQuery.isEmptyObject(unsaved_records)) ||
                    (this.screen.search_count == this.group.length) ||
                    (this.group.parent)) {
                this.screen.search_filter(search_string, true).then(
                function(ids) {
                    this.group.sort(function(a, b) {
                        a = ids.indexOf(a.id);
                        a = a < 0 ? ids.length : a;
                        b = ids.indexOf(b.id);
                        b = b < 0 ? ids.length : b;
                        if (a < b) {
                            return -1;
                        } else if (a > b) {
                            return 1;
                        } else {
                            return 0;
                        }
                    });
                    this.screen.display();
                }.bind(this));
            } else {
                this.screen.search_filter(search_string);
            }
        },
        update_arrow: function() {
            var order = this.screen.order,
                name = null,
                direction = null,
                icon = '';
            if (order && (order.length == 1)) {
                name = order[0][0];
                direction = order[0][1];
                icon = {
                    'ASC': 'tryton-arrow-down',
                    'DESC': 'tryton-arrow-up',
                }[direction];
            }
            this.columns.forEach(function(col) {
                var arrow = col.arrow;
                if (arrow) {
                    if (col.attributes.name != name) {
                        arrow.data('order', '');
                        arrow.attr('src', '');
                    } else {
                        arrow.data('order', direction);
                        Sao.common.ICONFACTORY.get_icon_url(icon)
                            .then(function(url) {
                                arrow.attr('src', url);
                            });
                    }
                }
            });
        },
        get_fields: function() {
            return Object.keys(this.widgets);
        },
        get_buttons: function() {
            var buttons = [];
            this.columns.forEach(function(column) {
                if (column instanceof Sao.View.Tree.ButtonColumn) {
                    buttons.push(column);
                }
            });
            return buttons;
        },
        display: function(selected, expanded) {
            var current_record = this.record;
            if (jQuery.isEmptyObject(selected)) {
                selected = this.get_selected_paths();
                if (this.selection.prop('checked') &&
                    !this.selection.prop('indeterminate')) {
                    this.screen.group.slice(
                        this.rows.length, this.display_size)
                        .forEach(function(record) {
                            selected.push([record.id]);
                        });
                } else {
                    if (current_record) {
                        var current_path = current_record.get_path(this.group);
                        current_path = current_path.map(function(e) {
                            return e[1];
                        });
                        if (!Sao.common.contains(selected, current_path)) {
                            selected = [current_path];
                        }
                    } else if (!current_record) {
                        selected = [];
                    }
                }
            }
            expanded = expanded || [];

            if (this.selection_mode == Sao.common.SELECTION_MULTIPLE) {
                this.selection.show();
            } else {
                this.selection.hide();
            }

            var row_records = function() {
                return this.rows.map(function(row) {
                    return row.record;
                });
            }.bind(this);
            var min_display_size = Math.min(
                    this.group.length, this.display_size);
            // XXX find better check to keep focus
            if (this.children_field) {
                this.construct();
            } else if ((min_display_size > this.rows.length) &&
                Sao.common.compare(
                    this.group.slice(0, this.rows.length),
                    row_records())) {
                this.construct(true);
            } else if ((min_display_size != this.rows.length) ||
                !Sao.common.compare(
                    this.group.slice(0, this.rows.length),
                    row_records())){
                this.construct();
            }

            // Set column visibility depending on attributes and domain
            var visible_columns = 1;  // start at 1 because of the checkbox
            var domain = [];
            if (!jQuery.isEmptyObject(this.screen.domain)) {
                domain.push(this.screen.domain);
            }
            var tab_domain = this.screen.screen_container.get_tab_domain();
            if (!jQuery.isEmptyObject(tab_domain)) {
                domain.push(tab_domain);
            }
            var inversion = new Sao.common.DomainInversion();
            domain = inversion.simplify(domain);
            var decoder = new Sao.PYSON.Decoder(this.screen.context);
            var min_width = 0;
            this.columns.forEach(function(column) {
                visible_columns += 1;
                var name = column.attributes.name;
                if (!name) {
                    return;
                }
                var related_cells = column.footers.slice();
                related_cells.push(column.header);
                if ((decoder.decode(column.attributes.tree_invisible || '0')) ||
                        (name === this.screen.exclude_field)) {
                    visible_columns -= 1;
                    related_cells.forEach(function(cell) {
                        cell.hide();
                        cell.addClass('invisible');
                    });
                } else {
                    var inv_domain = inversion.domain_inversion(domain, name);
                    if (typeof inv_domain != 'boolean') {
                        inv_domain = inversion.simplify(inv_domain);
                    }
                    var unique = inversion.unique_value(inv_domain)[0];
                    if (unique && jQuery.isEmptyObject(this.children_field)) {
                        visible_columns -= 1;
                        related_cells.forEach(function(cell) {
                            cell.hide();
                            cell.addClass('invisible');
                        });
                    } else {
                        related_cells.forEach(function(cell) {
                            cell.show();
                            cell.removeClass('invisible');
                        });
                    }
                }

                if (column.header.hasClass('invisible')) {
                    column.col.css('width', 0);
                    column.col.hide();
                } else if (!column.col.hasClass('selection-state') &&
                    !column.col.hasClass('favorite')) {
                    var width = {
                        'integer': 6,
                        'biginteger': 6,
                        'float': 8,
                        'numeric': 8,
                        'selection': 9,
                        'one2many': 5,
                        'many2many': 5,
                        'boolean': 2,
                        'binary': 20,
                    }[column.attributes.widget] || 10;
                    var factor = 1;
                    if (column.attributes.expand) {
                        factor += parseInt(column.attributes.expand, 10);
                    }
                    column.col.css('width', width * 100 * factor  + '%');
                    column.col.show();
                    min_width += width * 10;
                }
            }.bind(this));
            this.table.css('min-width', min_width + 'px');
            this.scrollbar.css('min-width', min_width + 'px');
            this.tbody.find('tr.more-row > td').attr(
                'colspan', visible_columns);

            if (!this.table.hasClass('no-responsive') &
                (this.columns.filter(function(c) {
                    return !c.header.hasClass('invisible');
                }).length > 1)) {
                this.table.addClass('responsive');
                this.table.addClass('responsive-header');
            } else {
                this.table.removeClass('responsive');
                this.table.removeClass('responsive-header');
            }

            this.update_arrow();
            return this.redraw(selected, expanded).done(
                Sao.common.debounce(this.update_sum.bind(this), 250));
        },
        construct: function(extend) {
            var tbody = this.tbody;
            if (!extend) {
                this.rows = [];
                this.tbody = jQuery('<tbody/>');
                this.edited_row = null;
            } else {
                this.tbody.find('tr.more-row').remove();
            }
            var start = this.rows.length;
            var add_row = function(record, pos, group) {
                var RowBuilder;
                if (this.editable) {
                    RowBuilder = Sao.View.Tree.RowEditable;
                } else {
                    RowBuilder = Sao.View.Tree.Row;
                }
                var tree_row = new RowBuilder(this, record, this.rows.length);
                this.rows.push(tree_row);
                tree_row.construct();
            };
            this.group.slice(start, this.display_size).forEach(
                    add_row.bind(this));
            if (!extend) {
                tbody.replaceWith(this.tbody);
            }

            if (this.display_size < this.group.length) {
                var more_row = jQuery('<tr/>', {
                    'class': 'more-row',
                });
                var more_cell = jQuery('<td/>');
                var more_button = jQuery('<button/>', {
                    'class': 'btn btn-default',
                    'type': 'button'
                }).append(Sao.i18n.gettext('More')
                    ).click(function() {
                    this.display_size += Sao.config.display_size;
                    this.display();
                }.bind(this));
                more_cell.append(more_button);
                more_row.append(more_cell);
                this.tbody.append(more_row);
            }
        },
        redraw: function(selected, expanded) {
            return redraw_async(this.rows, selected, expanded);
        },
        switch_: function(path) {
            this.screen.row_activate();
        },
        select_changed: function(record) {
            if (this.edited_row) {
                record = this.edited_row.record;
                this.edited_row.set_selection(true);
            }
            this.record = record;
            // TODO update_children
        },
        update_sum: function() {
            for (var name in this.sum_widgets) {
                if (!this.sum_widgets.hasOwnProperty(name)) {
                    continue;
                }

                var selected_records = this.selected_records;
                var aggregate = '-';
                var sum_label = this.sum_widgets[name][0];
                var sum_value = this.sum_widgets[name][1];
                var sum_ = null;
                var selected_sum = null;
                var loaded = true;
                var digit = 0;
                var field = this.screen.model.fields[name];
                var i, record;
                var records_ids = selected_records.map(function(record){
                    return record.id;
                });
                for (i=0; i < this.group.length; i++) {
                    record = this.group[i];
                    if (!record.get_loaded([name]) && record.id >=0){
                        loaded = false;
                        break;
                    }
                    var value = field.get(record);
                    if (value && value.isTimeDelta) {
                        value = value.asSeconds();
                    }
                    if (value !== null){
                        if (sum_ === null){
                            sum_ = value;
                        }else {
                            sum_ += value;
                        }
                        if (~records_ids.indexOf(record.id) ||
                            !selected_records){
                            if (selected_sum === null){
                                selected_sum = value;
                            }else {
                                selected_sum += value;
                            }
                        }
                        if (field.digits) {
                            var fdigits = field.digits(record);
                            if (fdigits && digit !== null){
                                digit = Math.max(fdigits[1], digit);
                            } else {
                                digit = null;
                            }
                        }
                    }
                }
                if (loaded) {
                    if (field.description.type == 'timedelta'){
                        var converter = field.converter(this.group);
                        selected_sum =  Sao.common.timedelta.format(
                            Sao.TimeDelta(null, selected_sum), converter);
                        sum_ = Sao.common.timedelta.format(
                            Sao.TimeDelta(null, sum_), converter);
                    } else if (digit !== null){
                        var options = {};
                        options.minimumFractionDigits = digit;
                        options.maximumFractionDigits = digit;
                        selected_sum = (selected_sum || 0).toLocaleString(
                            Sao.i18n.BC47(Sao.i18n.getlang()), options);
                        sum_ = (sum_ || 0).toLocaleString(
                            Sao.i18n.BC47(Sao.i18n.getlang()), options);
                    }
                    aggregate = selected_sum + ' / ' + sum_;
                }
                sum_value.text(aggregate);
                sum_value.parent().attr(
                    'title', sum_label.text() + ' ' + sum_value.text());
            }
        },
        get selected_records() {
            if (this.selection_mode == Sao.common.SELECTION_NONE) {
                return [];
            }
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
                this.group.slice(this.rows.length)
                    .forEach(function(record) {
                        records.push(record);
                    });
            }
            return records;
        },
        select_records: function(from, to) {
            if (!from && to) {
                from = this.rows[0].record;
            }
            if (from && to) {
                var from_idx = from.get_index_path(this.screen.group);
                var to_idx = to.get_index_path(this.screen.group);
                var max_len = Math.min(from_idx.length, to_idx.length);
                var tmp;
                for (var i=0; i < max_len; i++) {
                    if (from_idx[i] > to_idx[i]) {
                        tmp = from;
                        from = to;
                        to = tmp;
                        break;
                    }
                }
                if (!tmp && (from_idx.length > to_idx.length)) {
                    tmp = from;
                    from = to;
                    to = tmp;
                }
            }
            var value = this.rows[0].record === from;
            var select_record = function(row) {
                var record = row.record;
                if (record === from) {
                    value = true;
                }
                row.set_selection(value);
                if (record === to) {
                    value = false;
                }
                row.rows.forEach(select_record);
            };
            this.rows.forEach(select_record);
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
            this.update_sum();
        },
        update_selection: function() {
            this.update_sum();
            var selected_records = this.selected_records;
            this.selection.prop('indeterminate', false);
            if (jQuery.isEmptyObject(selected_records)) {
                this.selection.prop('checked', false);
            } else if (selected_records.length ==
                    this.tbody.children().length &&
                    this.display_size >= this.group.length) {
                this.selection.prop('checked', true);
            } else {
                this.selection.prop('indeterminate', true);
                // Set checked to go first unchecked after first click
                this.selection.prop('checked', true);
            }
        },
        get_selected_paths: function() {
            var selected_paths = [];
            function get_selected(row, path) {
                var i, r, len, r_path;
                for (i = 0, len = row.rows.length; i < len; i++) {
                    r = row.rows[i];
                    r_path = path.concat([r.record.id]);
                    if (r.is_selected()) {
                        selected_paths.push(r_path);
                    }
                    get_selected(r, r_path);
                }
            }
            get_selected(this, []);
            return selected_paths;
        },
        get_expanded_paths: function(starting_path, starting_id_path) {
            var id_path, id_paths, row, children_rows, path;
            if (starting_path === undefined) {
                starting_path = [];
            }
            if (starting_id_path === undefined) {
                starting_id_path = [];
            }
            id_paths = [];
            row = this.find_row(starting_path);
            children_rows = row ? row.rows : this.rows;
            for (var path_idx = 0, len = this.n_children(row) ;
                    path_idx < len ; path_idx++) {
                path = starting_path.concat([path_idx]);
                row = children_rows[path_idx];
                if (row && row.is_expanded()) {
                    id_path = starting_id_path.concat(row.record.id);
                    id_paths.push(id_path);
                    id_paths = id_paths.concat(this.get_expanded_paths(path,
                                id_path));
                }
            }
            return id_paths;
        },
        find_row: function(path) {
            var index;
            var row = null;
            var group = this.rows;
            for (var i=0, len=path.length; i < len; i++) {
                index = path[i];
                if (!group || index >= group.length) {
                    return null;
                }
                row = group[index];
                group = row.rows;
                if (!this.children_field) {
                    break;
                }
            }
            return row;
        },
        n_children: function(row) {
            if (!row || !this.children_field) {
                return this.rows.length;
            }
            return row.record._values[this.children_field].length;
        },
        set_cursor: function(new_, reset_view) {
            var i, root_group, path, row_path, row, column;
            var row_idx, rest, td;

            if (!this.record) {
                return;
            }
            path = this.record.get_index_path(this.group);
            if (this.rows.length < path[0]) {
                this.display_size = this.group.length;
                this.display();
            }
            row_idx = path[0];
            rest = path.slice(1);
            if (rest.length > 0) {
                this.rows[row_idx].expand_to_path(rest);
            }
            row = this.find_row(path);
            column = row.next_column(null, new_);
            if (column !== null) {
                td = row._get_column_td(column);
                if (this.editable && new_) {
                    td.trigger('click');
                }
                td.find(':input,[tabindex=0]').focus();
            }
        },
        save_row: function() {
            var i, prm, edited_row = this.edited_row;
            if (!this.editable || !this.edited_row) {
                return jQuery.when();
            }
            if (!this.edited_row.record.validate(
                    this.get_fields(), false, false, true)) {
                var focused = false;
                var invalid_fields = this.edited_row.record.invalid_fields();
                for (i = 0; i < this.columns.length; i++) {
                    var col = this.columns[i];
                    if (col.attributes.name in invalid_fields) {
                        var td = this.edited_row._get_column_td(i);
                        var editable_el = this.edited_row.get_editable_el(td);
                        var widget = editable_el.data('widget');
                        widget.display(this.edited_row.record, col.field);
                        if (!focused) {
                            widget.focus();
                            focused = true;
                        }
                    }
                }
                return;
            }
            if (!this.group.parent) {
                prm = this.edited_row.record.save();
            } else if (this.screen.attributes.pre_validate) {
                prm = this.record.pre_validate();
            } else {
                prm = jQuery.when();
            }
            prm.fail(function() {
                if (this.edited_row != edited_row) {
                    this.edit_row(null);
                    edited_row.set_selection(true);
                    edited_row.selection_changed();
                    this.edit_row(edited_row);
                }
            }.bind(this));
            return prm;
        },
        edit_row: function(row) {
            if (!this.editable || this.edited_row == row) {
                return;
            }
            if (this.edited_row) {
                this.edited_row.unset_editable();
            }
            if (row) {
                row.set_editable();
            }
            this.edited_row = row;
        }
    });

    function redraw_async(rows, selected, expanded) {
        var dfd= jQuery.Deferred(),
            i = 0;
        var redraw = function() {
            for (; i < rows.length; i++) {
                var row = rows[i];
                var record = row.record,
                    column = row.tree.columns[0];
                if (!record.is_loaded(column.attributes.name)) {
                    // Prefetch the first field to prevent promises in
                    // Cell.render
                    record.load(column.attributes.name).done(redraw);
                    return;
                } else {
                    row.redraw(selected, expanded);
                }
            }
            dfd.resolve();
        };
        redraw();
        return dfd.promise();
    }

    Sao.View.Tree.Row = Sao.class_(Object, {
        init: function(tree, record, pos, parent) {
            this.tree = tree;
            this.current_column = null;
            this.rows = [];
            this.record = record;
            this.parent_ = parent;
            this.children_field = tree.children_field;
            this.expander = null;
            var path = [];
            if (parent) {
                path = jQuery.extend([], parent.path.split('.'));
            }
            path.push(pos);
            this.path = path.join('.');
            this.el = jQuery('<tr/>');
            this.el.on('click', this.select_row.bind(this));
        },
        is_expanded: function() {
            return (this.path in this.tree.expanded);
        },
        get_last_child: function() {
            if (!this.children_field || !this.is_expanded() ||
                    jQuery.isEmptyObject(this.rows)) {
                return this;
            }
            return this.rows[this.rows.length - 1].get_last_child();
        },
        get_id_path: function() {
            if (!this.parent_) {
                return [this.record.id];
            }
            return this.parent_.get_id_path().concat([this.record.id]);
        },
        build_widgets: function() {
            var table = jQuery('<table/>');
            table.css('width', '100%');
            var row = jQuery('<tr/>');
            table.append(row);
            return [table, row];
        },
        construct: function() {
            var el_node = this.el[0];
            while (el_node.firstChild) {
                el_node.removeChild(el_node.firstChild);
            }

            var td;
            this.tree.el.uniqueId();
            td = jQuery('<td/>', {
                'class': 'selection-state',
            }).click(function(event_) {
                event_.stopPropagation();
                this.selection.click();
            }.bind(this));
            this.el.append(td);
            this.selection = jQuery('<input/>', {
                'type': 'checkbox',
                'name': 'tree-selection-' + this.tree.el.attr('id'),
            });
            this.selection.click(function(event_) {
                event_.stopPropagation();
            });
            this.selection.change(this.selection_changed.bind(this));
            td.append(this.selection);

            var depth = this.path.split('.').length;
            for (var i = 0; i < this.tree.columns.length; i++) {
                var column = this.tree.columns[i];
                td = jQuery('<td/>', {
                    'data-title': column.attributes.string + Sao.i18n.gettext(': ')
                }).append(jQuery('<span/>', { // For responsive min-height
                    'aria-hidden': true
                }));
                td.on('click keypress', {'index': i}, function(event_) {
                    if (this.expander && !this.is_expanded()) {
                        this.toggle_row();
                    }
                    this.select_column(event_.data.index);
                }.bind(this));
                if (!this.tree.editable) {
                    td.dblclick(this.switch_row.bind(this));
                } else {
                    if (column.attributes.required) {
                        td.addClass('required');
                    }
                    if (!column.attributes.readonly) {
                        td.addClass('editable');
                    }
                }
                var widgets = this.build_widgets();
                var table = widgets[0];
                var row = widgets[1];
                td.append(table);
                if ((i === 0) && this.children_field) {
                    this.expander = jQuery('<img/>', {
                        'tabindex': 0,
                        'class': 'icon',
                    });
                    this.expander.html('&nbsp;');
                    var margin = 'margin-left';
                    if (Sao.i18n.rtl) {
                        margin = 'margin-right';
                    }
                    this.expander.css(margin, (depth - 1) + 'em');
                    this.expander.on('click keypress',
                            Sao.common.click_press(this.toggle_row.bind(this)));
                    row.append(jQuery('<td/>', {
                        'class': 'expander'
                    }).append(this.expander).css('width', 1));
                }
                var j;
                if (column.prefixes) {
                    for (j = 0; j < column.prefixes.length; j++) {
                        var prefix = column.prefixes[j];
                        row.append(jQuery('<td/>', {
                            'class': 'prefix'
                        }).css('width', 1));
                    }
                }
                row.append(jQuery('<td/>', {
                    'class': 'widget'
                }));
                if (column.suffixes) {
                    for (j = 0; j < column.suffixes.length; j++) {
                        var suffix = column.suffixes[j];
                        row.append(jQuery('<td/>', {
                            'class': 'suffix'
                        }).css('width', 1));
                    }
                }

                this.el.append(td);
            }
            if (this.parent_) {
                var last_child = this.parent_.get_last_child();
                last_child.el.after(this.el);
            } else {
                this.tree.tbody.append(this.el);
            }
        },
        _get_column_td: function(column_index, row) {
            row = row || this.el;
            return jQuery(row.children()[column_index + 1]);
        },
        redraw: function(selected, expanded) {
            selected = selected || [];
            expanded = expanded || [];
            var thead_visible = this.tree.thead.is(':visible');

            switch(this.tree.selection_mode) {
                case Sao.common.SELECTION_NONE:
                    this.selection.hide();
                    break;
                case Sao.common.SELECTION_SINGLE:
                    this.selection.attr('type', 'radio');
                    this.selection.show();
                    break;
                case Sao.common.SELECTION_MULTIPLE:
                    this.selection.attr('type', 'checkbox');
                    this.selection.show();
                    break;
            }


            for (var i = 0; i < this.tree.columns.length; i++) {
                var column = this.tree.columns[i];
                var td = this._get_column_td(i);
                var tr = td.find('tr');
                var cell;
                if (column.prefixes) {
                    for (var j = 0; j < column.prefixes.length; j++) {
                        var prefix = column.prefixes[j];
                        var prefix_el = jQuery(tr.children('.prefix')[j]);
                        cell = prefix_el.children();
                        if (cell.length) {
                            prefix.render(this.record, cell);
                        } else {
                            prefix_el.html(prefix.render(this.record));
                        }
                    }
                }
                var widget = tr.children('.widget');
                cell = widget.children();
                if (cell.length) {
                    column.render(this.record, cell);
                } else {
                    widget.html(column.render(this.record));
                }
                if (column.suffixes) {
                    for (var k = 0; k < column.suffixes.length; k++) {
                        var suffix = column.suffixes[k];
                        var suffix_el = jQuery(tr.children('.suffix')[k]);
                        cell = suffix_el.children();
                        if (cell.length) {
                            suffix.render(this.record, cell);
                        } else {
                            suffix_el.html(suffix.render(this.record));
                        }
                    }
                }
                if ((column.header.is(':hidden') && thead_visible) ||
                        column.header.css('display') == 'none') {
                    td.hide();
                    td.addClass('invisible');
                } else {
                    td.show();
                    td.removeClass('invisible');
                }
            }
            var row_id_path = this.get_id_path();
            this.set_selection(Sao.common.contains(selected, row_id_path));
            if (this.children_field) {
                this.record.load(this.children_field).done(function() {
                    if (this.is_expanded() ||
                        Sao.common.contains(expanded, row_id_path)) {
                        this.expander.css('visibility', 'visible');
                        this.tree.expanded[this.path] = this;
                        this.expand_children(selected, expanded);
                        this.update_expander(true);
                    } else {
                        var length = this.record.field_get_client(
                            this.children_field).length;
                        this.expander.css('visibility',
                            length ? 'visible' : 'hidden');
                        this.update_expander(false);
                    }
                }.bind(this));
            }
            if (this.record.deleted || this.record.removed) {
                this.el.css('text-decoration', 'line-through');
            } else {
                this.el.css('text-decoration', 'inherit');
            }
        },
        toggle_row: function() {
            if (this.is_expanded()) {
                this.update_expander(false);
                delete this.tree.expanded[this.path];
                this.collapse_children();
            } else {
                if (this.tree.n_children(this) > Sao.config.limit) {
                    this.tree.record = this.record;
                    this.tree.screen.switch_view('form');
                } else {
                    this.update_expander(true);
                    this.tree.expanded[this.path] = this;
                    this.expand_children();
                }
            }
            return false;
        },
        update_expander: function(expanded) {
            var icon;
            if (expanded) {
                icon = 'tryton-arrow-down';
            } else {
                icon = 'tryton-arrow-right';
            }
            Sao.common.ICONFACTORY.get_icon_url(icon)
                .then(function(url) {
                    this.expander.attr('src', url);
                }.bind(this));
        },
        collapse_children: function() {
            this.rows.forEach(function(row, pos, rows) {
                row.collapse_children();
                var node = row.el[0];
                node.parentNode.removeChild(node);
            });
            this.rows = [];
        },
        expand_children: function(selected, expanded) {
            return this.record.load(this.children_field).done(function() {
                if (this.rows.length === 0) {
                    var children = this.record.field_get_client(
                        this.children_field);
                    children.forEach(function(record, pos, group) {
                        var tree_row = new this.Class(
                            this.tree, record, pos, this);
                        tree_row.construct(selected, expanded);
                        this.rows.push(tree_row);
                    }.bind(this));
                }
                redraw_async(this.rows, selected, expanded);
            }.bind(this));
        },
        switch_row: function() {
            if (window.getSelection) {
                if (window.getSelection().empty) {  // Chrome
                    window.getSelection().empty();
                } else if (window.getSelection().removeAllRanges) {  // Firefox
                    window.getSelection().removeAllRanges();
                }
            } else if (document.selection) {  // IE?
                document.selection.empty();
            }
            if (this.tree.selection_mode != Sao.common.SELECTION_NONE) {
                this.set_selection(true);
                this.selection_changed();
                if (!this.is_selected()) {
                    return;
                }
            }
            this.tree.switch_(this.path);
        },
        select_column: function(index) {
        },
        select_row: function(event_) {
            if (this.tree.selection_mode == Sao.common.SELECTION_NONE) {
                this.tree.select_changed(this.record);
                this.switch_row();
            } else {
                var current_record;
                if (event_.shiftKey &&
                    this.tree.selection_mode != Sao.common.SELECTION_SINGLE) {
                    current_record = this.tree.screen.current_record;
                    this.tree.select_records(current_record, this.record);
                } else {
                    if (!event_.ctrlKey ||
                        this.tree.selection_mode ==
                        Sao.common.SELECTION_SINGLE) {
                        this.tree.select_records(null, null);
                    }
                    this.set_selection(!this.is_selected());
                }
                this.selection_changed();
                if (current_record) {
                    // Keep original current record with shift select
                    this.tree.screen.current_record = current_record;
                }
            }
        },
        is_selected: function() {
            if (this.tree.selection_mode == Sao.common.SELECTION_NONE) {
                return false;
            }
            return this.selection.prop('checked');
        },
        set_selection: function(value) {
            if (this.tree.selection_mode == Sao.common.SELECTION_NONE) {
                return;
            }
            this.selection.prop('checked', value);
            if (value) {
                this.el.addClass('selected');
            } else {
                this.el.removeClass('selected');
            }
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
                        this.tree.selected_records[0] || null);
            }
            this.tree.update_selection();
        },
        expand_to_path: function(path) {
            var row_idx, rest;
            row_idx = path[0];
            rest = path.slice(1);
            if (rest.length > 0) {
                this.rows[row_idx].expand_children().done(function() {
                    this.rows[row_idx].expand_to_path(rest);
                }.bind(this));
            }
        },
        next_column: function(path, editable, sign) {
            var i, readonly, invisible;
            var column, column_index, state_attrs;

            sign = sign || 1;
            if ((path === null) && (sign > 0)) {
                path = -1;
            } else if (path === null) {
                path = 0;
            }
            column_index = 0;
            for (i = 0; i < this.tree.columns.length; i++) {
                column_index = ((path + (sign * (i + 1))) %
                        this.tree.columns.length);
                // javascript modulo returns negative number for negative
                // numbers
                if (column_index < 0) {
                    column_index += this.tree.columns.length;
                }
                column = this.tree.columns[column_index];
                if (!column.field) {
                    continue;
                }
                state_attrs = column.field.get_state_attrs(this.record);
                invisible = state_attrs.invisible;
                if (column.header.is(':hidden')) {
                    invisible = true;
                }
                if (editable) {
                    readonly = (column.attributes.readonly ||
                            state_attrs.readonly);
                } else {
                    readonly = false;
                }
                if (!(invisible || readonly)) {
                    return column_index;
                }
            }
        }
    });

    Sao.View.Tree.RowEditable = Sao.class_(Sao.View.Tree.Row, {
        init: function(tree, record, pos, parent) {
            Sao.View.Tree.RowEditable._super.init.call(this, tree, record, pos,
                parent);
            this.edited_column = null;
            this.el.on('keypress', function(event_) {
                if ((event_.which == Sao.common.RETURN_KEYCODE) &&
                    (this.tree.edited_row != this)) {
                    this.tree.edit_row(this);
                    event_.preventDefault();
                }
            }.bind(this));
        },
        redraw: function(selected, expanded) {
            var i, tr, td, widget;
            var field;

            Sao.View.Tree.RowEditable._super.redraw.call(this, selected,
                    expanded);
            // The autocompletion widget do not call display thus we have to
            // call it when redrawing the row
            for (i = 0; i < this.tree.columns.length; i++) {
                td = this._get_column_td(i);
                tr = td.find('tr');
                widget = jQuery(tr.children('.widget-editable')).data('widget');
                if (widget) {
                    field = this.record.model.fields[widget.field_name];
                    widget.display(this.record, field);
                }
            }
        },
        select_column: function(index) {
            this.edited_column = index;
        },
        select_row: function(event_) {
            var body, listener;
            event_.stopPropagation();
            if (this.tree.edited_row &&
                    (event_.currentTarget == this.tree.edited_row.el[0])) {
                return;
            }

            var current_record = this.tree.screen.current_record;
            if ((this.record != current_record) &&
                !current_record.validate(
                    this.tree.get_fields(), false, false, true)) {
                return;
            }

            body = listener = jQuery(document.body);
            if (body.hasClass('modal-open')) {
                listener = this.tree.el.parents('.modal').last();
            }
            var handler = function(event_) {
                if ((event_.currentTarget == body[0]) &&
                    body.hasClass('modal-open')) {
                    return;
                }

                if (!this.tree.save_row()) {
                    event_.preventDefault();
                    event_.stopPropagation();
                    return;
                }
                body.off('click.sao.editabletree');
                this.tree.edit_row(null);
                return true;
            }.bind(this);
            if (!handler(event_)) {
                return;
            }
            listener.on('click.sao.editabletree', handler);

            Sao.View.Tree.RowEditable._super.select_row.call(this, event_);

            if (!event_.shiftKey && !event_.ctrlKey) {
                this.tree.edit_row(this);
            }
        },
        unset_editable: function() {
            this.tree.columns.forEach(function(col, idx) {
                var td = this._get_column_td(idx);
                var static_el = this.get_static_el(td);
                static_el.html(col.render(this.record)).show();
                this.get_editable_el(td)
                    .empty()
                    .data('widget', null)
                    .parents('.treeview td').addBack().removeClass('edited');
            }.bind(this));
        },
        set_editable: function() {
            var focus_widget = null;
            for (var i = 0, len=this.tree.columns.length; i < len; i++) {
                var td = this._get_column_td(i);
                var col = this.tree.columns[i];
                if (!col.field) {
                    continue;
                }
                var state_attrs = col.field.get_state_attrs(this.record);
                var readonly = col.attributes.readonly;
                if (readonly === undefined) {
                    readonly = state_attrs.readonly;
                    if (readonly === undefined) {
                        readonly = false;
                    }
                }

                var EditableBuilder = Sao.View.EditableTree.WIDGETS[
                    col.attributes.widget];
                if (!readonly && EditableBuilder) {
                    var widget = new EditableBuilder(
                        this.tree, col.attributes);
                    widget.el.on('keydown', this.key_press.bind(this));

                    var editable_el = this.get_editable_el(td);
                    editable_el.append(widget.el);
                    editable_el.data('widget', widget);
                    widget.display(this.record, col.field);

                    var static_el = this.get_static_el(td);
                    static_el.hide();
                    editable_el.show();
                    editable_el.parents('.treeview td').addBack()
                        .addClass('edited');

                    if (this.edited_column == i) {
                        focus_widget = widget;
                    }
                }
            }
            if (focus_widget) {
                focus_widget.focus();
            }
        },
        get_static_el: function(td) {
            td = td || this.get_active_td();
            return td.find('.widget');
        },
        get_editable_el: function(td) {
            td = td || this.get_active_td();
            var editable = td.find('.widget-editable');
            if (!editable.length) {
                editable = jQuery('<td/>', {
                        'class': 'widget-editable'
                    }).insertAfter(td.find('.widget'));
            }
            return editable;
        },
        get_active_td: function() {
            return this._get_column_td(this.edited_column);
        },
        key_press: function(event_) {
            var current_td, selector, next_column, next_idx, i, next_row;
            var states;

            if ((event_.which != Sao.common.TAB_KEYCODE) &&
                    (event_.which != Sao.common.UP_KEYCODE) &&
                    (event_.which != Sao.common.DOWN_KEYCODE) &&
                    (event_.which != Sao.common.ESC_KEYCODE) &&
                    (event_.which != Sao.common.RETURN_KEYCODE)) {
                return;
            }
            var td = this._get_column_td(this.edited_column);
            var editable_el = this.get_editable_el(td);
            var widget = editable_el.data('widget');
            widget.focus_out();
            var column = this.tree.columns[this.edited_column];
            if (column.field.validate(this.record)) {
                if (event_.which == Sao.common.TAB_KEYCODE) {
                    var sign = 1;
                    if (event_.shiftKey) {
                        sign = -1;
                    }
                    event_.preventDefault();
                    next_idx = this.next_column(this.edited_column, true, sign);
                    if (next_idx !== null) {
                        this.edited_column = next_idx;
                        td = this._get_column_td(next_idx);
                        editable_el = this.get_editable_el(td);
                        widget = editable_el.data('widget');
                        widget.focus();
                    }
                } else if (event_.which == Sao.common.UP_KEYCODE ||
                    event_.which == Sao.common.DOWN_KEYCODE ||
                    event_.which == Sao.common.RETURN_KEYCODE) {
                    if (event_.which == Sao.common.UP_KEYCODE) {
                        next_row = this.el.prev('tr');
                    } else if (event_.which == Sao.common.DOWN_KEYCODE) {
                        next_row = this.el.next('tr');
                    } else {
                        if (this.tree.attributes.editable == 'bottom') {
                            next_row = this.el.next('tr');
                        } else {
                            next_row = this.el.prev('tr');
                        }
                    }
                    next_column = this.edited_column;
                    this.record.validate(this.tree.get_fields())
                        .then(function(validate) {
                            if (!validate) {
                                next_row = null;
                                var invalid_fields =
                                    this.record.invalid_fields();
                                for (i = 0; i < this.tree.columns.length; i++) {
                                    var col = this.tree.columns[i];
                                    if (col.attributes.name in invalid_fields) {
                                        next_column = i;
                                        break;
                                    }
                                }
                            } else {
                                var prm = jQuery.when();
                                if (!this.tree.screen.group.parent) {
                                    prm = this.record.save();
                                } else if (this.tree.screen.attributes.pre_validate) {
                                    prm = this.record.pre_validate();
                                }
                                prm.fail(function() {
                                    widget.focus();
                                });
                                if (!next_row.length &&
                                    ((event_.which == Sao.common.RETURN_KEYCODE) ||
                                        ((event_.which == Sao.common.UP_KEYCODE) &&
                                            (this.tree.attributes.editable == 'top')) ||
                                        ((event_.which == Sao.common.DOWN_KEYCODE) &&
                                            (this.tree.attributes.editable == 'bottom')))) {
                                    var model = this.tree.screen.group;
                                    var access = Sao.common.MODELACCESS.get(
                                        this.tree.screen.model_name);
                                    var limit = ((this.tree.screen.size_limit !== null) &&
                                        (model.length >= this.tree.screen.size_limit));
                                    if (access.create && !limit) {
                                        prm = prm.then(function() {
                                            return this.tree.screen.new_();
                                        }.bind(this))
                                            .then(function() {
                                                var rows = this.tree.tbody.children('tr');
                                                if (this.tree.attributes.editable == 'bottom') {
                                                    next_row = rows.last();
                                                } else {
                                                    next_row = rows.first();
                                                }
                                            }.bind(this));
                                    }
                                }
                                return prm;
                            }
                        }.bind(this)).then(function() {
                            window.setTimeout(function() {
                                this._get_column_td(next_column, next_row)
                                    .click()
                                    .find(':input,[tabindex=0]').focus();
                            }.bind(this), 0);
                        }.bind(this));
                } else if (event_.which == Sao.common.ESC_KEYCODE) {
                    this.tree.edit_row(null);
                    this.get_static_el().show().find('[tabindex=0]').focus();
                }
                event_.preventDefault();
            } else {
                widget.display(this.record, column.field);
            }
        }
    });

    Sao.View.Tree.Affix = Sao.class_(Object, {
        init: function(attributes, protocol) {
            this.attributes = attributes;
            this.protocol = protocol || null;
            this.icon = attributes.icon;
            if (this.protocol && !this.icon) {
                this.icon = 'tryton-public';
            }
        },
        get_cell: function() {
            var cell;
            if (this.protocol) {
                cell = jQuery('<a/>', {
                    'target': '_new'
                });
                cell.append(jQuery('<img/>'));
                cell.click({'cell': cell}, this.clicked.bind(this));
            } else if (this.icon) {
                cell = jQuery('<img/>');
            } else {
                cell = jQuery('<span/>');
                cell.attr('tabindex', 0);
            }
            cell.addClass('column-affix');
            return cell;
        },
        render: function(record, cell) {
            if (!cell) {
                cell = this.get_cell();
            }
            var render = function() {
                var value;
                var field = record.model.fields[this.attributes.name];
                var invisible = field.get_state_attrs(record).invisible;
                if (invisible) {
                    cell.hide();
                } else {
                    cell.show();
                }
                if (this.protocol) {
                    value = field.get(record);
                    if (!jQuery.isEmptyObject(value)) {
                        switch (this.protocol) {
                            case 'email':
                                value = 'mailto:' + value;
                                break;
                            case 'callto':
                                value = 'callto:' + value;
                                break;
                            case 'sip':
                                value = 'sip:' + value;
                                break;
                        }
                    }
                    cell.attr('src', value);
                }
                if (this.icon) {
                    if (this.icon in record.model.fields) {
                        var icon_field = record.model.fields[this.icon];
                        value = icon_field.get_client(record);
                    }
                    else {
                        value = this.icon;
                    }
                    Sao.common.ICONFACTORY.get_icon_url(value)
                        .done(function(url) {
                            var img_tag;
                            if (cell.children('img').length) {
                                img_tag = cell.children('img');
                            } else {
                                img_tag = cell;
                            }
                            if (url) {
                                img_tag.attr('src', url);
                            } else {
                                img_tag.removeAttr('src');
                            }
                        }.bind(this));
                } else {
                    value = this.attributes.string || '';
                    if (!value) {
                        value = field.get_client(record) || '';
                    }
                    cell.text(value);
                }
            }.bind(this);
            if (!record.is_loaded(this.attributes.name)) {
                record.load(this.attributes.name).done(render);
            } else {
                render();
            }
            return cell;
        },
        clicked: function(event) {
            event.preventDefault();  // prevent edition
            window.open(event.data.cell.attr('src'), '_blank');
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
            this.header = null;
            this.footers = [];
        },
        get_cell: function() {
            var cell = jQuery('<div/>', {
                'class': this.class_,
                'tabindex': 0
            });
            return cell;
        },
        update_text: function(cell, record) {
            var text = this.field.get_client(record);
            cell.text(text).attr('title', text);
        },
        render: function(record, cell) {
            if (!cell) {
                cell = this.get_cell();
            }
            var render = function() {
                this.update_text(cell, record);
                this.field.set_state(record);
                var state_attrs = this.field.get_state_attrs(record);
                if (state_attrs.invisible) {
                    cell.hide();
                } else {
                    cell.show();
                }
            }.bind(this);
            if (!record.is_loaded(this.attributes.name)) {
                record.load(this.attributes.name).done(render);
            } else {
                render();
            }
            return cell;
        }
    });

    Sao.View.Tree.TextColum = Sao.class_(Sao.View.Tree.CharColumn, {
        class_: 'column-text'
    });

    Sao.View.Tree.IntegerColumn = Sao.class_(Sao.View.Tree.CharColumn, {
        class_: 'column-integer',
        init: function(model, attributes) {
            Sao.View.Tree.IntegerColumn._super.init.call(this, model, attributes);
            this.factor = Number(attributes.factor || 1);
        },
        get_cell: function() {
            return Sao.View.Tree.IntegerColumn._super.get_cell.call(this);
        },
        update_text: function(cell, record) {
            var value = this.field.get_client(record, this.factor);
            cell.text(value).attr('title', value);
        }
    });

    Sao.View.Tree.FloatColumn = Sao.class_(Sao.View.Tree.IntegerColumn, {
        class_: 'column-float'
    });

    Sao.View.Tree.BooleanColumn = Sao.class_(Sao.View.Tree.CharColumn, {
        class_: 'column-boolean',
        get_cell: function() {
            return jQuery('<input/>', {
                'type': 'checkbox',
                'disabled': true,
                'class': this.class_,
                'tabindex': 0
            });
        },
        update_text: function(cell, record) {
            cell.prop('checked', this.field.get(record));
        }
    });

    Sao.View.Tree.Many2OneColumn = Sao.class_(Sao.View.Tree.CharColumn, {
        class_: 'column-many2one',
        get_cell: function() {
            var cell = Sao.View.Tree.Many2OneColumn._super.get_cell.call(this);
            cell.append(jQuery('<a/>', {
                'href': '#',
            }));
            return cell;
        },
        update_text: function(cell, record) {
            cell = cell.children('a');
            cell.unbind('click');
            Sao.View.Tree.Many2OneColumn._super.update_text.call(this, cell, record);
            cell.click(function(event) {
                event.stopPropagation();
                var params = {};
                params.model = this.attributes.relation;
                params.res_id = this.field.get(record);
                params.mode = ['form'];
                params.name = this.attributes.string;
                Sao.Tab.create(params);
            }.bind(this));
        }
    });

    Sao.View.Tree.One2OneColumn = Sao.class_(Sao.View.Tree.Many2OneColumn, {
        class_: 'column-one2one'
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
                    cell.text(text_value).attr('title', text_value);
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
        update_selection: function(record, callback) {
            Sao.common.selection_mixin.update_selection.call(this, record,
                this.field, callback);
        },
        update_text: function(cell, record) {
            this.update_selection(record, function() {
                var value = this.field.get_client(record);
                var model, name, text;
                if (!value) {
                    model = '';
                    name = '';
                } else {
                    model = value[0];
                    name = value[1];
                }
                if (model) {
                    for (var i = 0, len = this.selection.length; i < len; i++) {
                        if (this.selection[i][0] === model) {
                            model = this.selection[i][1];
                            break;
                        }
                    }
                    text = model + ',' + name;
                } else {
                    text = name;
                }
                cell.text(text).attr('title', text);
            }.bind(this));
        }
    });

    Sao.View.Tree.DictColumn = Sao.class_(Sao.View.Tree.CharColumn, {
        class_: 'column-dict',
        update_text: function(cell, record) {
            var text = '(' + Object.keys(this.field.get_client(record)).length + ')';
            cell.text(text).attr('title', text);
        },
    });

    Sao.View.Tree.DateColumn = Sao.class_(Sao.View.Tree.CharColumn, {
        class_: 'column-date',
        update_text: function(cell, record) {
            var value = this.field.get_client(record);
            var date_format = this.field.date_format(record);
            var text = Sao.common.format_date(date_format, value);
            cell.text(text).attr('title', text);
        }
    });

    Sao.View.Tree.TimeColumn = Sao.class_(Sao.View.Tree.CharColumn, {
        class_: 'column-time',
        update_text: function(cell, record) {
            var value = this.field.get_client(record);
            var text = Sao.common.format_time(
                    this.field.time_format(record), value);
            cell.text(text).attr('title', text);
        }
    });

    Sao.View.Tree.TimeDeltaColumn = Sao.class_(Sao.View.Tree.CharColumn, {
        class_: 'column-timedelta'
    });

    Sao.View.Tree.One2ManyColumn = Sao.class_(Sao.View.Tree.CharColumn, {
        class_: 'column-one2many',
        update_text: function(cell, record) {
            var text = '( ' + this.field.get_client(record).length + ' )';
            cell.text(text).attr('title', text);
        }
    });

    Sao.View.Tree.Many2ManyColumn = Sao.class_(Sao.View.Tree.One2ManyColumn, {
        class_: 'column-many2many'
    });

    Sao.View.Tree.BinaryColumn = Sao.class_(Sao.View.Tree.CharColumn, {
        class_: 'column-binary',
        init: function(model, attributes) {
            Sao.View.Tree.BinaryColumn._super.init.call(this, model, attributes);
            this.filename = attributes.filename || null;
        },
        get_cell: function() {
            var cell = Sao.View.Tree.BinaryColumn._super.get_cell.call(this);
            jQuery('<span/>').appendTo(cell);
            return cell;
        },
        update_text: function(cell, record) {
            var size;
            if (this.field.get_size) {
                size = this.field.get_size(record);
            } else {
                size = this.field.get(record).length;
            }
            var text = size? Sao.common.humanize(size) : '';
            cell.children('span').text(text).attr('title', text);
            var button = cell.children('button');
            if (!button.length) {
                button = jQuery('<button/>', {
                    'class': 'btn btn-default btn-sm',
                    'type': 'button',
                }).append(Sao.common.ICONFACTORY.get_icon_img('tryton-save')
                ).appendTo(cell)
                    .click(record, function(event) {
                        // Prevent editable tree to start edition
                        event.stopPropagation();
                        this.save_as(event.data);
                    }.bind(this));
            }
            if (!size) {
                button.hide();
            } else {
                button.show();
            }
        },
        save_as: function(record) {
            var filename;
            var mimetype = 'application/octet-binary';
            var filename_field = record.model.fields[this.filename];
            if (filename_field) {
                filename = filename_field.get_client(record);
                mimetype = Sao.common.guess_mimetype(filename);
            }
            var prm;
            if (this.field.get_data) {
                prm = this.field.get_data(record);
            } else {
                prm = jQuery.when(this.field.get(record));
            }
            prm.done(function(data) {
                Sao.common.download_file(data, filename);
            }.bind(this));
        },
    });

    Sao.View.Tree.ImageColumn = Sao.class_(Sao.View.Tree.CharColumn, {
        class_: 'column-image',
        get_cell: function() {
            var cell = jQuery('<img/>', {
                'class': this.class_,
                'tabindex': 0
            });
            cell.css('width', '100%');
            return cell;
        },
        render: function(record, cell) {
            if (!cell) {
                cell = this.get_cell();
            }
            var render = function() {
                var set_src = function(data) {
                    var img_url, blob;
                    if (!data) {
                        img_url = null;
                    } else {
                        blob = new Blob([data]);
                        img_url = window.URL.createObjectURL(blob);
                    }
                    cell.attr('src', img_url);
                }.bind(this);

                var value = this.field.get_client(record);
                if (value) {
                    if (value > Sao.common.BIG_IMAGE_SIZE) {
                        set_src(null);
                    } else {
                        this.field.get_data(record).done(set_src);
                    }
                } else {
                    set_src(null);
                }
            }.bind(this);
            if (!record.is_loaded(this.attributes.name)) {
                record.load(this.attributes.name).done(render);
            } else {
                render();
            }
            return cell;
        }
    });

    Sao.View.Tree.URLColumn = Sao.class_(Sao.View.Tree.CharColumn, {
        class_: 'column-url',
        render: function(record, cell) {
            cell = Sao.View.Tree.URLColumn._super.render.call(
                    this, record, cell);
            this.field.set_state(record);
            var state_attrs = this.field.get_state_attrs(record);
            if (state_attrs.readonly) {
                cell.hide();
            } else {
                cell.show();
            }
            return cell;
        }
    });

    Sao.View.Tree.ProgressBar = Sao.class_(Sao.View.Tree.CharColumn, {
        class_: 'column-progressbar',
        get_cell: function() {
            var cell = jQuery('<div/>', {
                'class': this.class_ + ' progress',
                'tabindex': 0
            });
            var progressbar = jQuery('<div/>', {
                'class': 'progress-bar',
                'role': 'progressbar',
                'aria-valuemin': 0,
                'aria-valuemax': 100
            }).appendTo(cell);
            progressbar.css('min-width: 2em');
            return cell;
        },
        update_text: function(cell, record) {
            var text = this.field.get_client(record, 100);
            if (text) {
                text = Sao.i18n.gettext('%1%', text);
            }
            var value = this.field.get(record) || 0;
            var progressbar = cell.find('.progress-bar');
            progressbar.attr('aria-valuenow', value * 100);
            progressbar.css('width', value * 100 + '%');
            progressbar.text(text).attr('title', text);
        }
    });

    Sao.View.Tree.ButtonColumn = Sao.class_(Object, {
        init: function(view, attributes) {
            this.view = view;
            this.type = 'button';
            this.attributes = attributes;
        },
        render: function(record, el) {
            var button = new Sao.common.Button(this.attributes, el);
            if (!el) {
                button.el.click(
                        [record, button], this.button_clicked.bind(this));
            }
            var fields = jQuery.map(this.view.screen.model.fields,
                function(field, name) {
                    if ((field.description.loading || 'eager') ==
                        'eager') {
                        return name;
                    } else {
                        return undefined;
                    }
                });
            button.set_state(record);
            return button.el;
        },
        button_clicked: function(event) {
            var record = event.data[0];
            var button = event.data[1];
            if (record != this.view.screen.current_record) {
                // Need to raise the event to get the record selected
                return true;
            }
            var states = record.expr_eval(this.attributes.states || {});
            if (states.invisible || states.readonly) {
                return;
            }
            button.el.prop('disabled', true);
            this.view.screen.button(this.attributes).always(function() {
                button.el.prop('disabled', false);
            });
        }
    });

    Sao.View.TreeXMLViewParser.WIDGETS = {
        'biginteger': Sao.View.Tree.IntegerColumn,
        'binary': Sao.View.Tree.BinaryColumn,
        'boolean': Sao.View.Tree.BooleanColumn,
        'callto': Sao.View.Tree.URLColumn,
        'char': Sao.View.Tree.CharColumn,
        'date': Sao.View.Tree.DateColumn,
        'dict': Sao.View.Tree.DictColumn,
        'email': Sao.View.Tree.URLColumn,
        'float': Sao.View.Tree.FloatColumn,
        'image': Sao.View.Tree.ImageColumn,
        'integer': Sao.View.Tree.IntegerColumn,
        'many2many': Sao.View.Tree.Many2ManyColumn,
        'many2one': Sao.View.Tree.Many2OneColumn,
        'numeric': Sao.View.Tree.FloatColumn,
        'one2many': Sao.View.Tree.One2ManyColumn,
        'one2one': Sao.View.Tree.One2OneColumn,
        'progressbar': Sao.View.Tree.ProgressBar,
        'reference': Sao.View.Tree.ReferenceColumn,
        'selection': Sao.View.Tree.SelectionColumn,
        'sip': Sao.View.Tree.URLColumn,
        'text': Sao.View.Tree.TextColum,
        'time': Sao.View.Tree.TimeColumn,
        'timedelta': Sao.View.Tree.TimeDeltaColumn,
        'url': Sao.View.Tree.URLColumn,
    };

    Sao.View.EditableTree = {};

    Sao.View.EditableTree.editable_mixin = function(widget) {
        var key_press = function(event_) {
            if ((event_.which == Sao.common.TAB_KEYCODE) ||
                    (event_.which == Sao.common.UP_KEYCODE) ||
                    (event_.which == Sao.common.DOWN_KEYCODE) ||
                    (event_.which == Sao.common.ESC_KEYCODE) ||
                    (event_.which == Sao.common.RETURN_KEYCODE)) {
                this.focus_out();
            }
        };
        widget.el.on('keydown', key_press.bind(widget));
    };

    Sao.View.EditableTree.Char = Sao.class_(Sao.View.Form.Char, {
        class_: 'editabletree-char',
        init: function(view, attributes) {
            Sao.View.EditableTree.Char._super.init.call(
                this, view, attributes);
            Sao.View.EditableTree.editable_mixin(this);
        }
    });

    Sao.View.EditableTree.Date = Sao.class_(Sao.View.Form.Date, {
        class_: 'editabletree-date',
        init: function(view, attributes) {
            Sao.View.EditableTree.Date._super.init.call(
                this, view, attributes);
            Sao.View.EditableTree.editable_mixin(this);
        }
    });

    Sao.View.EditableTree.Time = Sao.class_(Sao.View.Form.Time, {
        class_: 'editabletree-time',
        init: function(view, attributes) {
            Sao.View.EditableTree.Time._super.init.call(
                this, view, attributes);
            Sao.View.EditableTree.editable_mixin(this);
        }
    });

    Sao.View.EditableTree.TimeDelta = Sao.class_(Sao.View.Form.TimeDelta, {
        class_: 'editabletree-timedelta',
        init: function(view, attributes) {
            Sao.View.EditableTree.TimeDelta._super.init.call(
                this, view, attributes);
            Sao.View.EditableTree.editable_mixin(this);
        }
    });

    Sao.View.EditableTree.Integer = Sao.class_(Sao.View.Form.Integer, {
        class_: 'editabletree-integer',
        init: function(view, attributes) {
            Sao.View.EditableTree.Integer._super.init.call(
                this, view, attributes);
            Sao.View.EditableTree.editable_mixin(this);
        }
    });

    Sao.View.EditableTree.Float = Sao.class_(Sao.View.Form.Float, {
        class_: 'editabletree-float',
        init: function(view, attributes) {
            Sao.View.EditableTree.Float._super.init.call(
                this, view, attributes);
            Sao.View.EditableTree.editable_mixin(this);
        }
    });

    Sao.View.EditableTree.Selection = Sao.class_(Sao.View.Form.Selection, {
        class_: 'editabletree-selection',
        init: function(view, attributes) {
            Sao.View.EditableTree.Selection._super.init.call(
                this, view, attributes);
            Sao.View.EditableTree.editable_mixin(this);
        }
    });

    Sao.View.EditableTree.Boolean = Sao.class_(Sao.View.Form.Boolean, {
        class_: 'editabletree-boolean',
        init: function(view, attributes) {
            Sao.View.EditableTree.Boolean._super.init.call(
                this, view, attributes);
            Sao.View.EditableTree.editable_mixin(this);
        }
    });

    Sao.View.EditableTree.Many2One = Sao.class_(Sao.View.Form.Many2One, {
        class_: 'editabletree-many2one',
        init: function(view, attributes) {
            Sao.View.EditableTree.Many2One._super.init.call(
                this, view, attributes);
        },
    });

    Sao.View.EditableTree.Reference = Sao.class_(Sao.View.Form.Reference, {
        class_: 'editabletree-reference',
        init: function(view, attributes) {
            Sao.View.EditableTree.Reference._super.init.call(
                this, view, attributes);
        },
    });

    Sao.View.EditableTree.One2One = Sao.class_(Sao.View.Form.One2One, {
        class_: 'editabletree-one2one',
        init: function(view, attributes) {
            Sao.View.EditableTree.One2One._super.init.call(
                this, view, attributes);
        },
    });

    Sao.View.EditableTree.One2Many = Sao.class_(Sao.View.EditableTree.Char, {
        class_: 'editabletree-one2many',
        init: function(view, attributes) {
            Sao.View.EditableTree.One2Many._super.init.call(
                this, view, attributes);
        },
        display: function(record, field) {
            if (record) {
                this.el.val('(' + field.get_client(record).length + ')');
            } else {
                this.el.val('');
            }
        },
        key_press: function(event_) {
            // TODO: remove when key_press is implemented
            if (event_.which == Sao.common.TAB_KEYCODE) {
                this.focus_out();
            }
        },
        set_value: function(record, field) {
        }
    });

    Sao.View.EditableTree.Binary = Sao.class_(Sao.View.Form.Binary, {
        class_: 'editabletree-binary',
        init: function(view, attributes) {
            Sao.View.EditableTree.Binary._super.init.call(
                this, view, attributes);
            Sao.View.EditableTree.editable_mixin(this);
        }
    });

    Sao.View.EditableTree.WIDGETS = {
        'biginteger': Sao.View.EditableTree.Integer,
        'binary': Sao.View.EditableTree.Binary,
        'boolean': Sao.View.EditableTree.Boolean,
        'callto': Sao.View.EditableTree.Char,
        'char': Sao.View.EditableTree.Char,
        'date': Sao.View.EditableTree.Date,
        'email': Sao.View.EditableTree.Char,
        'float': Sao.View.EditableTree.Float,
        'integer': Sao.View.EditableTree.Integer,
        'many2many': Sao.View.EditableTree.Many2Many,
        'many2one': Sao.View.EditableTree.Many2One,
        'numeric': Sao.View.EditableTree.Float,
        'one2many': Sao.View.EditableTree.One2Many,
        'one2one': Sao.View.EditableTree.One2One,
        'reference': Sao.View.EditableTree.Reference,
        'selection': Sao.View.EditableTree.Selection,
        'sip': Sao.View.EditableTree.Char,
        'text': Sao.View.EditableTree.Char,
        'time': Sao.View.EditableTree.Time,
        'timedelta': Sao.View.EditableTree.TimeDelta,
        'url': Sao.View.EditableTree.Char,
    };

}());
