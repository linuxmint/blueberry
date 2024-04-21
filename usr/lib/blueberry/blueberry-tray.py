#!/usr/bin/python3

import sys
import gettext
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('GnomeBluetooth', '1.0')
gi.require_version('AppIndicator3', '0.1')
from gi.repository import AppIndicator3, Gtk, GnomeBluetooth, Gio
import rfkillMagic
import setproctitle
import subprocess

# i18n
gettext.install("blueberry", "/usr/share/locale")
_ = gettext.gettext

setproctitle.setproctitle("blueberry-tray")

class BluetoothTray(Gtk.Application):
    def __init__(self):
        super(BluetoothTray, self).__init__(
            register_session=True,
            application_id="org.linuxmint.blueberry.tray"
        )

    def do_activate(self):
        self.hold()

    def do_startup(self):
        Gtk.Application.do_startup(self)

        debug = len(sys.argv) > 1 and sys.argv[1] == "debug"

        self.rfkill = rfkillMagic.Interface(self.update_icon_callback, debug)
        self.settings = Gio.Settings(schema="org.blueberry")
        self.settings.connect("changed::tray-enabled", self.on_settings_changed_cb)

        self.icons = {
            'default':  'blueberry-tray',
            'active':   'blueberry-tray-active',
            'disabled': 'blueberry-tray-disabled',
        }

        if self.settings.get_boolean("use-symbolic-icons"):
            for state in self.icons:
                self.icons[state] += '-symbolic'

        # If we have no adapter, or disabled tray, end early
        if (not self.rfkill.have_adapter) or (not self.settings.get_boolean("tray-enabled")):
            self.rfkill.terminate()
            sys.exit(0)

        self.client = GnomeBluetooth.Client()
        self.model = self.client.get_model()
        self.model.connect('row-changed', self.update_icon_callback)
        self.model.connect('row-deleted', self.update_icon_callback)
        self.model.connect('row-inserted', self.update_icon_callback)

        self.paired_devices = {}

        self.icon = AppIndicator3.Indicator.new(
            'BlueBerry',
            'blueberry',
            AppIndicator3.IndicatorCategory.SYSTEM_SERVICES
        )
        self.icon.set_status(AppIndicator3.IndicatorStatus.ACTIVE)

        self.update_icon_callback()

    def on_settings_changed_cb(self, setting, key, data=None):
        if not self.settings.get_boolean("tray-enabled"):
            self.terminate()

    def update_icon_callback(self, path=None, iter=None, data=None):
        if not self.rfkill.have_adapter:
            self.terminate(None)
            return

        if self.rfkill.hard_block or self.rfkill.soft_block:
            self.icon.set_icon_full(self.icons['disabled'], '')
        else:
            self.icon.set_icon_full(self.icons['default'], '')
            self.update_connected_state()

        self.icon.set_menu(self.build_menu())

    def update_connected_state(self):
        self.get_devices()

        if len(self.connected_devices) > 0:
            self.icon.set_icon_full(self.icons['active'], '')
        else:
            self.icon.set_icon_full(self.icons['default'], '')

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

    def start_blueberry(self, item):
        subprocess.Popen(["blueberry"])

    def build_menu(self):
        menu = Gtk.Menu()
        blueberry_exec = Gtk.MenuItem(label=_("BlueBerry"))
        blueberry_exec.connect("activate", self.start_blueberry)
        menu.append(blueberry_exec)

        if not self.rfkill.hard_block:
            if self.rfkill.soft_block:
                item = Gtk.MenuItem(label=_("Turn on Bluetooth"))
                item.connect("activate", self.turn_on_bluetooth)
                menu.append(item)
            else:
                item = Gtk.MenuItem(label=_("Turn off Bluetooth"))
                item.connect("activate", self.turn_off_bluetooth)
                menu.append(item)

        if not(self.rfkill.hard_block or self.rfkill.soft_block):
            item = Gtk.MenuItem(label=_("Send files to a device"))
            item.connect("activate", self.send_files_cb)
            menu.append(item)

        item = Gtk.MenuItem(label=_("Open Bluetooth device manager"))
        item.connect("activate", self.open_manager_cb)
        menu.append(item)

        if len(self.paired_devices) > 0:
            menu.append(Gtk.SeparatorMenuItem())
            m_item = Gtk.MenuItem(label=_("Paired devices"))
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
        return menu

    def toggle_connect_cb(self, item, data = None):
        proxy = self.paired_devices[data]
        connected = data in self.connected_devices
        self.client.connect_service(proxy.get_object_path(), not connected)

    def send_files_cb(self, item, data = None):
        subprocess.Popen(["bluetooth-sendto"])

    def open_manager_cb(self, item, data = None):
        subprocess.Popen(["blueberry"])

    def turn_on_bluetooth(self, item):
        self.rfkill.try_set_blocked(False)
        return True

    def turn_off_bluetooth(self, item):
        self.rfkill.try_set_blocked(True)
        return True

    def terminate(self, window = None, data = None):
        self.quit()

if __name__ == "__main__":
    BluetoothTray().run()
