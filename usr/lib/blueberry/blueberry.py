#!/usr/bin/env python3

import sys, os
import gettext
import rfkillMagic
import setproctitle
import subprocess
from BlueberrySettingsWidgets import SettingsBox, SettingsRow
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('GnomeBluetooth', '1.0')
from gi.repository import Gtk, GnomeBluetooth, Gio, GLib

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
APPLICATION_ID = 'com.linuxmint.blueberry'

# i18n
gettext.install("blueberry", "/usr/share/locale")

setproctitle.setproctitle("blueberry")

# similar to g_warning by default, can specify any log level though
def log(text, log_level=GLib.LogLevelFlags.LEVEL_WARNING):
    variant = GLib.Variant("a{sv}", { "MESSAGE": GLib.Variant("s", text) })
    GLib.log_variant(APPLICATION_ID, log_level, variant)

# searches a widget and its children for a specific buildable id or widget type
# note: stops at first match
def find_widget(parent, name="", widgetClass=None):
    p_name = Gtk.Buildable.get_name(parent)
    if p_name and name and p_name.strip() == name.strip():
        return parent

    if widgetClass and isinstance(parent, widgetClass):
        return parent

    if hasattr(parent, "get_children"):
        children = parent.get_children()
        for child in children:
            res = find_widget(child, name, widgetClass)
            if res is not None:
                return res

    return None

# We attempt to override the widget style to replace
# the explanation label text and stop the spinner.
# gnome_bluetooth_settings_widget doesn't give explicit access
# to its label via gi so we recurse its child widgets to try
# to find the parts we want to modify.

# if the override fails for any reason it is disabled. update
# signals in the main class are only connected if a test call
# to this succeeds the first time
override_failed = False

def apply_widget_override(widget, adapter_name, obex_enabled):
    global override_failed
    if override_failed:
        return False

    try:
        # not finding the label is fatal as it's our main purpose here
        label = find_widget(widget, "explanation-label")
        if label is None:
            raise LookupError("unable to find label to override")

        # not finding the spinner is non-fatal
        spinner = find_widget(widget, widgetClass=Gtk.Spinner)
        if spinner and spinner.props.active:
            spinner.stop()

        if adapter_name is not None:
            if obex_enabled:
                text = _("Visible as %s and available for Bluetooth file transfers.")
            else:
                text = _("Visible as %s.")
            text = "%s\n" % text
            label.set_markup(text % "\"%s\"" % adapter_name)
        else:
            label.set_label("")

    except Exception as e:
        log("apply_widget_override failed: {}".format(e))
        override_failed = True
        return False

    return True


