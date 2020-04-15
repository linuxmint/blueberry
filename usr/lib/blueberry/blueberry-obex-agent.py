#!/usr/bin/python3

# CREDITS
# --------
# This OBEX agent was ported from the Blueman project
# https://github.com/blueman-project/blueman
# where it was implemented by Christopher Schramm and Sander Sweers.

import dbus
import dbus.mainloop.glib
import dbus.service
import fcntl
import gettext
import gi
import os
import setproctitle
import shutil
import struct
import subprocess
import sys
import termios
import traceback

from datetime import datetime
from gi.types import GObjectMeta

gi.require_version("Gtk", "3.0")
gi.require_version('Notify', '0.7')

from gi.repository import GObject, GLib, Gtk, Gio, Notify

BOLD = lambda x: "\033[1m" + x + "\033[0m"

SHARED_PATH = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DOWNLOAD)
if SHARED_PATH is None or not os.path.exists(SHARED_PATH):
    SHARED_PATH = os.path.expanduser("~")

# i18n
gettext.install("blueberry", "/usr/share/locale")

setproctitle.setproctitle("blueberry-obex-agent")

Notify.init("Blueberry")

try:
    in_fg = os.getpgrp() == struct.unpack(str('h'), fcntl.ioctl(0, termios.TIOCGPGRP, "  "))[0]
except IOError:
    in_fg = 'DEBUG' in os.environ

def dprint(*args):
    #dont print if in the background
    if in_fg:

        s = ""
        for a in args:
            s += ("%s " % a)
        co = sys._getframe(1).f_code

        fname = BOLD(co.co_name)

        print("_________")
        print("%s %s" % (fname, "(%s:%d)" % (co.co_filename, co.co_firstlineno)))
        print(s)
        try:
            sys.stdout.flush()
        except IOError:
            pass

class _GDbusObjectType(dbus.service.InterfaceType, GObjectMeta):
    pass

_GDBusObject = _GDbusObjectType(str('_GDBusObject'), (dbus.service.Object, GObject.GObject), {})

# noinspection PyPep8Naming
class Agent(_GDBusObject, dbus.service.Object, GObject.GObject):
    __gsignals__ = {
        str('release'): (GObject.SignalFlags.NO_HOOKS, None, ()),
        str('authorize'): (GObject.SignalFlags.NO_HOOKS, None, (GObject.TYPE_PYOBJECT, GObject.TYPE_PYOBJECT,
                                                                GObject.TYPE_PYOBJECT, GObject.TYPE_PYOBJECT)),
        str('cancel'): (GObject.SignalFlags.NO_HOOKS, None, ()),
    }

    def __init__(self, agent_path):
        self._agent_path = agent_path
        dbus.service.Object.__init__(self, dbus.SessionBus(), agent_path)
        GObject.GObject.__init__(self)
        self._reply_handler = None
        self._error_handler = None

    @dbus.service.method('org.bluez.obex.Agent1')
    def Release(self):
        dprint(self._agent_path)
        self.emit('release')

    @dbus.service.method('org.bluez.obex.Agent1', async_callbacks=('reply_handler', 'error_handler'))
    def AuthorizePush(self, transfer_path, reply_handler, error_handler):
        dprint(self._agent_path, transfer_path)
        self._reply_handler = reply_handler
        self._error_handler = error_handler
        self.emit('authorize', transfer_path, None, None, None)

    @dbus.service.method('org.bluez.obex.Agent1')
    def Cancel(self):
        dprint(self._agent_path)
        self.emit('cancel')

    @dbus.service.method('org.bluez.obex.Agent', async_callbacks=('reply_handler', 'error_handler'))
    def Authorize(self, transfer_path, bt_address, name, _type, length, _time, reply_handler, error_handler):
        dprint(self._agent_path, transfer_path, bt_address, name, length)
        self._reply_handler = reply_handler
        self._error_handler = error_handler
        self.emit('authorize', transfer_path, bt_address, name, length)

    @dbus.service.method('org.bluez.obex.Agent')
    def Cancel(self):
        dprint(self._agent_path)
        self.emit('cancel')

    def reply(self, reply):
        dprint(self._agent_path, reply)
        self._reply_handler(reply)
        self._reply_handler = None
        self._error_handler = None

    def reply_cancelled(self, reply):
        dprint(self._agent_path, reply)
        self._error_handler(dbus.DBusException(name=('org.bluez.obex.Error.Canceled')))
        self._reply_handler = None
        self._error_handler = None

    def reply_rejected(self, reply):
        dprint(self._agent_path, reply)
        self._error_handler(dbus.DBusException(name=('org.bluez.obex.Error.Rejected')))
        self._reply_handler = None
        self._error_handler = None

