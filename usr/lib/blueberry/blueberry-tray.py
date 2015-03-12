#!/usr/bin/env python2

import sys
import gettext
from gi.repository import Gtk, Gdk, GnomeBluetooth, Gio
import rfkillMagic
import subprocess

SETTINGS_SCHEMA = "org.blueberry"
TRAY_KEY = "tray-enabled"

# i18n
gettext.install("blueberry", "/usr/share/locale")

class BluetoothTray:
    def __init__(self):
        debug = False
        if len(sys.argv) > 1 and sys.argv[1] == "debug":
            debug = True

        self.settings = Gio.Settings(SETTINGS_SCHEMA)
        if not self.settings.get_boolean(TRAY_KEY):
            self.terminate(None)

        self.settings.connect("changed::tray-enabled", self.on_settings_changed_cb)

        self.rfkill = rfkillMagic.Interface(self.update_icon_callback, debug)

        # If we have no adapter, just end it
        if not self.rfkill.have_adapter:
            self.terminate(None)

        self.client = GnomeBluetooth.Client()
        self.model = self.client.get_model()
        self.model.connect('row-changed', self.update_icon_callback)
        self.model.connect('row-deleted', self.update_icon_callback)
        self.model.connect('row-inserted', self.update_icon_callback)

        self.icon = Gtk.StatusIcon()
        self.icon.set_title("Bluetooth status")
        self.icon.connect("popup-menu", self.do_popup_menu)

        self.update_icon_callback(None, None, None)

    def on_settings_changed_cb(self, setting, key, data=None):
        if not self.settings.get_boolean(TRAY_KEY):
            self.terminate()

    def update_icon_callback(self, path=None, iter=None, data=None):
        if not self.rfkill.have_adapter:
            self.terminate(None)
            return

        if self.rfkill.hard_block or self.rfkill.soft_block:
            self.icon.set_visible(False)
        else:
            self.icon.set_visible(True)
            self.update_connected_state()

    def update_connected_state(self):
        n_devices = self.get_n_devices()

        if n_devices > 0:
            self.icon.set_from_icon_name("blueberry-active")
            self.icon.set_tooltip_text(_("%d devices connected"))
            self.icon.set_tooltip_text(gettext.ngettext("%d device connected" % n_devices, 
                                                        "%d devices connected" % n_devices,
                                                        n_devices))
        else:
            self.icon.set_from_icon_name("blueberry")
            self.icon.set_tooltip_text(_("No devices connected"))

    def get_n_devices(self):
        default_iter = None

        iter = self.model.get_iter_first()

        while iter:
            default = self.model.get_value(iter, GnomeBluetooth.Column.DEFAULT)
            if default:
                default_iter = iter
                break
            iter = self.model.iter_next(iter)

        if default_iter == None:
            return False

        n_devices = 0

        iter = self.model.iter_children(default_iter)
        while iter:
            connected = self.model.get_value(iter, GnomeBluetooth.Column.CONNECTED)
            if connected:
                n_devices += 1

            iter = self.model.iter_next(iter)

        return n_devices

    def do_popup_menu(self, icon, button, time, data = None):
        menu = Gtk.Menu()

        item = Gtk.MenuItem(label=_("Send files to a device"))
        item.connect("activate", self.send_files_cb)
        menu.append(item)

        item = Gtk.MenuItem(label=_("Open Bluetooth device manager"))
        item.connect("activate", self.open_manager_cb)
        menu.append(item)

        menu.append(Gtk.SeparatorMenuItem())

        item = Gtk.MenuItem(label=_("Quit"))
        item.connect("activate", self.terminate)
        menu.append(item)

        menu.show_all()

        device = Gdk.Display.get_default().get_device_manager().get_client_pointer()
        menu.popup_for_device(device, None, None, lambda w,x: icon.position_menu(menu, icon), icon, button, time)

    def send_files_cb(self, item, data = None):
        subprocess.Popen(["bluetooth-sendto"])

    def open_manager_cb(self, item, data = None):
        subprocess.Popen(["blueberry"])

    def terminate(self, window = None, data = None):
        self.rfkill.terminate()
        Gtk.main_quit()

if __name__ == "__main__":
    BluetoothTray()
    Gtk.main()
