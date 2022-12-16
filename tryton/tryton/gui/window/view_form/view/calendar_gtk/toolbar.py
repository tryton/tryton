# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
import calendar
import gettext

from gi.repository import Gdk, Gtk

from tryton.gui import Main
from tryton.common import IconFactory
from tryton.common.datetime_ import popup_position, popup_show, popup_hide

_ = gettext.gettext


class Toolbar(Gtk.Toolbar):

    def __init__(self, goocalendar):
        super(Toolbar, self).__init__()
        self.goocalendar = goocalendar
        self.accel_group = Main().accel_group

        today_button = Gtk.ToolButton()
        today_button.set_label(_('Today'))
        today_button.set_homogeneous(False)
        today_button.connect("clicked", self.on_today_button_clicked)
        today_button.add_accelerator(
            "clicked", self.accel_group, Gdk.KEY_t,
            Gdk.ModifierType.MODIFIER_MASK, Gtk.AccelFlags.VISIBLE)
        self.insert(today_button, -1)

        arrow_left = IconFactory.get_image('tryton-arrow-left')
        go_back = Gtk.ToolButton()
        go_back.set_icon_widget(arrow_left)
        go_back.set_label(_("go back"))
        go_back.set_expand(False)
        go_back.set_homogeneous(False)
        go_back.connect("clicked", self.on_go_back_clicked)
        self.insert(go_back, -1)

        self.current_page_label = Gtk.Label(
            width_chars=10, max_width_chars=10, ellipsize=True)
        self.current_page = Gtk.ToggleToolButton()
        self.current_page.set_label_widget(self.current_page_label)
        self.current_page.connect("clicked", self.on_current_page_clicked)
        self.insert(self.current_page, -1)

        self.__cal_popup = Gtk.Window(type=Gtk.WindowType.POPUP)
        self.__cal_popup.set_events(
            self.__cal_popup.get_events() | Gdk.EventMask.KEY_PRESS_MASK)
        self.__cal_popup.set_resizable(False)
        self.__cal_popup.connect('delete-event', self.on_cal_popup_closed)
        self.__cal_popup.connect(
            'key-press-event', self.on_cal_popup_key_pressed)
        self.__cal_popup.connect(
            'button-press-event', self.on_cal_popup_button_pressed)

        gtkcal = Gtk.Calendar()
        gtkcal.connect('day-selected', self.on_gtkcal_day_selected)
        gtkcal.connect(
            'day-selected-double-click',
            self.on_gtkcal_day_selected_double_click)
        gtkcal.set_display_options(
            Gtk.CalendarDisplayOptions.SHOW_HEADING
            | Gtk.CalendarDisplayOptions.SHOW_WEEK_NUMBERS
            | Gtk.CalendarDisplayOptions.SHOW_DAY_NAMES)
        gtkcal.set_no_show_all(True)
        self.__cal_popup.add(gtkcal)
        gtkcal.show()
        self.gtkcal = gtkcal
        self.goocalendar.connect('day-selected',
            self.on_goocalendar_day_selected)

        arrow_right = IconFactory.get_image('tryton-arrow-right')
        go_forward = Gtk.ToolButton()
        go_forward.set_icon_widget(arrow_right)
        go_forward.set_label(_("go forward"))
        go_forward.set_expand(False)
        go_forward.set_homogeneous(False)
        go_forward.connect("clicked", self.on_go_forward_clicked)
        self.insert(go_forward, -1)

        arrow_left = IconFactory.get_image('tryton-arrow-left')
        previous_year = Gtk.ToolButton()
        previous_year.set_icon_widget(arrow_left)
        previous_year.set_label(_("previous year"))
        previous_year.set_expand(False)
        previous_year.set_homogeneous(False)
        previous_year.connect("clicked", self.on_previous_year_clicked)
        self.insert(previous_year, -1)

        self.current_year_label = Gtk.Label(width_chars=4)
        current_year = Gtk.ToolItem()
        current_year.add(self.current_year_label)
        self.insert(current_year, -1)

        arrow_right = IconFactory.get_image('tryton-arrow-right')
        next_year = Gtk.ToolButton()
        next_year.set_icon_widget(arrow_right)
        next_year.set_label(_("next year"))
        next_year.set_expand(False)
        next_year.set_homogeneous(False)
        next_year.connect("clicked", self.on_next_year_clicked)
        self.insert(next_year, -1)

        blank_widget = Gtk.ToolItem()
        blank_widget.set_expand(True)
        self.insert(blank_widget, -1)

        day_button = Gtk.RadioToolButton()
        day_button.set_label(_('Day View'))
        day_button.connect("clicked", self.on_day_button_clicked)
        day_button.add_accelerator(
            "clicked", self.accel_group, Gdk.KEY_d,
            Gdk.ModifierType.MODIFIER_MASK, Gtk.AccelFlags.VISIBLE)
        self.insert(day_button, -1)

        week_button = Gtk.RadioToolButton.new_from_widget(day_button)
        week_button.set_label(_('Week View'))
        week_button.connect("clicked", self.on_week_button_clicked)
        week_button.add_accelerator(
            "clicked", self.accel_group, Gdk.KEY_w,
            Gdk.ModifierType.MODIFIER_MASK, Gtk.AccelFlags.VISIBLE)
        self.insert(week_button, -1)

        month_button = Gtk.RadioToolButton.new_from_widget(week_button)
        month_button.set_label_widget(Gtk.Label(label=_('Month View')))
        month_button.connect("clicked", self.on_month_button_clicked)
        month_button.add_accelerator(
            "clicked", self.accel_group, Gdk.KEY_m,
            Gdk.ModifierType.MODIFIER_MASK, Gtk.AccelFlags.VISIBLE)
        self.insert(month_button, -1)
        buttons = {
            'month': month_button,
            'week': week_button,
            'day': day_button,
            }
        buttons[self.goocalendar.view].set_active(True)
        self.update_displayed_date()
        self.set_style(Gtk.ToolbarStyle.ICONS)

    def update_displayed_date(self):
        date = self.goocalendar.selected_date
        year = date.timetuple()[0]
        month = date.timetuple()[1]
        day = date.timetuple()[2]
        month_label = calendar.month_name[month]
        self.current_year_label.set_text(str(year))

        if self.goocalendar.view == "month":
            self.current_page_label.set_text(month_label)
        elif self.goocalendar.view == "week":
            week_number = datetime.date(year, month, day).isocalendar()[1]
            new_label = _('Week') + ' ' + str(week_number)
            new_label += ' (' + month_label + ')'
            self.current_page_label.set_text(new_label)
        elif self.goocalendar.view == "day":
            new_label = date.strftime('%x')
            self.current_page_label.set_text(new_label)

    def on_today_button_clicked(self, widget):
        self.goocalendar.select(datetime.date.today())

    def on_go_back_clicked(self, widget):
        self.goocalendar.previous_page()

    def on_current_page_clicked(self, widget):
        if widget.get_active():
            self.__cal_popup.set_transient_for(widget.get_toplevel())
            popup_position(widget, self.__cal_popup)
            popup_show(self.__cal_popup)

    def on_cal_popup_closed(self, widget):
        self.cal_popup_hide()
        return True

    def on_cal_popup_key_pressed(self, widget, event):
        if event.keyval != Gdk.KEY_Escape:
            return False
        widget.stop_emission_by_name('key-press-event')
        self.cal_popup_hide()
        return True

    def on_cal_popup_button_pressed(self, widget, event):
        child = event.window
        if child != widget.props.window:
            while child:
                if child == widget.props.window:
                    return False
                child = child.get_parent()
        self.cal_popup_hide()
        return True

    def cal_popup_hide(self):
        popup_hide(self.__cal_popup)
        self.current_page.set_active(False)

    def on_gtkcal_day_selected(self, gtkcal):
        year, month, day = gtkcal.get_date()
        month += 1  # months go from 1 to 12 instead of from 0 to 11
        self.goocalendar.select(datetime.date(year, month, day))

    def on_gtkcal_day_selected_double_click(self, gtkcal):
        self.cal_popup_hide()

    def on_goocalendar_day_selected(self, goocalendar, day):
        # months go from 0 to 11 in Gtk.Calendar instead of 1 to 12
        new_date = self.goocalendar.selected_date
        self.gtkcal.select_month(new_date.month - 1, new_date.year)
        self.gtkcal.handler_block_by_func(self.on_gtkcal_day_selected)
        self.gtkcal.select_day(new_date.day)
        self.gtkcal.handler_unblock_by_func(self.on_gtkcal_day_selected)

    def on_go_forward_clicked(self, widget):
        self.goocalendar.next_page()

    def on_previous_year_clicked(self, widget):
        date = datetime.datetime.combine(self.goocalendar.selected_date,
            datetime.time(0))
        year, month, day = date.timetuple()[:3]
        year -= 1
        cal = calendar.Calendar(self.goocalendar.firstweekday)
        next_month_days = [d for d in cal.itermonthdays(year, month)]
        if day not in next_month_days:
            day = max(next_month_days)
        self.goocalendar.select(datetime.datetime(year, month, day))

    def on_next_year_clicked(self, widget):
        date = datetime.datetime.combine(self.goocalendar.selected_date,
            datetime.time(0))
        year, month, day = date.timetuple()[:3]
        year += 1
        cal = calendar.Calendar(self.goocalendar.firstweekday)
        next_month_days = [d for d in cal.itermonthdays(year, month)]
        if day not in next_month_days:
            day = max(next_month_days)
        self.goocalendar.select(datetime.datetime(year, month, day))

    def on_day_button_clicked(self, widget):
        self.goocalendar.set_view("day")

    def on_week_button_clicked(self, widget):
        self.goocalendar.set_view("week")

    def on_month_button_clicked(self, widget):
        self.goocalendar.set_view("month")