class SignalTracker:
    def __init__(self):
        self._signals = []

    def Handle(self, *args, **kwargs):
        if "sigid" in kwargs:
            sigid = kwargs["sigid"]
            del kwargs["sigid"]
        else:
            sigid = None

        objtype = args[0]
        obj = args[1]
        args = args[2:]

        if objtype == "bluez":
            obj.handle_signal(*args, **kwargs)
        elif objtype == "gobject":
            args = obj.connect(*args)
        elif objtype == "dbus":
            if isinstance(obj, dbus.Bus):
                obj.add_signal_receiver(*args, **kwargs)
            else:
                print("Deprecated use of dbus signaltracker")
                traceback.print_stack()
                obj.bus.add_signal_receiver(*args, **kwargs)

        self._signals.append((sigid, objtype, obj, args, kwargs))

    def Disconnect(self, sigid):
        for sig in self._signals:
            (_sigid, objtype, obj, args, kwargs) = sig
            if sigid != None and _sigid == sigid:
                if objtype == "bluez":
                    obj.unhandle_signal(*args)
                elif objtype == "gobject":
                    obj.disconnect(args)
                elif objtype == "dbus":
                    if isinstance(obj, dbus.Bus):
                        if "path" in kwargs:
                            obj.remove_signal_receiver(*args, **kwargs)
                        else:
                            obj.remove_signal_receiver(*args)
                    else:
                        obj.bus.remove_signal_receiver(*args)

                self._signals.remove(sig)


    def DisconnectAll(self):
        for sig in self._signals:

            (sigid, objtype, obj, args, kwargs) = sig
            if objtype == "bluez":
                obj.unhandle_signal(*args)
            elif objtype == "gobject":
                obj.disconnect(args)
            elif objtype == "dbus":
                if isinstance(obj, dbus.Bus):
                    if "path" in kwargs:
                        obj.remove_signal_receiver(*args, **kwargs)
                    else:
                        obj.remove_signal_receiver(*args)
                else:
                    obj.bus.remove_signal_receiver(*args)

        self._signals = []

class NotificationBubble(Notify.Notification):

    @staticmethod
    def actions_supported():
        return "actions" in Notify.get_server_caps()

    def __new__(cls, summary, message, timeout=-1, actions=None, actions_cb=None):
        self = Notify.Notification.new(summary, message, None)

        def on_notification_closed(n, *args):
            self.disconnect(closed_sig)
            if actions_cb:
                actions_cb(n, "closed")

        def on_action(n, action, *args):
            self.disconnect(closed_sig)
            actions_cb(n, action)

        self.set_icon_from_pixbuf(Gtk.IconTheme.get_default().load_icon("blueberry", 48, 0))

        if actions:
            for action in actions:
                self.add_action(action[0], action[1], on_action, None)
            self.add_action("default", "Default Action", on_action, None)

        closed_sig = self.connect("closed", on_notification_closed)
        if timeout != -1:
            self.set_timeout(timeout)

        self.show()

        return self

