
import thread
import subprocess
import os
from gi.repository import GObject, Gio, GLib
import signal

RFKILL_CHK = ["/usr/sbin/rfkill", "list", "bluetooth"]
RFKILL_BLOCK = ["/usr/sbin/rfkill", "block", "bluetooth"]
RFKILL_UNBLOCK = ["/usr/sbin/rfkill", "unblock", "bluetooth"]

RFKILL_EVENT_MONITOR = ["/usr/lib/blueberry/safechild", "/usr/sbin/rfkill", "event"]

# index of .split() from rfkill event output where lines are:
#     1426095957.906704: idx 0 type 1 op 0 soft 0 hard 0
#     1426095957.906769: idx 1 type 2 op 0 soft 1 hard 0
#     1426096013.465033: idx 1 type 2 op 2 soft 0 hard 0

EVENT_INDEX_DEVICE = 2
EVENT_INDEX_SOFT_BLOCK = 8
EVENT_INDEX_HARD_BLOCK = 10

class Interface:
    def __init__(self, output_callback, debug):
        self.enable_debugging = debug
        self.output_callback = output_callback
        self.have_adapter = False
        self.adapter_index = -1

        self.tproc = None
        self.blockproc = None

        self.hard_block = False
        self.soft_block = False

        self.monitor_killer = False

        self.have_adapter = self.adapter_check()

        if self.have_adapter:
            self.start_event_monitor()

    def adapter_check(self):
        # res = subprocess.check_output(RFKILL_CHK)

        try:
            proc = Gio.Subprocess.new(RFKILL_CHK, Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_PIPE)

            ret, out, err = proc.communicate(None, None)
        except GLib.Error as e:
            print(e.message)
            return

        '''
        Assume the output of:

        > /usr/sbin/rfkill list bluetooth

        looks like:

        1: hci0: Bluetooth
            Soft blocked: yes
            Hard blocked: no
        '''

        res = out.get_data().decode()

        self.debug("adapter_check full output:\n%s" % res)

        if not res:
            self.debug("adapter_check no output (no adapter)")
            self.have_adapter = False
            return False

        reslines = res.split('\n')
        for line in reslines:
            if "Bluetooth" in line:
                self.adapter_index = int(line[0])
                self.debug("adapter_check found adapter at %d" % self.adapter_index)
                return True

        return False

    def start_event_monitor(self):
        if not self.tproc and not self.monitor_killer:
            self.tproc = Gio.Subprocess.new(RFKILL_EVENT_MONITOR,
                                            Gio.SubprocessFlags.STDIN_PIPE |
                                            Gio.SubprocessFlags.STDOUT_PIPE |
                                            Gio.SubprocessFlags.STDERR_SILENCE)

            stream = Gio.DataInputStream.new(self.tproc.get_stdout_pipe())
            stream.read_line_async(GLib.PRIORITY_DEFAULT, None, self.on_event_line_read, None)

            self.tproc.wait_async(None, self.on_event_mon_terminated, stream)

    def on_event_line_read(self, stream, result, data=None):
        line, length = stream.read_line_finish_utf8(result)

        if line != None:
            self.update_state(line)

        if not self.monitor_killer:
            stream.read_line_async(GLib.PRIORITY_DEFAULT, None, self.on_event_line_read, None)

    def on_event_mon_terminated(self, process, result, data=None):
        stream = data
        stream.clear_pending()
        stream.close()

        self.tproc = None

    def update_state(self, line):
        self.debug("update_state line: %s" % line)

        elements = line.split()

        if len(elements) < EVENT_INDEX_HARD_BLOCK:
            return

        if int(elements[EVENT_INDEX_DEVICE]) == self.adapter_index:
            self.soft_block = int(elements[EVENT_INDEX_SOFT_BLOCK]) == 1
            self.hard_block = int(elements[EVENT_INDEX_HARD_BLOCK]) == 1

        self.output_callback()

    def try_set_blocked(self, blocked):
        thread.start_new_thread(self.set_block_thread, (blocked,))

    def set_block_thread(self, data):
        block = data

        block_cmd = None

        if block:
            self.debug("set_block_thread blocking")
            block_cmd = RFKILL_BLOCK
        else:
            self.debug("set_block_thread unblocking")
            block_cmd = RFKILL_UNBLOCK

        self.blockproc = Gio.Subprocess.new(block_cmd, Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_PIPE)

        try:
            self.blockproc.wait(None)
        except GLib.Error as e:
            print(e.message)

        self.blockproc = None
        self.debug("set_block_thread finished")
        thread.exit()

    def debug(self, msg):
        if self.enable_debugging:
            print(msg)

