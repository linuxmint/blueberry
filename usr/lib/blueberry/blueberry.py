#!/usr/bin/env python2

import sys
import os
import gettext
from gi.repository import Gtk, GnomeBluetooth
import pwd
import socket
import subprocess

BLUETOOTH_DISABLED_PAGE      = "disabled-page"
BLUETOOTH_HW_DISABLED_PAGE   = "hw-disabled-page"
BLUETOOTH_NO_DEVICES_PAGE    = "no-devices-page"
BLUETOOTH_WORKING_PAGE       = "working-page"

RFKILL_CHK = ["/usr/sbin/rfkill", "list", "bluetooth"]
RFKILL_BLOCK = ["/usr/sbin/rfkill", "block", "bluetooth"]
RFKILL_UNBLOCK = ["/usr/sbin/rfkill", "unblock", "bluetooth"]

# i18n
gettext.install("blueberry", "/usr/share/locale")

class BluetoothConfig:
    ''' Create the UI '''
    def __init__(self):
        self.window = Gtk.Window(Gtk.WindowType.TOPLEVEL)

        self.window.set_title(_("Bluetooth"))
        self.window.set_icon_name("bluetooth")
        self.window.connect("destroy", Gtk.main_quit)
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

        self.check_airplane_mode()

        self.rf_switch.connect("state-set", self.on_switch_changed)

        self.window.show()

    def add_stack_page(self, message, name):
        label = Gtk.Label(message)
        self.stack.add_named(label, name)
        label.show()

    def check_airplane_mode(self):
        res = subprocess.check_output(RFKILL_CHK)

        if not res:
            self.stack.set_visible_child_name (BLUETOOTH_NO_DEVICES_PAGE);
            self.rf_switch.set_sensitive(False)

    def on_switch_changed(self, state, data):
        finish_state = False

        try:
            if state == True:
                res = subprocess.check_output(RFKILL_UNBLOCK)
            else:
                res = subprocess.check_output(RFKILL_BLOCK)

            if not res:
                res = subprocess.check_output(RFKILL_CHK)
        except CalledProcessError:
            finish_state = False;

        # figure out if it worked...
        #
        #

        # commit the state (background of switch now changes)
        self.rf_switch.set_state(finish_state)

        # stop handler
        return True

if __name__ == "__main__":
    BluetoothConfig()
    Gtk.main()