class _Agent:
    def __init__(self):
        self._agent_path = '/org/blueberry/obex_agent'

        self._agent = Agent(self._agent_path)
        self._agent.connect('release', self._on_release)
        self._agent.connect('authorize', self._on_authorize)
        self._agent.connect('cancel', self._on_cancel)

        self._allowed_devices = []
        self._notification = None
        self._pending_transfer = None
        self.transfers = {}

        AgentManager().register_agent(self._agent_path)

    def __del__(self):
        AgentManager().unregister_agent(self._agent_path)

    def _on_release(self, _agent):
        raise Exception(self._agent_path + " was released unexpectedly")

    def _on_action(self, _notification, action):
        dprint(action)

        if action == "accept":
            self.transfers[self._pending_transfer['transfer_path']] = {
                'path': self._pending_transfer['root'] + '/' + os.path.basename(self._pending_transfer['filename']),
                'size': self._pending_transfer['size'],
                'name': self._pending_transfer['name']
            }
            self._agent.reply(self.transfers[self._pending_transfer['transfer_path']]['path'])
            self._allowed_devices.append(self._pending_transfer['address'])
            GObject.timeout_add(60000, self._allowed_devices.remove, self._pending_transfer['address'])
        else:
            self._agent.reply_rejected(None)

    def _on_authorize(self, _agent, transfer_path, address=None, filename=None, size=None):
        if address and filename and size:
            # stand-alone obexd
            # FIXME: /tmp is only the default. Can we get the actual root
            # directory from stand-alone obexd?
            root = '/tmp'
            name = _("Unknown device")
        else:
            # BlueZ 5 integrated obexd
            transfer = Transfer(transfer_path)
            session = Session(transfer.session)
            root = session.root
            address = session.address
            filename = transfer.name
            size = transfer.size
            name = get_device_name_by_address(session.address)

        self._pending_transfer = {'transfer_path': transfer_path, 'address': address, 'root': root,
                                  'filename': filename, 'size': size, 'name': name}

        try:
            name = str("<b>%s</b>" % name)
            filename = str("<b>%s</b>" % filename)
        except Exception as e:
            print (e)

        # This device was not allowed yet -> ask for confirmation
        if address not in self._allowed_devices:
            self._notification = NotificationBubble(_("Incoming file over Bluetooth"),
                _("Incoming file %(0)s from %(1)s") % {"0": filename, "1": name},
                30000, [["accept", _("Accept"), "help-about"], ["reject", _("Reject"), "help-about"]], self._on_action)
        # Device was already allowed, larger file -> display a notification, but auto-accept
        elif size > 350000:
            self._notification = NotificationBubble(_("Receiving file"),
                _("Receiving file %(0)s from %(1)s") % {"0": filename, "1": name})
            self._on_action(self._notification, 'accept')
        # Device was already allowed. very small file -> auto-accept and transfer silently
        else:
            self._notification = None
            self._on_action(self._notification, "accept")

    def _on_cancel(self, agent):
        self._notification.close()
        agent.reply_cancelled(None)


class TransferService():
    _silent_transfers = 0
    _normal_transfers = 0

    _manager = None
    _agent = None
    _watch = None

    def load(self):
        self._manager = Manager()
        self._manager.connect("transfer-started", self._on_transfer_started)
        self._manager.connect("transfer-completed", self._on_transfer_completed)
        self._manager.connect('session-removed', self._on_session_removed)

        self._watch = dbus.SessionBus().watch_name_owner("org.bluez.obex", self._on_obex_owner_changed)

    def unload(self):
        if self._watch:
            self._watch.cancel()

        self._agent = None

    def on_manager_state_changed(self, state):
        if not state:
            self._agent = None

    def _on_obex_owner_changed(self, owner):
        dprint("obex owner changed:", owner)
        if owner == "":
            self._agent = None
        else:
            self._agent = _Agent()

    def _on_transfer_started(self, _manager, transfer_path):
        if transfer_path not in self._agent.transfers:
            # This is not an incoming transfer we authorized
            return

        if self._agent.transfers[transfer_path]['size'] > 350000:
            self._normal_transfers += 1
        else:
            self._silent_transfers += 1

    @staticmethod
    def _add_open(n, name, path):
        if NotificationBubble.actions_supported():
            print("adding action")

            def on_open(*_args):
                print("open")
                subprocess.Popen(['xdg-open', path])

            n.add_action("open", name, on_open, None)
            n.show()

    def _on_transfer_completed(self, _manager, transfer_path, success):
        try:
            attributes = self._agent.transfers[transfer_path]
        except KeyError:
            # This is probably not an incoming transfer we authorized
            return

        src = attributes['path']
        dest_dir = SHARED_PATH
        filename = os.path.basename(src)

        # We get bytes from pygobject under python 2.7
        if hasattr(dest_dir, "upper",) and hasattr(dest_dir, "decode"):
            dest_dir = dest_dir.decode("UTF-8")

        if os.path.exists(os.path.join(dest_dir, filename)):
            now = datetime.now()
            filename = "%s_%s" % (now.strftime("%Y%m%d%H%M%S"), filename)
            dprint("Destination file exists, renaming to: %s" % filename)

        dest = os.path.join(dest_dir, filename)
        shutil.move(src, dest)

        attr = attributes['name']
        try:
            filename = str("<b>%s</b>" % filename)
            attr = str("<b>%s</b>" % attr)
        except Exception as e:
            print(e)

        if success:
            n = NotificationBubble(_("File received"),
                             _("File %(0)s from %(1)s successfully received") % {
                                 "0": filename,
                                 "1": attr})
            self._add_open(n, _("Open"), dest)
        elif not success:
            NotificationBubble(_("Transfer failed"),
                         _("Transfer of file %(0)s failed") % {
                             "0": filename,
                             "1": attr})

            if attributes['size'] > 350000:
                self._normal_transfers -= 1
            else:
                self._silent_transfers -= 1

        del self._agent.transfers[transfer_path]

    def _on_session_removed(self, _manager, _session_path):
        if self._silent_transfers == 0:
            return

        if self._normal_transfers == 0:
            n = NotificationBubble(_("Files received"),
                             ngettext("Received %d file in the background", "Received %d files in the background",
                                      self._silent_transfers) % self._silent_transfers)

            self._add_open(n, _("Open"), SHARED_PATH)
        else:
            n = NotificationBubble(_("Files received"),
                             ngettext("Received %d more file in the background",
                                      "Received %d more files in the background",
                                      self._silent_transfers) % self._silent_transfers)
            self._add_open(n, _("Open"), SHARED_PATH)

