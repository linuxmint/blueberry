
import _thread as thread
import subprocess
import re
from gi.repository import GLib

RFKILL_CHK = ["/usr/sbin/rfkill", "list", "bluetooth"]
RFKILL_BLOCK = ["/usr/sbin/rfkill", "block", "bluetooth"]
RFKILL_UNBLOCK = ["/usr/sbin/rfkill", "unblock", "bluetooth"]

RFKILL_EVENT_MONITOR = ["/usr/lib/blueberry/safechild", "/usr/sbin/rfkill", "event"]

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
        res = subprocess.check_output(RFKILL_CHK).decode('utf-8')

        '''
        Assume the output of:

        > /usr/sbin/rfkill list bluetooth

        looks like:

        1: hci0: Bluetooth
            Soft blocked: yes
            Hard blocked: no
        '''

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
            thread.start_new_thread(self.event_monitor_thread, (None,))

    def event_monitor_thread(self, data):
        self.tproc = subprocess.Popen(RFKILL_EVENT_MONITOR, stdout=subprocess.PIPE, stdin=subprocess.PIPE)
        while self.tproc.poll() is None and not self.monitor_killer:
            l = self.tproc.stdout.readline().decode('utf-8') # This blocks until it receives a newline.
            self.update_state(l)

        self.tproc = None
        thread.exit()

    def update_state(self, line):
        self.debug("update_state line: %s" % line)

        '''
        Assume the output of:

        > /usr/bin/rfkill event

        looks like:

        1426095957.906704: idx 0 type 1 op 0 soft 0 hard 0
        1426095957.906769: idx 1 type 2 op 0 soft 1 hard 0
        1426096013.465033: idx 1 type 2 op 2 soft 0 hard 0

        or:

        2017-12-08 11:54:16,972291-0800: idx 0 type 2 op 0 soft 0 hard 0
        2017-12-08 11:54:16,972431-0800: idx 1 type 1 op 0 soft 0 hard 0
        2017-12-08 11:54:16,972474-0800: idx 4 type 2 op 0 soft 0 hard 0
        '''

        match = re.search(r'idx (?P<idx>\d+) type (?P<type>\d+) op (?P<op>\d+) soft (?P<soft>\d+) hard (?P<hard>\d+)', line)

        if not match:
            return

        if int(match.group('idx')) == self.adapter_index:
            self.soft_block = int(match.group('soft')) == 1
            self.hard_block = int(match.group('hard')) == 1

        self.update_ui()

    def update_ui(self):
        GLib.idle_add(self.output_callback)

    def try_set_blocked(self, blocked):
        thread.start_new_thread(self.set_block_thread, (blocked,))

    def set_block_thread(self, data):
        block = data

        if block:
            self.debug("set_block_thread blocking")
            self.blockproc = subprocess.Popen(RFKILL_BLOCK)
        else:
            self.debug("set_block_thread unblocking")
            self.blockproc = subprocess.Popen(RFKILL_UNBLOCK)

        while self.blockproc.poll() is None:
            pass

        self.blockproc = None
        self.debug("set_block_thread finished")
        thread.exit()

    def terminate(self):
        if self.blockproc:
            self.blockproc.kill()

    def debug(self, msg):
        if self.enable_debugging:
            print(msg)

