#!/usr/bin/env python2

from gi.repository import Gio

SETTINGS_SCHEMA = "org.blueberry"
TRAY_KEY = "tray-enabled"

class Settings():
    def __init__(self):
        self.gsettings = Gio.Settings.new(SETTINGS_SCHEMA)

    def get_tray_enabled(self):
        return self.gsettings.get_boolean(TRAY_KEY)

    def set_tray_enabled(self, enabled):
        self.gsettings.set_boolean(TRAY_KEY, enabled)