class ObexdNotFoundError(Exception):
    pass

class Base(GObject.GObject):
    interface_version = None

    @staticmethod
    def get_interface_version():
        if not Base.interface_version:
            obj = dbus.SessionBus().get_object('org.bluez.obex', '/')
            introspection = dbus.Interface(obj, 'org.freedesktop.DBus.Introspectable').Introspect()
            if 'org.freedesktop.DBus.ObjectManager' in introspection:
                dprint('Detected BlueZ integrated obexd')
                Base.interface_version = [5]
            elif 'org.bluez.obex.Manager' in introspection:
                dprint('Detected standalone obexd')
                Base.interface_version = [4]
            else:
                raise ObexdNotFoundError('Could not find any compatible version of obexd')

        return Base.interface_version

    def __init__(self, interface_name, obj_path, legacy_client_bus=False):
        self.__signals = SignalTracker()
        self.__obj_path = obj_path
        self.__interface_name = interface_name
        self.__bus = dbus.SessionBus()
        self.__bus_name = 'org.bluez.obex.client' if legacy_client_bus else 'org.bluez.obex'
        self.__dbus_proxy = self.__bus.get_object(self.__bus_name, obj_path, follow_name_owner_changes=True)
        self.__interface = dbus.Interface(self.__dbus_proxy, interface_name)
        super(Base, self).__init__()

    def __del__(self):
        self.__signals.DisconnectAll()

    def _handle_signal(self, handler, signal):
        self.__signals.Handle('dbus', self.__bus, handler, signal, self.__interface_name, self.__bus_name,
                              self.__obj_path)

    @property
    def _interface(self):
        return self.__interface

    @property
    def object_path(self):
        return self.__obj_path

class Session(Base):
    def __init__(self, session_path):
        if self.__class__.get_interface_version()[0] < 5:
            super(Session, self).__init__('org.bluez.obex.Session', session_path)
        else:
            super(Session, self).__init__('org.freedesktop.DBus.Properties', session_path)

    @property
    def address(self):
        if self.__class__.get_interface_version()[0] < 5:
            return self._interface.GetProperties()['Address']
        else:
            return self._interface.Get('org.bluez.obex.Session1', 'Destination')

    @property
    def target(self):
        if self.__class__.get_interface_version()[0] < 5:
            return self.address()
        else:
            return self._interface.Get('org.bluez.obex.Session1', 'Destination')

    @property
    def root(self):
        if self.__class__.get_interface_version()[0] < 5:
            raise NotImplementedError()
        else:
            return self._interface.Get('org.bluez.obex.Session1', 'Root')