class Blueberry(Gtk.Application):
    def do_startup(self):
        Gtk.Application.do_startup(self)

        self.settings = Gio.Settings(schema="org.blueberry")

        #detect current DE
        wm_info = subprocess.getoutput("wmctrl -m")
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
            log("DE could not be detected!")
            self.configuration_tools = {}
            if os.path.exists("/usr/bin/pavucontrol"):
                self.configuration_tools["sound"] = "pavucontrol"

    def do_activate(self):
        if self.settings.get_boolean("tray-enabled"):
            subprocess.Popen(['blueberry-tray'])

        if len(self.get_windows()) > 0:
            # Blueberry is already running, focus the window
            self.get_active_window().present()
            return

        builder = Gtk.Builder.new_from_file(os.path.join(SCRIPT_DIR, "blueberry.ui"))

        window = builder.get_object("window")
        window.set_title(_("Bluetooth"))

        builder.get_object("settings-button").set_tooltip_text(_("Settings"))

        self.stack = builder.get_object("stack")

        debug = False
        if len(sys.argv) > 1 and sys.argv[1] == "debug":
            debug = True

        self.header_icon = builder.get_object("header-icon")
        self.status_icon = builder.get_object("status-icon")
        self.status_label = builder.get_object("status-label")

        # Devices
        self.rf_switch = builder.get_object("bluetooth-switch")
        self.rfkill = rfkillMagic.Interface(self.update_ui_callback, debug)
        self.rf_handler_id = self.rf_switch.connect("state-set", self.on_switch_changed)

        self.lib_widget = GnomeBluetooth.SettingsWidget.new()
        self.lib_widget.connect("panel-changed", self.panel_changed)
        builder.get_object("bluetooth-widget-box").pack_start(self.lib_widget, True, True, 0)
        self.lib_widget.show()

        # Settings
        settings_box = SettingsBox()
        settings_container = builder.get_object("settings-container")
        settings_container.pack_start(settings_box, True, True, 0)

        self.adapter_name_entry = Gtk.Entry()
        adapter_name = self.get_default_adapter_name()
        if adapter_name is not None:
            self.adapter_name_entry.set_text(adapter_name)
        self.adapter_name_entry.connect("changed", self.on_adapter_name_changed)
        row = SettingsRow(Gtk.Label(label=_("Name")), self.adapter_name_entry)
        row.set_tooltip_text(_("This is the Bluetooth name of your computer"))
        settings_box.add_row(row)

        self.obex_switch = Gtk.Switch()
        self.obex_switch.set_active(self.settings.get_boolean("obex-enabled"))
        self.obex_switch.connect("notify::active", self.on_obex_switch_toggled)
        self.settings.connect("changed", self.on_settings_changed)
        row = SettingsRow(Gtk.Label(label=_("Receive files from remote devices")), self.obex_switch)
        row.set_tooltip_text(_("This option allows your computer to receive files transferred over Bluetooth (OBEX)"))
        settings_box.add_row(row)

        self.tray_switch = Gtk.Switch()
        self.tray_switch.set_active(self.settings.get_boolean("tray-enabled"))
        self.tray_switch.connect("notify::active", self.on_tray_switch_toggled)
        self.settings.connect("changed", self.on_settings_changed)
        settings_box.add_row(SettingsRow(Gtk.Label(label=_("Show a tray icon")), self.tray_switch))

        settings_container.show_all()

        self.update_ui_callback()

        self.add_window(window)
        window.show_all()

        # attempt to apply overrides and if we fail don't setup update hooks
        name = self.get_default_adapter_name()
        obex_enabled = self.settings.get_boolean("obex-enabled")
        if apply_widget_override(self.lib_widget, name, obex_enabled):
            self.client = GnomeBluetooth.Client()
            self.model = self.client.get_model()
            self.model.connect('row-changed', self.update_status)
            self.model.connect('row-deleted', self.update_status)
            self.model.connect('row-inserted', self.update_status)
            self.update_status()

    def panel_changed(self, widget, panel):
        if not panel in self.configuration_tools:
            log("No configuration tool known for panel '{}'".format(panel))
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

    def get_default_adapter_name(self):
        name = None
        try:
            output = subprocess.check_output(["timeout", "2s", "bt-adapter", "-i"]).decode("utf-8").strip()
            for line in output.split("\n"):
                line = line.strip()
                if line.startswith("Alias: "):
                    name = line.replace("Alias: ", "").replace(" [rw]", "").replace(" [ro]", "")
                    break
        except Exception as cause:
            log("Could not retrieve the BT adapter name with 'bt-adapter -i': {}".format(cause))
        return name

    def update_status(self, path=None, iter=None, data=None):
        if override_failed:
            return

        name = self.get_default_adapter_name()
        obex_enabled = self.settings.get_boolean("obex-enabled")
        apply_widget_override(self.lib_widget, name, obex_enabled)

    def update_ui_callback(self):
        powered = False
        sensitive = False
        header_icon_name = status_icon_name = "blueberry-disabled"
        status_msg = ""

        if self.rfkill.rfkill_err is not None:
            status_msg = ("%s\n%s" % (_("An error has occurred"), self.rfkill.rfkill_err))
            status_icon_name = "dialog-error"
            sensitive = True
        elif not self.rfkill.have_adapter:
            status_msg = _("No Bluetooth adapters found")
            status_icon_name = "dialog-info"
        elif self.rfkill.hard_block:
            status_msg = _("Bluetooth is disabled by hardware switch")
        elif self.rfkill.soft_block:
            status_msg = _("Bluetooth is disabled")
            sensitive = True
        else:
            header_icon_name = status_icon_name = "blueberry"
            sensitive = True
            powered = True

        self.status_label.set_markup(status_msg)

        self.header_icon.set_from_icon_name(header_icon_name, Gtk.IconSize.LARGE_TOOLBAR)
        self.status_icon.set_from_icon_name(status_icon_name, Gtk.IconSize.DIALOG)

        self.rf_switch.set_sensitive(sensitive)

        self.rf_switch.handler_block(self.rf_handler_id)
        self.rf_switch.set_state(powered)
        self.rf_switch.handler_unblock(self.rf_handler_id)

        self.stack.set_visible_child_name("main-page" if powered else "status-page");

    def on_switch_changed(self, widget, state):
        self.rfkill.try_set_blocked(not state)
        return True

if __name__ == "__main__":
    app = Blueberry(application_id=APPLICATION_ID, flags=Gio.ApplicationFlags.FLAGS_NONE)
    app.run(None)
