# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
import calendar
import gettext
import gtk
import goocanvas
from tryton.gui import Main

_ = gettext.gettext


class Toolbar(gtk.Toolbar):

    def __init__(self, goocalendar):
        super(Toolbar, self).__init__()
        self.goocalendar = goocalendar
        self.accel_group = Main.get_main().accel_group

        today_label = gtk.Label(_('Today'))
        today_button = gtk.ToolButton(today_label)
        today_button.set_homogeneous(False)
        today_button.connect("clicked", self.on_today_button_clicked)
        today_button.add_accelerator("clicked", self.accel_group,
            gtk.keysyms.t, gtk.gdk.MODIFIER_MASK, gtk.ACCEL_VISIBLE)
        self.insert(today_button, -1)

        arrow_left = gtk.Arrow(gtk.ARROW_LEFT, gtk.SHADOW_NONE)
        go_back = gtk.ToolButton(arrow_left, "go left")
        go_back.set_expand(False)
        go_back.set_homogeneous(False)
        go_back.connect("clicked", self.on_go_back_clicked)
        self.insert(go_back, -1)

        self.current_page_label = gtk.Label("")
        self.current_page = gtk.ToggleToolButton()
        self.current_page.set_icon_widget(self.current_page_label)
        self.current_page.connect("clicked", self.on_current_page_clicked)
        self.insert(self.current_page, -1)

        gtkcal = gtk.Calendar()
        gtkcal.connect('day-selected', self.on_gtkcal_day_selected)
        gtkcal.set_display_options(
            gtk.CALENDAR_SHOW_HEADING |
            gtk.CALENDAR_SHOW_WEEK_NUMBERS |
            gtk.CALENDAR_SHOW_DAY_NAMES)
        gtkcal.set_no_show_all(True)
        gtkcal_item = goocanvas.Widget(widget=gtkcal)
        gtkcal_item.set_property('visibility', goocanvas.ITEM_INVISIBLE)
        goocalendar.get_root_item().add_child(gtkcal_item)
        self.gtkcal = gtkcal
        self.gtkcal_item = gtkcal_item
        self.goocalendar.connect('day-selected',
            self.on_goocalendar_day_selected)

        arrow_right = gtk.Arrow(gtk.ARROW_RIGHT, gtk.SHADOW_NONE)
        go_forward = gtk.ToolButton(arrow_right, "go right")
        go_forward.set_expand(False)
        go_forward.set_homogeneous(False)
        go_forward.connect("clicked", self.on_go_forward_clicked)
        self.insert(go_forward, -1)

        arrow_left = gtk.Arrow(gtk.ARROW_LEFT, gtk.SHADOW_NONE)
        previous_year = gtk.ToolButton(arrow_left, "next year")
        previous_year.set_expand(False)
        previous_year.set_homogeneous(False)
        previous_year.connect("clicked", self.on_previous_year_clicked)
        self.insert(previous_year, -1)

        self.current_year_label = gtk.Label("")
        current_year = gtk.ToolItem()
        current_year.add(self.current_year_label)
        self.insert(current_year, -1)

        arrow_right = gtk.Arrow(gtk.ARROW_RIGHT, gtk.SHADOW_NONE)
        next_year = gtk.ToolButton(arrow_right, "next year")
        next_year.set_expand(False)
        next_year.set_homogeneous(False)
        next_year.connect("clicked", self.on_next_year_clicked)
        self.insert(next_year, -1)

        blank_widget = gtk.ToolItem()
        blank_widget.set_expand(True)
        self.insert(blank_widget, -1)

        week_button = gtk.RadioToolButton()
        week_button.set_label(_('Week View'))
        week_button.connect("clicked", self.on_week_button_clicked)
        week_button.add_accelerator("clicked", self.accel_group, gtk.keysyms.w,
            gtk.gdk.MODIFIER_MASK, gtk.ACCEL_VISIBLE)
        self.insert(week_button, -1)

        month_button = gtk.RadioToolButton(week_button)
        month_button.set_label(_('Month View'))
        month_button.connect("clicked", self.on_month_button_clicked)
        month_button.add_accelerator("clicked", self.accel_group,
            gtk.keysyms.m, gtk.gdk.MODIFIER_MASK, gtk.ACCEL_VISIBLE)
        month_button.set_active(True)
        self.insert(month_button, -1)
        self.update_displayed_date()
        self.set_style(gtk.TOOLBAR_ICONS)

    def update_displayed_date(self):
        date = self.goocalendar.selected_date
        year = date.timetuple()[0]
        month = date.timetuple()[1]
        day = date.timetuple()[2]
        self.current_year_label.set_text(str(year))

        if self.goocalendar.view == "month":
            new_label = calendar.month_name[month]
            self.current_page_label.set_text(new_label)
        elif self.goocalendar.view == "week":
            week_number = datetime.date(year, month, day).isocalendar()[1]
            new_label = _('Week') + ' ' + str(week_number)
            new_label += ' (' + calendar.month_name[month] + ')'
            self.current_page_label.set_text(new_label)

    def on_today_button_clicked(self, widget):
        self.goocalendar.select(datetime.date.today())

    def on_go_back_clicked(self, widget):
        self.goocalendar.previous_page()

    def on_current_page_clicked(self, widget):
        gtkcal_item = self.gtkcal_item
        if gtkcal_item.get_property('visibility') == goocanvas.ITEM_VISIBLE:
            gtkcal_item.set_property('visibility', goocanvas.ITEM_INVISIBLE)
        else:
            gtkcal_item.set_property('visibility', goocanvas.ITEM_VISIBLE)

    def on_gtkcal_day_selected(self, gtkcal):
        year, month, day = gtkcal.get_date()
        month += 1  # months go from 1 to 12 instead of from 0 to 11
        self.goocalendar.select(datetime.date(year, month, day))

    def on_goocalendar_day_selected(self, goocalendar, day):
        # months go from 0 to 11 in gtk.Calendar instead of 1 to 12
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

    def on_week_button_clicked(self, widget):
        self.goocalendar.set_view("week")

    def on_month_button_clicked(self, widget):
        self.goocalendar.set_view("month")