class Transfer(Base):
    __gsignals__ = {
        str('progress'): (GObject.SignalFlags.NO_HOOKS, None, (GObject.TYPE_PYOBJECT,)),
        str('completed'): (GObject.SignalFlags.NO_HOOKS, None, ()),
        str('error'): (GObject.SignalFlags.NO_HOOKS, None, (GObject.TYPE_PYOBJECT,))
    }

    def __init__(self, transfer_path):
        if self.__class__.get_interface_version()[0] < 5:
            super(Transfer, self).__init__('org.bluez.obex.Transfer', transfer_path, True)

            handlers = {
                'PropertyChanged': self._on_property_changed,
                'Complete': self._on_complete,
                'Error': self._on_error
            }

            for signal, handler in handlers.items():
                self._handle_signal(handler, signal)
        else:
            super(Transfer, self).__init__('org.freedesktop.DBus.Properties', transfer_path)
            self._handle_signal(self._on_properties_changed, 'PropertiesChanged')

    def __getattr__(self, name):
        if name in ('filename', 'name', 'session', 'size'):
            if self.__class__.get_interface_version()[0] < 5:
                raise NotImplementedError()
            else:
                return self._interface.Get('org.bluez.obex.Transfer1', name.capitalize())

    def _on_property_changed(self, name, value):
        if name == 'Progress':
            dprint(self.object_path, name, value)
            self.emit('progress', value)

    def _on_complete(self):
        dprint(self.object_path)
        self.emit('completed')

    def _on_error(self, code, message):
        dprint(self.object_path, code, message)
        self.emit('error', message)

    def _on_properties_changed(self, interface_name, changed_properties, _invalidated_properties):
        if interface_name != 'org.bluez.obex.Transfer1':
            return

        for name, value in changed_properties.items():
            dprint(self.object_path, name, value)
            if name == 'Transferred':
                self.emit('progress', value)
            elif name == 'Status':
                if value == 'complete':
                    self.emit('completed')
                elif value == 'error':
                    self.emit('error', None)

class Manager(Base):
    __gsignals__ = {
        str('session-removed'): (GObject.SignalFlags.NO_HOOKS, None, (GObject.TYPE_PYOBJECT,)),
        str('transfer-started'): (GObject.SignalFlags.NO_HOOKS, None, (GObject.TYPE_PYOBJECT,)),
        str('transfer-completed'): (GObject.SignalFlags.NO_HOOKS, None, (GObject.TYPE_PYOBJECT, GObject.TYPE_PYOBJECT)),
    }

    def __init__(self):
        if self.__class__.get_interface_version()[0] < 5:
            super(Manager, self).__init__('org.bluez.obex.Manager', '/')
            handlers = {
                'SessionRemoved': self._on_session_removed,
                'TransferStarted': self._on_transfer_started,
                'TransferCompleted': self._on_transfer_completed
            }

            for signal, handler in handlers.items():
                self._handle_signal(handler, signal, )

        else:
            super(Manager, self).__init__('org.freedesktop.DBus.ObjectManager', '/')

            self._transfers = {}

            def on_interfaces_added(object_path, interfaces):
                if 'org.bluez.obex.Transfer1' in interfaces:
                    def on_tranfer_completed(_transfer):
                        self._on_transfer_completed(object_path, True)

                    def on_tranfer_error(_transfer, _msg):
                        self._on_transfer_completed(object_path, False)

                    self._transfers[object_path] = Transfer(object_path)
                    self._transfers[object_path].connect('completed', on_tranfer_completed)
                    self._transfers[object_path].connect('error', on_tranfer_error)
                    self._on_transfer_started(object_path)

            self._handle_signal(on_interfaces_added, 'InterfacesAdded')

            def on_interfaces_removed(object_path, interfaces):
                if 'org.bluez.obex.Session1' in interfaces:
                    self._on_session_removed(object_path)

            self._handle_signal(on_interfaces_removed, 'InterfacesRemoved')

    def _on_session_removed(self, session_path):
        dprint(session_path)
        self.emit('session-removed', session_path)

    def _on_transfer_started(self, transfer_path):
        dprint(transfer_path)
        self.emit('transfer-started', transfer_path)

    def _on_transfer_completed(self, transfer_path, success):
        dprint(transfer_path, success)
        self.emit('transfer-completed', transfer_path, success)

