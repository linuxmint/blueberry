// -*- mode: js; js-indent-level: 4; indent-tabs-mode: nil -*-

const Applet = imports.ui.applet;
const Lang = imports.lang;
const St = imports.gi.St;
const PopupMenu = imports.ui.popupMenu;
const Util = imports.misc.util;
const Main = imports.ui.main;
const GnomeBluetooth = imports.gi.GnomeBluetooth;
const GLib = imports.gi.GLib;

// Override Gettext localization
const Gettext = imports.gettext;
Gettext.bindtextdomain('blueberry', '/usr/share/locale');

function gettextBT(string) {
    return Gettext.dgettext("blueberry", string);
}

function MyApplet(metadata, orientation, panel_height, instance_id) {
    this._init(metadata, orientation, panel_height, instance_id);
}

MyApplet.prototype = {
    __proto__: Applet.IconApplet.prototype,

    _init: function(metadata, orientation, panel_height, instance_id) {
        Applet.IconApplet.prototype._init.call(this, orientation, panel_height, instance_id);

        this.setAllowedLayout(Applet.AllowedLayout.BOTH);

        this.metadata = metadata;
        Main.systrayManager.registerRole("blueberry-tray.py", metadata.uuid);
        this.set_applet_icon_symbolic_name('blueberry-applet');
        this.set_applet_tooltip(gettextBT("Bluetooth"));

        try {
            this.menuManager = new PopupMenu.PopupMenuManager(this);
            this.menu = new Applet.AppletPopupMenu(this, orientation);
            this.menuManager.addMenu(this.menu);

            let item = new PopupMenu.PopupIconMenuItem(gettextBT("Send files to a device"), "send-to", St.IconType.SYMBOLIC);
            item.connect('activate', Lang.bind(this, function() {
                Util.spawnCommandLine("bluetooth-sendto");
            }));
            this.menu.addMenuItem(item);

            item = new PopupMenu.PopupIconMenuItem(gettextBT("Open Bluetooth device manager"), "preferences-system", St.IconType.SYMBOLIC);
            item.connect('activate', Lang.bind(this, function() {
                Util.spawnCommandLine("blueberry");
            }));
            this.menu.addMenuItem(item);

            this._client = new GnomeBluetooth.Client();
            this._model = this._client.get_model();
            this._model.connect('row-changed', Lang.bind(this, this._sync));
            this._model.connect('row-deleted', Lang.bind(this, this._sync));
            this._model.connect('row-inserted', Lang.bind(this, this._sync));
            this._sync();
        }
        catch (e) {
            global.logError(e);
        }
    },

    on_applet_clicked: function(event) {
        this.menu.toggle();
    },

    on_applet_removed_from_panel: function() {
        Main.systrayManager.unregisterId(this.metadata.uuid);
    },

    _getDefaultAdapter: function() {
        let [ret, iter] = this._model.get_iter_first();
        while (ret) {
            let isDefault = this._model.get_value(iter, GnomeBluetooth.Column.DEFAULT);
            let isPowered = this._model.get_value(iter, GnomeBluetooth.Column.POWERED);
            if (isDefault && isPowered) {
                return iter;
            }
            ret = this._model.iter_next(iter);
        }
        return null;
    },

    _get_connected_devices: function() {
        let nDevices = 0;
        let connected_devices = new Array();

        let adapter = this._getDefaultAdapter();
        if (!adapter)
            return [-1, connected_devices];

        let [ret, iter] = this._model.iter_children(adapter);
        while (ret) {
            let isConnected = this._model.get_value(iter, GnomeBluetooth.Column.CONNECTED);
            if (isConnected) {
                let name = this._model.get_value(iter, GnomeBluetooth.Column.NAME);
                connected_devices.push(name);
            }
            let isPaired = this._model.get_value(iter, GnomeBluetooth.Column.PAIRED);
            let isTrusted = this._model.get_value(iter, GnomeBluetooth.Column.TRUSTED);
            if (isPaired || isTrusted) {
                nDevices++;
            }
            ret = this._model.iter_next(iter);
        }

        return [nDevices, connected_devices];
    },

    _computer_has_a_bt_adapter: function() {
        try {
            let [result, stdout, stderr] = GLib.spawn_command_line_sync("/usr/sbin/rfkill list bluetooth");
            if (stdout != null) {
                let output = stdout.toString();
                let lines = output.split('\n');
                for (let i = 0; i < lines.length; i++) {
                    let line = lines[i];
                    if (line.search("Bluetooth") != -1) {
                        return true;
                    }
                }
            }
        }
        catch (e) {
            global.logError(e);
        }
        return false;
    },

    _sync: function() {

        try {
            if (this._computer_has_a_bt_adapter()) {
                this.set_applet_enabled(true);
                let [ nDevices, connected_devices ] = this._get_connected_devices();
                if (nDevices >= 0) {
                    if (connected_devices.length > 0) {
                        this.set_applet_icon_symbolic_name('blueberry-applet-connected');
                        let text = gettextBT("Bluetooth: Connected to %s");
                        text = text.replace("%s", connected_devices.join(", "));
                        this.set_applet_tooltip(text);
                    }
                    else {
                        this.set_applet_icon_symbolic_name('blueberry-applet');
                        this.set_applet_tooltip(gettextBT("Bluetooth"));
                    }
                }
                else {
                    this.set_applet_icon_symbolic_name('blueberry-applet-disabled');
                    this.set_applet_tooltip(gettextBT("Bluetooth is disabled"));
                }
            }
            else {
                this.set_applet_enabled(false);
            }
        }
        catch (e) {
            global.logError(e);
        }
    }
};

function main(metadata, orientation, panel_height, instance_id) {
    let myApplet = new MyApplet(metadata, orientation, panel_height, instance_id);
    return myApplet;
}
