#!/usr/bin/env python2

import sys, os, commands
import gettext
import rfkillMagic
import subprocess
from BlueberrySettingsWidgets import SettingsPage, SettingsBox, SettingsRow
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('GnomeBluetooth', '1.0')
from gi.repository import Gtk, GnomeBluetooth, Gio

BLUETOOTH_DISABLED_PAGE      = "disabled-page"
BLUETOOTH_HW_DISABLED_PAGE   = "hw-disabled-page"
BLUETOOTH_NO_DEVICES_PAGE    = "no-devices-page"
BLUETOOTH_WORKING_PAGE       = "working-page"

# i18n
gettext.install("blueberry", "/usr/share/locale")

class Blueberry(Gtk.Application):
    ''' Create the UI '''
    def __init__(self):

        Gtk.Application.__init__(self, application_id='com.linuxmint.blueberry', flags=Gio.ApplicationFlags.FLAGS_NONE)
        self.window = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
        self.detect_desktop_environment()
        self.connect("activate", self.on_activate)

    def on_activate(self, data=None):
        list = self.get_windows()
        if len(list) > 0:
            # Blueberry is already running, focus the window
            self.get_active_window().present()
        else:
            self.create_window()

    def detect_desktop_environment(self):
        wm_info = commands.getoutput("wmctrl -m")
        if "XDG_CURRENT_DESKTOP" in os.environ:
            xdg_current_desktop = os.environ["XDG_CURRENT_DESKTOP"]
        else:
            xdg_current_desktop = ""

        if "Marco" in wm_info or xdg_current_desktop == "MATE":
            self.de = "Mate"
            self.configuration_tools = {"sound": "mate-volume-control", "keyboard": "mate-keyboard-properties", "mouse": "mate-mouse-properties"}
        elif "Xfwm4" in wm_info or xdg_current_desktop == "XFCE":
            self.de = "Xfce"
            self.configuration_tools = {"keyboard": "xfce4-keyboard-settings", "mouse": "xfce4-mouse-settings"}
            if os.path.exists("/usr/bin/pavucontrol"):
                self.configuration_tools["sound"] = "pavucontrol"
            else:
                self.configuration_tools["sound"] = "xfce4-mixer"
        elif "Muffin" in wm_info or xdg_current_desktop == "X-Cinnamon":
            self.de = "Cinnamon"
            self.configuration_tools = {"sound": "cinnamon-settings sound", "keyboard": "cinnamon-settings keyboard", "mouse": "cinnamon-settings mouse"}
        elif "Mutter" in wm_info or "GNOME" in xdg_current_desktop:
            self.de = "Gnome"
            self.configuration_tools = {"sound": "gnome-control-center sound", "keyboard": "gnome-control-center keyboard", "mouse": "gnome-control-center mouse"}
        elif "Unity" in wm_info or xdg_current_desktop == "Unity":
            self.de = "Unity"
            self.configuration_tools = {"sound": "unity-control-center sound", "keyboard": "unity-control-center keyboard", "mouse": "unity-control-center mouse"}
        elif xdg_current_desktop == "LXDE":
            self.de = "LXDE"
            self.configuration_tools = {"sound": "pavucontrol", "keyboard": "lxinput", "mouse": "lxinput"}
        else:
            self.de = "Unknown"
            print "Warning: DE could not be detected!"
            self.configuration_tools = {}
            if os.path.exists("/usr/bin/pavucontrol"):
                self.configuration_tools["sound"] = "pavucontrol"

    def create_window(self):

        self.window.set_title(_("Bluetooth"))
        self.window.set_icon_name("bluetooth")
        self.window.set_default_size(640, 400)

        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        # Toolbar
        toolbar = Gtk.Toolbar()
        toolbar.get_style_context().add_class("primary-toolbar")
        self.main_box.pack_start(toolbar, False, False, 0)

        self.main_stack = Gtk.Stack()
        self.main_stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self.main_stack.set_transition_duration(150)
        self.main_box.pack_start(self.main_stack, True, True, 0)

        stack_switcher = Gtk.StackSwitcher()
        stack_switcher.set_stack(self.main_stack)

        tool_item = Gtk.ToolItem()
        tool_item.set_expand(True)
        tool_item.get_style_context().add_class("raised")
        toolbar.insert(tool_item, 0)
        switch_holder = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        switch_holder.set_border_width(1)
        tool_item.add(switch_holder)
        switch_holder.pack_start(stack_switcher, True, True, 0)
        stack_switcher.set_halign(Gtk.Align.CENTER)
        toolbar.show_all()

        self.settings = Gio.Settings(schema="org.blueberry")

        debug = False
        if len(sys.argv) > 1 and sys.argv[1] == "debug":
            debug = True

        # Devices
        self.devices_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.devices_box.set_border_width(12)

        self.rf_switch = Gtk.Switch()
        self.rfkill = rfkillMagic.Interface(self.update_ui_callback, debug)
        self.rf_handler_id = self.rf_switch.connect("state-set", self.on_switch_changed)

        self.status_image = Gtk.Image()
        self.status_image.set_from_icon_name("blueberry", Gtk.IconSize.DIALOG)
        self.status_image.show()

        self.stack = Gtk.Stack()
        self.add_stack_page(_("Bluetooth is disabled"), BLUETOOTH_DISABLED_PAGE);
        self.add_stack_page(_("No Bluetooth adapters found"), BLUETOOTH_NO_DEVICES_PAGE);
        self.add_stack_page(_("Bluetooth is disabled by hardware switch"), BLUETOOTH_HW_DISABLED_PAGE);

        self.lib_widget = GnomeBluetooth.SettingsWidget.new();
        self.lib_widget.connect("panel-changed", self.panel_changed);
        self.stack.add_named(self.lib_widget, BLUETOOTH_WORKING_PAGE)
        self.lib_widget.show()
        self.stack.show();

        switchbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        hbox.pack_end(self.rf_switch, False, False, 10)
        switchbox.pack_start(hbox, False, False, 0)
        switchbox.pack_start(self.status_image, False, False, 0)
        switchbox.show_all()

        self.devices_box.pack_start(switchbox, False, False, 0)
        self.devices_box.pack_start(self.stack, True, True, 0)

        self.main_stack.add_titled(self.devices_box, "devices", _("Devices"))

        # Settings

        page = SettingsPage()

        section = page.add_section(_("Bluetooth settings"))
        self.adapter_name_entry = Gtk.Entry()
        adapter_name = self.get_default_adapter_name()
        if adapter_name is not None:
            self.adapter_name_entry.set_text(adapter_name)
        self.adapter_name_entry.connect("changed", self.on_adapter_name_changed)
        row = SettingsRow(Gtk.Label(_("Name")), self.adapter_name_entry)
        row.set_tooltip_text(_("This is the Bluetooth name of your computer"))
        section.add_row(row)

        self.obex_switch = Gtk.Switch()
        self.obex_switch.set_active(self.settings.get_boolean("obex-enabled"))
        self.obex_switch.connect("notify::active", self.on_obex_switch_toggled)
        self.settings.connect("changed", self.on_settings_changed)
        row = SettingsRow(Gtk.Label(label=_("Receive files from remote devices")), self.obex_switch)
        row.set_tooltip_text(_("This option allows your computer to receive files transferred over Bluetooth (OBEX)"))
        section.add_row(row)

        self.tray_switch = Gtk.Switch()
        self.tray_switch.set_active(self.settings.get_boolean("tray-enabled"))
        self.tray_switch.connect("notify::active", self.on_tray_switch_toggled)
        self.settings.connect("changed", self.on_settings_changed)
        section.add_row(SettingsRow(Gtk.Label(label=_("Show a tray icon")), self.tray_switch))

        self.window.add(self.main_box)

        self.main_stack.add_titled(page, "settings", _("Settings"))

        self.devices_box.show_all()

        self.update_ui_callback()

        self.add_window(self.window)
        self.window.show_all()

        self.client = GnomeBluetooth.Client()
        self.model = self.client.get_model()
        self.model.connect('row-changed', self.update_status)
        self.model.connect('row-deleted', self.update_status)
        self.model.connect('row-inserted', self.update_status)
        self.update_status()

    def panel_changed(self, widget, panel):
        if not panel in self.configuration_tools:
            print "Warning, no configuration tool known for panel '%s'" % panel
        else:
            os.system("%s &" % self.configuration_tools[panel])

    def on_tray_switch_toggled(self, widget, data=None):
        if widget.get_active():
            self.settings.set_boolean("tray-enabled", True)
            subprocess.Popen(["blueberry-tray"])
        else:
            self.settings.set_boolean("tray-enabled", False)

    def on_obex_switch_toggled(self, widget, data=None):
        if widget.get_active():
            self.settings.set_boolean("obex-enabled", True)
            os.system("/usr/lib/blueberry/blueberry-obex-agent.py &")
        else:
            self.settings.set_boolean("obex-enabled", False)
            os.system("killall -9 blueberry-obex-agent");
        self.update_status()

    def on_adapter_name_changed(self, entry):
        subprocess.call(["bt-adapter", "--set", "Alias", entry.get_text()])
        self.update_status()

    def on_settings_changed(self, settings, key):
        self.tray_switch.set_active(self.settings.get_boolean("tray-enabled"))
        self.obex_switch.set_active(self.settings.get_boolean("obex-enabled"))

    def add_stack_page(self, message, name):
        label = Gtk.Label(label=message)
        self.stack.add_named(label, name)
        label.show()

    def get_default_adapter_name(self):
        name = None
        try:
            output = subprocess.check_output(["bt-adapter", "-i"]).strip()
            for line in output.split("\n"):
                line = line.strip()
                if line.startswith("Alias: "):
                    name = line.replace("Alias: ", "").replace(" [rw]", "").replace(" [ro]", "")
                    break
        except Exception as cause:
            print ("Could not retrieve the BT adapter name with 'bt-adapter -i': %s" % cause)
        return name

    def update_status(self, path=None, iter=None, data=None):
        try:
            # In version 3.18, gnome_bluetooth_settings_widget
            # doesn't give explicit access to its label via gi
            # but it's a composite widget and its hierarchy is:
            # scrolledwindow -> viewport -> vbox -> explanation-label
            scrolledwindow = self.lib_widget.get_children()[0]
            scrolledwindow.set_shadow_type(Gtk.ShadowType.NONE)
            viewport = scrolledwindow.get_children()[0]
            vbox = viewport.get_children()[0]
            explanation_label = vbox.get_children()[0]
            name = self.get_default_adapter_name()
            if name is not None:
                if self.settings.get_boolean('obex-enabled'):
                    text = _("Visible as %s and available for Bluetooth file transfers.")
                else:
                    text = _("Visible as %s.")
                text = "%s\n" % text
                explanation_label.set_markup(text % "\"%s\"" % name)
            else:
                explanation_label.set_label("")
        except Exception as e:
            print (e)
            return None

    def update_ui_callback(self):
        powered = False
        sensitive = False
        page = ""

        if not self.rfkill.have_adapter:
            page = BLUETOOTH_NO_DEVICES_PAGE
            self.status_image.set_from_icon_name("blueberry-disabled", Gtk.IconSize.DIALOG)
        elif self.rfkill.hard_block:
            page = BLUETOOTH_HW_DISABLED_PAGE
            self.status_image.set_from_icon_name("blueberry-disabled", Gtk.IconSize.DIALOG)
        elif self.rfkill.soft_block:
            page = BLUETOOTH_DISABLED_PAGE
            sensitive = True
            self.status_image.set_from_icon_name("blueberry-disabled", Gtk.IconSize.DIALOG)
        else:
            page = BLUETOOTH_WORKING_PAGE
            sensitive = True
            powered = True
            self.status_image.set_from_icon_name("blueberry", Gtk.IconSize.DIALOG)

        self.rf_switch.set_sensitive(sensitive)

        self.rf_switch.handler_block(self.rf_handler_id)
        self.rf_switch.set_state(powered)
        self.rf_switch.handler_unblock(self.rf_handler_id)

        self.stack.set_visible_child_name (page);

    def on_switch_changed(self, widget, state):
        self.rfkill.try_set_blocked(not state)
        return True

if __name__ == "__main__":
    app = Blueberry()
    app.run(None)
