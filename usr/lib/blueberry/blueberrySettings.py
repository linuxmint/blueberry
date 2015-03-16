#!/usr/bin/env python2

from gi.repository import Gio

SETTINGS_SCHEMA = "org.blueberry"
TRAY_KEY = "tray-enabled"
BLOCK_KEY = "bluetooth-soft-block"
MANAGED_KEY = "manage-bluetooth-state"

class Settings():
    def __init__(self):
        self.gsettings = Gio.Settings(SETTINGS_SCHEMA)

    def get_tray_enabled(self):
        return self.gsettings.get_boolean(TRAY_KEY)

    def set_tray_enabled(self, enabled):
        self.gsettings.set_boolean(TRAY_KEY, enabled)

    def get_soft_blocked(self):
        return self.gsettings.get_boolean(BLOCK_KEY)

    def set_soft_blocked(self, blocked):
        self.gsettings.set_boolean(BLOCK_KEY, blocked)

    def get_state_managed(self):
        return self.gsettings.get_boolean(MANAGED_KEY)


