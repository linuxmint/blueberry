#!/usr/bin/python3

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

def list_header_func(row, before, user_data):
    if before and not row.get_header():
        row.set_header(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

class SettingsBox(Gtk.Frame):

    def __init__(self, title=""):
        Gtk.Frame.__init__(self)
        self.set_shadow_type(Gtk.ShadowType.IN)
        frame_style = self.get_style_context()
        frame_style.add_class("view")

        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.add(self.box)

        if title != "":
            toolbar = Gtk.Toolbar.new()
            Gtk.StyleContext.add_class(Gtk.Widget.get_style_context(toolbar), "cs-header")

            label = Gtk.Label.new()
            label.set_markup("<b>%s</b>" % title)
            title_holder = Gtk.ToolItem()
            title_holder.add(label)
            toolbar.add(title_holder)
            self.box.add(toolbar)

            toolbar_separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
            self.box.add(toolbar_separator)
            separator_context = toolbar_separator.get_style_context()
            frame_color = frame_style.get_border_color(Gtk.StateFlags.NORMAL).to_string()
            css_provider = Gtk.CssProvider()
            css_provider.load_from_data(".separator {{ -GtkWidget-wide-separators: 0; \
                                                    color: {};                    \
                                                    }}".format(frame_color).encode())
            separator_context.add_provider(css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        self.list_box = Gtk.ListBox()
        self.list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        self.list_box.set_header_func(list_header_func, None)
        self.box.add(self.list_box)

    def add_row(self, row):
        self.list_box.add(row)


class SettingsRow(Gtk.ListBoxRow):

    def __init__(self, label, main_widget, alternative_widget=None):

        self.main_widget = main_widget
        self.alternative_widget = alternative_widget
        self.label = label
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self.stack.set_transition_duration(1000)

        self.stack.add_named(main_widget, "main_widget")
        if alternative_widget is not None:
            self.stack.add_named(self.alternative_widget, "alternative_widget")

        Gtk.ListBoxRow.__init__(self)

        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        hbox.set_border_width(5)
        hbox.set_margin_left(20)
        hbox.set_margin_right(20)
        self.add(hbox)

        grid = Gtk.Grid()
        grid.set_column_spacing(15)
        hbox.pack_start(grid, True, True, 0)

        self.description_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.description_box.props.hexpand = True
        self.description_box.props.halign = Gtk.Align.START
        self.description_box.props.valign = Gtk.Align.CENTER
        self.label.props.xalign = 0.0
        self.description_box.add(self.label)

        grid.attach(self.description_box, 0, 0, 1, 1)
        grid.attach_next_to(self.stack, self.description_box, Gtk.PositionType.RIGHT, 1, 1)

    def show_alternative_widget(self):
        if self.alternative_widget is not None:
            self.stack.set_visible_child(self.alternative_widget)