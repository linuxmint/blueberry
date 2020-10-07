#!/usr/bin/python3

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

        self.rfkill_error_image = builder.get_object("rfkill-error-image")

        # Settings
        settings_box = SettingsBox()
        settings_container = builder.get_object("settings-container")
        settings_container.pack_start(settings_box, True, True, 0)

        self.adapter_name_entry = Gtk.Entry(width_chars=30)
        self.adapter_name_entry.connect("focus-out-event", self.update_name_from_entry)
        self.adapter_name_entry.connect("activate", self.update_name_from_entry)
        self.adapter_name_entry.set_sensitive(False)
        self.adapter_name_entry.set_placeholder_text(_("Enable Bluetooth to edit"))
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

        settings_box.show_all()

        self.lib_widget = GnomeBluetooth.SettingsWidget.new()
        self.lib_widget.connect("panel-changed", self.panel_changed)
        builder.get_object("bluetooth-widget-box").pack_start(self.lib_widget, True, True, 0)

        self.add_window(window)
        window.show_all()
        self.update_ui_callback()

        # attempt to apply overrides and if we fail don't setup update hooks
        if self.get_label_widget_and_spinner(self.lib_widget):
            self.label_widget.set_text("")
            self.client = GnomeBluetooth.Client()
            self.model = self.client.get_model()
            self.model.connect('row-changed', self.on_adapter_status_changed)
            self.model.connect('row-deleted', self.on_adapter_status_changed)
            self.model.connect('row-inserted', self.on_adapter_status_changed)
            self.on_adapter_status_changed(self.lib_widget)

    def bluetooth_on(self):
        return not self.rfkill.soft_block and not self.rfkill.hard_block

    def get_label_widget_and_spinner(self, widget):
        # We attempt to override the widget style to replace
        # the explanation label text and destroy the spinner.
        # gnome_bluetooth_settings_widget doesn't give explicit access
        # to its label via gi so we recurse its child widgets to try
        # to find the parts we want to modify.

        # if the override fails for any reason it is disabled. update
        # signals in the main class are only connected if a test call
        # to this succeeds the first time

        self.label_widget = None
        self.spinner = None

        try:
            # not finding the label is fatal as it's our main purpose here
            self.label_widget = find_widget(widget, "explanation-label")

            if self.label_widget is None:
                raise LookupError("unable to find label to override")

            spinner = find_widget(widget, widgetClass=Gtk.Spinner)
            if spinner != None:
                spinner.destroy()

        except Exception as e:
            log("could not fetch label widget: {}".format(e))
            return False

        return True

    def on_adapter_status_changed(self, settings, foo=None, data=None):
        if self.bluetooth_on():
            self.adapter_name_entry.set_text(self.get_adapter_name())
        else:
            self.adapter_name_entry.set_text("")
        self.update_status(self.adapter_name_entry)

    def panel_changed(self, widget, panel=None):
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
            os.system("pkill -9 blueberry-obex");
        self.update_status()

    def update_name_from_entry(self, entry, arg1=None, data=None):
        name = entry.get_text()
        if name == "":
            adapter_name = self.client.props.default_adapter_name
            name = adapter_name if adapter_name else ""
            entry.set_text(name)

        subprocess.call(["bt-adapter", "--set", "Alias", name])
        self.update_status()

    def on_settings_changed(self, settings, key):
        self.tray_switch.set_active(self.settings.get_boolean("tray-enabled"))
        self.obex_switch.set_active(self.settings.get_boolean("obex-enabled"))

    def get_adapter_name(self):
        if not self.bluetooth_on():
            return ""

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

        if name == None:
            default_name = self.client.props.default_adapter_name
            name = default_name if (default_name != None) else ""

        return name

    def update_status(self, path=None, iter=None, data=None):
        if not self.label_widget:
            return

        obex_enabled = self.settings.get_boolean("obex-enabled")

        if self.bluetooth_on():
            adapter_name = self.get_adapter_name()
            if adapter_name != "":
                self.adapter_name_entry.set_sensitive(True)

                if obex_enabled:
                    text = _("Visible as %s and available for Bluetooth file transfers.")
                else:
                    text = _("Visible as %s.")

                text = "%s\n" % text
                self.label_widget.set_markup(text % "\"%s\"" % adapter_name)
            else:
                self.adapter_name_entry.set_sensitive(False)
                self.label_widget.set_label("")
        else:
            self.adapter_name_entry.set_sensitive(False)

    def update_ui_callback(self):
        powered = False
        sensitive = False
        header_icon_name = status_icon_name = "blueberry-disabled"
        status_msg = ""

        if not self.rfkill.have_adapter:
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

        # rfkill errors don't change powered state. If we forced the status page then the
        # most likely scenario would be a mixed state of powered-on bluetooth with UI
        # hiding that fact. Instead we show an error icon next to the switch and disable
        # the switch itself without changing any other state.
        if self.rfkill.rfkill_err is not None:
            strings = (_("An error has occurred"),
                       self.rfkill.rfkill_err.strip(),
                       _("Permission issues can be solved with a udev rule for rfkill or membership in the 'rfkill' group."))
            self.rfkill_error_image.set_tooltip_text("%s\n%s\n\n%s" % strings)
            self.rfkill_error_image.show()
            sensitive = False
        else:
            self.rfkill_error_image.hide()

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