class ObjectPush(Base):
    __gsignals__ = {
        str('transfer-started'): (GObject.SignalFlags.NO_HOOKS, None, (GObject.TYPE_PYOBJECT, GObject.TYPE_PYOBJECT,)),
        str('transfer-failed'): (GObject.SignalFlags.NO_HOOKS, None, (GObject.TYPE_PYOBJECT,)),
    }

    def __init__(self, session_path):
        if self.__class__.get_interface_version()[0] < 5:
            super(ObjectPush, self).__init__('org.bluez.obex.ObjectPush', session_path, True)
        else:
            super(ObjectPush, self).__init__('org.bluez.obex.ObjectPush1', session_path)

    def send_file(self, file_path):
        def on_transfer_started(*params):
            transfer_path, props = params[0] if self.__class__.get_interface_version()[0] < 5 else params
            dprint(self.object_path, file_path, transfer_path)
            self.emit('transfer-started', transfer_path, props['Filename'])

        def on_transfer_error(error):
            dprint(file_path, error)
            self.emit('transfer-failed', error)

        self._interface.SendFile(file_path, reply_handler=on_transfer_started, error_handler=on_transfer_error)

    def get_session_path(self):
        return self.object_path

class Client(Base):
    __gsignals__ = {
        str('session-created'): (GObject.SignalFlags.NO_HOOKS, None, (GObject.TYPE_PYOBJECT,)),
        str('session-failed'): (GObject.SignalFlags.NO_HOOKS, None, (GObject.TYPE_PYOBJECT,)),
        str('session-removed'): (GObject.SignalFlags.NO_HOOKS, None, ()),
    }

    def __init__(self):
        if self.__class__.get_interface_version()[0] < 5:
            super(Client, self).__init__('org.bluez.obex.Client', '/', True)
        else:
            super(Client, self).__init__('org.bluez.obex.Client1', '/org/bluez/obex')

    def create_session(self, dest_addr, source_addr="00:00:00:00:00:00", pattern="opp"):
        def on_session_created(session_path):
            dprint(dest_addr, source_addr, pattern, session_path)
            self.emit("session-created", session_path)

        def on_session_failed(error):
            dprint(dest_addr, source_addr, pattern, error)
            self.emit("session-failed", error)

        self._interface.CreateSession(dest_addr, {"Source": source_addr, "Target": pattern},
                                      reply_handler=on_session_created, error_handler=on_session_failed)

    def remove_session(self, session_path):
        def on_session_removed():
            dprint(session_path)
            self.emit('session-removed')

        def on_session_remove_failed(error):
            dprint(session_path, error)

        self._interface.RemoveSession(session_path, reply_handler=on_session_removed,
                                      error_handler=on_session_remove_failed)

class AgentManager(Base):
    def __init__(self):
        if self.__class__.get_interface_version()[0] < 5:
            super(AgentManager, self).__init__('org.bluez.obex.Manager', '/')
        else:
            super(AgentManager, self).__init__('org.bluez.obex.AgentManager1', '/org/bluez/obex')

    def register_agent(self, agent_path):
        def on_registered():
            dprint(agent_path)

        def on_register_failed(error):
            dprint(agent_path, error)

        self._interface.RegisterAgent(agent_path, reply_handler=on_registered, error_handler=on_register_failed)

    def unregister_agent(self, agent_path):
        def on_unregistered():
            dprint(agent_path)

        def on_unregister_failed(error):
            dprint(agent_path, error)

        self._interface.UnregisterAgent(agent_path, reply_handler=on_unregistered, error_handler=on_unregister_failed)


def get_device_name_by_address(address):
    text = subprocess.check_output(["bt-device", "--info=" + address]).decode("utf-8").strip()

    for line in text.splitlines():
        line = line.strip()
        if line.startswith("Name:"):
            return line[5:].strip()

    raise ValueError


if __name__ == '__main__':
    settings = Gio.Settings(schema="org.blueberry")
    if settings.get_boolean("obex-enabled"):
        try:
            dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
            mainloop = GLib.MainLoop()
            service = TransferService()
            service.load()
            cont = True
            while cont:
                try:
                    mainloop.run()
                except KeyboardInterrupt:
                    service.unload()
                    cont = False
        except Exception as e:
            dprint("Something went wrong in blueberry-obex-agent: %s" % e)
            dprint("Setting org.blueberry obex-enabled to False and exiting.")
            settings.set_boolean("obex-enabled", False)
    else:
        dprint("org.blueberry obex-enabled is False, exiting.")
