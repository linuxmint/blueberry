#!/usr/bin/env python2

import sys
import gettext
from gi.repository import Gtk, GnomeBluetooth, Gio
import rfkillMagic
import subprocess

BLUETOOTH_DISABLED_PAGE      = "disabled-page"
BLUETOOTH_HW_DISABLED_PAGE   = "hw-disabled-page"
BLUETOOTH_NO_DEVICES_PAGE    = "no-devices-page"
BLUETOOTH_WORKING_PAGE       = "working-page"

RFKILL_CHK = ["/usr/sbin/rfkill", "list", "bluetooth"]
RFKILL_BLOCK = ["/usr/sbin/rfkill", "block", "bluetooth"]
RFKILL_UNBLOCK = ["/usr/sbin/rfkill", "unblock", "bluetooth"]

SETTINGS_SCHEMA = "org.blueberry"
TRAY_KEY = "tray-enabled"

# i18n
gettext.install("blueberry", "/usr/share/locale")

class BluetoothConfig:
    ''' Create the UI '''
    def __init__(self):
        self.window = Gtk.Window(Gtk.WindowType.TOPLEVEL)

        self.window.set_title(_("Bluetooth"))
        self.window.set_icon_name("bluetooth")
        self.window.connect("destroy", self.terminate)
        self.window.set_default_size(640, 480)

        self.main_box = Gtk.VBox()
        self.stack = Gtk.Stack()
        self.rf_switch = Gtk.Switch()

        self.add_stack_page(_("Bluetooth is disabled"), BLUETOOTH_DISABLED_PAGE);
        self.add_stack_page(_("No Bluetooth adapters found"), BLUETOOTH_NO_DEVICES_PAGE);
        self.add_stack_page(_("Bluetooth is disabled by hardware switch"), BLUETOOTH_HW_DISABLED_PAGE);

        self.lib_widget = GnomeBluetooth.SettingsWidget.new();

        self.stack.add_named(self.lib_widget, BLUETOOTH_WORKING_PAGE)

        self.lib_widget.show()
        self.stack.show();
        self.main_box.show();

        switchbox = Gtk.HBox()
        switchbox.pack_end(self.rf_switch, False, False, 6)
        switchbox.show_all()

        self.main_box.pack_start(switchbox, False, False, 6)
        self.main_box.pack_start(self.stack, True, True, 6)

        frame = Gtk.Frame()
        frame.add(self.main_box)
        frame.set_border_width(6)
        frame.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
        frame.show()

        self.window.add(frame)

        debug = False
        if len(sys.argv) > 1 and sys.argv[1] == "debug":
            debug = True

        self.rfkill = rfkillMagic.Interface(self.update_ui_callback, debug)
        self.rf_handler_id = self.rf_switch.connect("state-set", self.on_switch_changed)

        self.settings = Gio.Settings(SETTINGS_SCHEMA)

        traybox = Gtk.HBox()
        self.traybutton = Gtk.CheckButton(label=_("Show a tray icon when bluetooth is enabled"))
        self.traybutton.set_active(self.settings.get_boolean(TRAY_KEY))
        self.traybutton.connect("toggled", self.on_tray_button_toggled)
        self.settings.connect("changed::tray-enabled", self.on_settings_changed)

        traybox.pack_start(self.traybutton, False, False, 6)
        traybox.show_all()

        self.main_box.pack_start(traybox, False, False, 6)

        self.window.show()

        self.update_ui_callback()

    def on_tray_button_toggled(self, widget, data=None):
        if widget.get_active():
            self.settings.set_boolean(TRAY_KEY, True)
            subprocess.Popen(["blueberry-tray"])
        else:
            self.settings.set_boolean(TRAY_KEY, False)

    def on_settings_changed(self, settings, key):
        self.traybutton.set_active(settings.get_boolean(key))

    def add_stack_page(self, message, name):
        label = Gtk.Label(message)
        self.stack.add_named(label, name)
        label.show()

    def update_ui_callback(self):
        powered = False
        sensitive = False
        page = ""

        if not self.rfkill.have_adapter:
            page = BLUETOOTH_NO_DEVICES_PAGE
        elif self.rfkill.hard_block:
            page = BLUETOOTH_DISABLED_PAGE
        elif self.rfkill.soft_block:
            page = BLUETOOTH_DISABLED_PAGE
            sensitive = True
        else:
            page = BLUETOOTH_WORKING_PAGE
            sensitive = True
            powered = True

        self.rf_switch.set_sensitive(sensitive)

        self.rf_switch.handler_block(self.rf_handler_id)
        self.rf_switch.set_state(powered)
        self.rf_switch.handler_unblock(self.rf_handler_id)

        self.stack.set_visible_child_name (page);

    def on_switch_changed(self, widget, state):
        self.rfkill.try_set_blocked(not state)

        return True

    def terminate(self, window):
        self.rfkill.terminate()
        Gtk.main_quit()

if __name__ == "__main__":
    BluetoothConfig()
    Gtk.main()
