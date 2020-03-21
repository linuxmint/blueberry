#!/usr/bin/env python3

import sys
import gettext
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('GnomeBluetooth', '1.0')
gi.require_version('XApp', '1.0')
from gi.repository import Gtk, Gdk, GnomeBluetooth, Gio, XApp
import rfkillMagic
import setproctitle
import subprocess

# i18n
gettext.install("blueberry", "/usr/share/locale")

setproctitle.setproctitle("blueberry-tray")

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

        self.tray_icon = "blueberry-tray"
        self.tray_active_icon = "blueberry-tray-active"
        self.tray_disabled_icon = "blueberry-tray-disabled"
        if self.settings.get_boolean("use-symbolic-icons"):
            self.tray_icon = "blueberry-tray-symbolic"
            self.tray_active_icon = "blueberry-tray-active-symbolic"
            self.tray_disabled_icon = "blueberry-tray-disabled-symbolic"

        # If we have no adapter, or disabled tray, end early
        if (not self.rfkill.have_adapter) or (not self.settings.get_boolean("tray-enabled")):
            self.rfkill.terminate()
            sys.exit(0)

        self.client = GnomeBluetooth.Client()
        self.model = self.client.get_model()
        self.model.connect('row-changed', self.update_icon_callback)
        self.model.connect('row-deleted', self.update_icon_callback)
        self.model.connect('row-inserted', self.update_icon_callback)

        self.icon = XApp.StatusIcon()
        self.icon.set_name("blueberry")
        self.icon.set_tooltip_text(_("Bluetooth"))
        self.icon.connect("activate", self.on_statusicon_activated)
        self.icon.connect("button-release-event", self.on_statusicon_released)

        self.update_icon_callback(None, None, None)

    def on_settings_changed_cb(self, setting, key, data=None):
        if not self.settings.get_boolean("tray-enabled"):
            self.terminate()

    def update_icon_callback(self, path=None, iter=None, data=None):
        if not self.rfkill.have_adapter:
            self.terminate(None)
            return

        if self.rfkill.hard_block or self.rfkill.soft_block:
            self.icon.set_icon_name(self.tray_disabled_icon)
            self.icon.set_tooltip_text(_("Bluetooth is disabled"))
        else:
            self.icon.set_icon_name(self.tray_icon)
            self.update_connected_state()

    def update_connected_state(self):
        self.get_devices()

        if len(self.connected_devices) > 0:
            self.icon.set_icon_name(self.tray_active_icon)
            self.icon.set_tooltip_text(_("Bluetooth: Connected to %s") % (", ".join(self.connected_devices)))
        else:
            self.icon.set_icon_name(self.tray_icon)
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

    def on_statusicon_activated(self, icon, button, time):
        if button == Gdk.BUTTON_PRIMARY:
            subprocess.Popen(["blueberry"])

    def on_statusicon_released(self, icon, x, y, button, time, position):
        if button == 3:
            menu = Gtk.Menu()
            if not(self.rfkill.hard_block or self.rfkill.soft_block):
                item = Gtk.MenuItem(label=_("Send files to a device"))
                item.connect("activate", self.send_files_cb)
                menu.append(item)

            item = Gtk.MenuItem(label=_("Open Bluetooth device manager"))
            item.connect("activate", self.open_manager_cb)
            menu.append(item)

            if len(self.paired_devices) > 0:
                menu.append(Gtk.SeparatorMenuItem())
                m_item = Gtk.MenuItem(_("Paired devices"))
                menu.append(m_item)
                paired_menu = Gtk.Menu()
                m_item.set_submenu(paired_menu)
                for device in self.paired_devices:
                    label = device
                    item = Gtk.ImageMenuItem(label=label)
                    if device in self.connected_devices:
                        image = Gtk.Image.new_from_icon_name("emblem-ok-symbolic", Gtk.IconSize.MENU)
                        image.set_tooltip_text(_("Connected"))
                        item.set_always_show_image(True)
                        item.set_image(image)
                    item.connect("activate",self.toggle_connect_cb, device)
                    paired_menu.append(item)

            menu.append(Gtk.SeparatorMenuItem())

            item = Gtk.MenuItem(label=_("Quit"))
            item.connect("activate", self.terminate)
            menu.append(item)

            menu.show_all()

            if position == -1:
                # The position and coordinates are unknown. This is the
                # case when the XAppStatusIcon fallbacks as a Gtk.StatusIcon
                menu.popup(None, None, None, None, button, time)
            else:
                def position_menu_cb(menu, pointer_x, pointer_y, user_data):
                    [x, y, position] = user_data;
                    if (position == Gtk.PositionType.BOTTOM):
                        y = y - menu.get_allocation().height;
                    if (position == Gtk.PositionType.RIGHT):
                        x = x - menu.get_allocation().width;
                    return (x, y, False)
                device = Gdk.Display.get_default().get_device_manager().get_client_pointer()
                menu.popup_for_device(device, None, None, position_menu_cb, [x, y, position], button, time)

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
