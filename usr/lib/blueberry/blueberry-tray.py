#!/usr/bin/env python2

import sys
import gettext
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('GnomeBluetooth', '1.0')
from gi.repository import Gtk, Gdk, GnomeBluetooth, Gio
import rfkillMagic
import subprocess

# i18n
gettext.install("blueberry", "/usr/share/locale")

class BluetoothTray(Gtk.Application):
    def __init__(self):
        super(BluetoothTray, self).__init__(register_session=True, application_id="org.linuxmint.blueberry.tray")

    def do_activate(self):
        self.hold()

    def do_startup(self):
        Gtk.Application.do_startup(self)

        debug = False
        if len(sys.argv) > 1 and sys.argv[1] == "debug":
            debug = True

        self.rfkill = rfkillMagic.Interface(self.update_icon_callback, debug)
        self.settings = Gio.Settings(schema="org.blueberry")
        self.settings.connect("changed::tray-enabled", self.on_settings_changed_cb)

        # If we have no adapter, or disabled tray, end early
        if (not self.rfkill.have_adapter) or (not self.settings.get_boolean("tray-enabled")):
            self.rfkill.terminate()
            sys.exit(0)

        self.client = GnomeBluetooth.Client()
        self.model = self.client.get_model()
        self.model.connect('row-changed', self.update_icon_callback)
        self.model.connect('row-deleted', self.update_icon_callback)
        self.model.connect('row-inserted', self.update_icon_callback)

        self.icon = Gtk.StatusIcon()
        self.icon.set_title(_("Bluetooth"))
        self.icon.connect("popup-menu", self.on_popup_menu)
        self.icon.connect("activate", self.on_activate)

        self.update_icon_callback(None, None, None)

    def on_settings_changed_cb(self, setting, key, data=None):
        if not self.settings.get_boolean("tray-enabled"):
            self.terminate()

    def update_icon_callback(self, path=None, iter=None, data=None):
        if not self.rfkill.have_adapter:
            self.terminate(None)
            return

        if self.rfkill.hard_block or self.rfkill.soft_block:
            self.icon.set_from_icon_name("blueberry-tray-disabled")
            self.icon.set_tooltip_text(_("Bluetooth is disabled"))
        else:
            self.icon.set_from_icon_name("blueberry-tray")
            self.update_connected_state()

    def update_connected_state(self):
        self.get_devices()

        if len(self.connected_devices) > 0:
            self.icon.set_from_icon_name("blueberry-tray-active")
            self.icon.set_tooltip_text(_("Bluetooth: Connected to %s") % (", ".join(self.connected_devices)))
        else:
            self.icon.set_from_icon_name("blueberry-tray")
            self.icon.set_tooltip_text(_("Bluetooth"))

    def get_devices(self):
        self.connected_devices = []
        self.paired_devices = {}
        default_iter = None

        iter = self.model.get_iter_first()

        while iter:
            default = self.model.get_value(iter, GnomeBluetooth.Column.DEFAULT)
            if default:
                default_iter = iter
                break
            iter = self.model.iter_next(iter)

        if default_iter != None:
            iter = self.model.iter_children(default_iter)
            while iter:
                connected = self.model.get_value(iter, GnomeBluetooth.Column.CONNECTED)
                if connected:
                    name = self.model.get_value(iter, GnomeBluetooth.Column.NAME)
                    self.connected_devices.append(name)

                paired = self.model.get_value(iter, GnomeBluetooth.Column.PAIRED)
                if paired:
                    name = self.model.get_value(iter, GnomeBluetooth.Column.NAME)
                    proxy = self.model.get_value(iter, GnomeBluetooth.Column.PROXY)
                    self.paired_devices[name] = proxy

                iter = self.model.iter_next(iter)

    def on_activate(self, icon, data=None):
        subprocess.Popen(["blueberry"])

    def create_paired_submenu(self):
        paired_menu = None
        if len(self.paired_devices) > 0:
            paired_menu = Gtk.Menu()
            for device in self.paired_devices:
                label = device
                if device in self.connected_devices:
                    label = label + " - connected"
                item = Gtk.MenuItem(label=label)
                item.connect("activate",self.toggle_connect_cb, device)
                paired_menu.append(item)
            m_item = Gtk.MenuItem("Paired Devices")
            m_item.set_submenu(paired_menu)
        return m_item

    def on_popup_menu(self, icon, button, time, data = None):
        menu = Gtk.Menu()

        def position_menu_cb(m, x, y=None, i=None):
            try:
                return Gtk.StatusIcon.position_menu(menu, x, y, icon)
            except (AttributeError, TypeError):
                return Gtk.StatusIcon.position_menu(menu, icon)

        if not(self.rfkill.hard_block or self.rfkill.soft_block):
            item = Gtk.MenuItem(label=_("Send files to a device"))
            item.connect("activate", self.send_files_cb)
            menu.append(item)

        item = Gtk.MenuItem(label=_("Open Bluetooth device manager"))
        item.connect("activate", self.open_manager_cb)
        menu.append(item)

        menu.append(Gtk.SeparatorMenuItem())
        paired_menu = self.create_paired_submenu()
        if paired_menu:
            menu.append(paired_menu)

        menu.append(Gtk.SeparatorMenuItem())

        item = Gtk.MenuItem(label=_("Quit"))
        item.connect("activate", self.terminate)
        menu.append(item)

        menu.show_all()

        device = Gdk.Display.get_default().get_device_manager().get_client_pointer()
        menu.popup_for_device(device, None, None, position_menu_cb, icon, button, time)

    def toggle_connect_cb(self, item, data = None):
        proxy = self.paired_devices[data]
        connected = data in self.connected_devices
        self.client.connect_service(proxy.get_object_path(), not connected)

    def send_files_cb(self, item, data = None):
        subprocess.Popen(["bluetooth-sendto"])

    def open_manager_cb(self, item, data = None):
        subprocess.Popen(["blueberry"])

    def terminate(self, window = None, data = None):
        self.quit()

if __name__ == "__main__":
    BluetoothTray().run()
