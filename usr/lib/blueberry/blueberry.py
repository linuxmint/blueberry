#!/usr/bin/env python2

import sys, os, commands
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

# detect the DE environment
wm_info = commands.getoutput("wmctrl -m")
if "XDG_CURRENT_DESKTOP" in os.environ:
    xdg_current_desktop = os.environ["XDG_CURRENT_DESKTOP"]
else:
    xdg_current_desktop = ""

if "Marco" in wm_info or xdg_current_desktop == "MATE":
    CONF_TOOLS = {"sound": "mate-volume-control", "keyboard": "mate-keyboard-properties", "mouse": "mate-mouse-properties"}
elif "Xfwm4" in wm_info or xdg_current_desktop == "XFCE":
    CONF_TOOLS = {"keyboard": "xfce4-keyboard-settings", "mouse": "xfce4-mouse-settings"}
    if os.path.exists("/usr/bin/pavucontrol"):
        CONF_TOOLS["sound"] = "pavucontrol"
    else:
        CONF_TOOLS["sound"] = "xfce4-mixer"
elif "Muffin" in wm_info:
    CONF_TOOLS = {"sound": "cinnamon-settings sound", "keyboard": "cinnamon-settings keyboard", "mouse": "cinnamon-settings mouse"}
elif "Mutter" in wm_info:
    CONF_TOOLS = {"sound": "gnome-control-center sound", "keyboard": "gnome-control-center keyboard", "mouse": "gnome-control-center mouse"}
elif "Unity" in wm_info or xdg_current_desktop == "Unity":
    CONF_TOOLS = {"sound": "unity-control-center sound", "keyboard": "unity-control-center keyboard", "mouse": "unity-control-center mouse"}
else:
    print "Warning: DE could not be detected!"
    CONF_TOOLS = {}
 
class Blueberry(Gtk.Application):
    ''' Create the UI '''
    def __init__(self):

        Gtk.Application.__init__(self, application_id='com.linuxmint.blueberry', flags=Gio.ApplicationFlags.FLAGS_NONE)
        self.connect("activate", self.on_activate)

    def on_activate(self, data=None):
        list = self.get_windows()
        if len(list) > 0:
            # Blueberry is already running, focus the window
            self.get_active_window().present()
        else:
            self.create_window()
            
    def create_window(self):
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

        self.lib_widget.connect("panel-changed", self.panel_changed);

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

        self.add_window(self.window)

    def panel_changed(self, widget, panel):
        if not panel in CONF_TOOLS:
            print "Warning, no configuration tool known for panel '%s'" % panel
        else:
            os.system("%s &" % CONF_TOOLS[panel])

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
            page = BLUETOOTH_HW_DISABLED_PAGE
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
    app = Blueberry()
    app.run(None)
