/* This file is part of Tryton.  The COPYRIGHT file at the top level of
   this repository contains the full copyright notices and license terms. */
(function() {
    'use strict';

    Sao.View.ListGroupViewForm = Sao.class_(Sao.View.Form, {
        get record() {
            return this._record;
        },
        set record(value) {
            this._record = value;
        },
        button_clicked: function(event) {
            if (Sao.common.compare(this.screen.selected_records, [this.record])) {
                Sao.View.ListGroupViewForm._super.button_clicked.call(this, event);
            }
        }
    });

    Sao.View.ListForm = Sao.class_(Sao.View, {
        editable: true,
        creatable: true,
        view_type: 'list-form',
        init: function(view_id, screen, xml) {
            Sao.View.ListForm._super.init.call(this, view_id, screen, xml);
            if (this.attributes.creatable) {
                this.creatable = Boolean(parseInt(this.attributes.creatable, 10));
            }

            this.form_xml = xml;
            this.el = jQuery('<ul/>', {
                'class': 'list-group list-form'
            });
            this._view_forms = [];
        },
        display: function(selected_nodes) {
            var record, view_form, view_form_frame, to_delete;
            var deferreds = [];
            var new_elements = [];
            var selected = new Set();
            if (!jQuery.isEmptyObject(selected_nodes)) {
                for (const id_path of selected_nodes) {
                    selected.add(id_path[0]);
                }
            }
            for (var i = 0; i < this.group.length; i++) {
                record = this.group[i];
                view_form = this._view_forms[i];
                if (!view_form) {
                    view_form_frame = this._create_form(record);
                    new_elements.push(view_form_frame);
                    view_form = this._view_forms[this._view_forms.length - 1];
                } else {
                    view_form_frame = view_form.el.parent();
                    view_form.record = record;
                }

                if (~this.group.record_deleted.indexOf(record) ||
                        ~this.group.record_removed.indexOf(record)) {
                    view_form_frame.addClass('disabled');
                } else {
                    view_form_frame.removeClass('disabled');
                }
                if ((this.record === record) || selected.has(record.id)) {
                    view_form_frame.addClass('list-group-item-selected');
                } else {
                    view_form_frame.removeClass('list-group-item-selected');
                }
                deferreds.push(view_form.display());
            }
            if (new_elements.length > 0) {
                this.el.append(new_elements);
            }
            to_delete = this._view_forms.splice(this.group.length);
            jQuery(to_delete.map(function (vf) { return vf.el[0]; }))
                .parent().detach();
            return jQuery.when.apply(jQuery, deferreds);
        },
        get_selected_paths: function() {
            var paths = [];
            var view_form_frame;
            for (const form of this._view_forms) {
                view_form_frame = form.el.parent();
                if (view_form_frame.hasClass('list-group-item-selected')) {
                    paths.push([form.record.id]);
                }
            }
            return paths;
        },
        _create_form: function(record) {
            var view_form = new Sao.View.ListGroupViewForm(
                this.view_id, this.screen, this.form_xml);
            view_form.record = record;
            this._view_forms.push(view_form);
            var frame = jQuery('<li/>', {
                'class': 'list-group-item list-form-item'
            });
            frame.append(view_form.el);
            frame.click(
                this._view_forms.length - 1, this._select_row.bind(this));
            return frame;
        },
        get selected_records() {
            var records = [];
            for (const view_form of this._view_forms) {
                const frame = view_form.el.parent();
                if (frame.hasClass('list-group-item-selected')) {
                    records.push(view_form.record);
                }
            }
            return records;
        },
        get listed_records() {
            return this.group.slice();
        },
        set_cursor: function(new_, reset_view) {
            if (new_) {
                this.el.animate({
                    scrollTop: this.el[0].scrollHeight
                });
            }
        },
        select_records: function(from, to) {
            jQuery(this._view_forms.map(function (vf) { return vf.el[0]; }))
                .parent().removeClass('list-group-item-selected');
            if ((from === null) && (to === null)) {
                return;
            }

            if (!from) {
                from = 0;
            }
            if (!to) {
                to = 0;
            }
            if (to < from) {
                var tmp = from;
                from = to;
                to = tmp;
            }

            for (const form of this._view_forms.slice(from, to + 1)) {
                form.el.parent().addClass('list-group-item-selected');
            }
        },
        _select_row: function(event_) {
            var next_form_idx = event_.data;
            var next_view_form = this._view_forms[next_form_idx];

            var prm = jQuery.when();
            if (this.record && (next_view_form.record != this.record)) {
                if (!this.screen.group.parent) {
                    if (!this.record.validate(
                            this.get_fields(), false, false, false)) {
                        prm = jQuery.Deferred().reject();
                    } else {
                        prm = this.record.save();
                    }
                } else if (this.screen.attributes.pre_validate) {
                    prm = this.record.pre_validate();
                }
            }

            prm.done(() => {
                var current_view_form;

                if (event_.shiftKey) {
                    let i = 0;
                    for (const other_view_form of this._view_forms) {
                        if (other_view_form.record === this.record) {
                            current_view_form = other_view_form;
                            break;
                        }
                        i++;
                    }
                    this.select_records(i, next_form_idx);
                } else {
                    if (!(event_.ctrlKey || event_.metaKey)) {
                        this.select_records(null, null);
                    }
                    this.record = next_view_form.record;
                    next_view_form.el.parent()
                        .toggleClass('list-group-item-selected');
                }
                if (current_view_form) {
                    this.record = current_view_form.record;
                }
            });
        }
    });

}());
