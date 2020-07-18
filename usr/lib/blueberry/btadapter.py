
import subprocess
import re


class BtAdapter:
    def get_discoverable(self):
        try:
            output = subprocess.check_output(["bt-adapter", "-i"], timeout=2).decode("utf-8").strip()
            match = re.search("Discoverable: ([0|1]) \[rw\]", output)
            if match:
                return match.group(1) == '1'
        except Exception as e:
            pass
        return False

    def get_powered(self):
        try:
            output = subprocess.check_output(["bt-adapter", "-i"], timeout=2).decode("utf-8").strip()
            match = re.search("Powered: ([0|1]) \[rw\]", output)
            if match:
                return match.group(1) == '1'
        except Exception as e:
            pass
        return False

    def set_discoverabletimeout(self):
        try:
            output = subprocess.run(["bt-adapter", "--set", "DiscoverableTimeout", "300"], timeout=2, check=True,
                                    capture_output=True)
        except Exception:
            pass

    def poweron(self):
        try:
            output = subprocess.run(["bt-adapter", "--set", "Powered", "1" ], timeout=2, check=True,
                                    capture_output=True)
        except Exception:
            pass

    def make_discoverable(self, visible=True):
        try:
            output = subprocess.run(["bt-adapter", "--set", "Discoverable", "1" if visible else "0"], timeout=2, check=True,
                                    capture_output=True)
        except Exception:
            pass
