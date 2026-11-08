# firmware/pico/drive/comm.py
#
# The Pico's side of the USB serial link to the Pi: line in, line out.
#
# What it decides: when a complete line has arrived. The loop must never wait
# on the Pi. A half-sent line is held in a buffer and handed over only when
# its newline arrives, so the failsafe check keeps running every pass. (Calling
# readline() as soon as one byte is ready would block until the newline came,
# freezing the loop, failsafe included.)
#
# Two parts:
#   LineBuffer - pure: characters in, complete lines out. Host-tested in
#                tests/test_pico_comm.py.
#   Link       - the hardware part (USB serial via sys.stdin/stdout). Only this
#                touches the board, and it imports nothing until it is created,
#                so the host tests can import this file.

MAX_LINE = 64   # longer lines are junk: dropped, and reported as BAD by main.py


class LineBuffer:
    def __init__(self, max_line=MAX_LINE):
        self.max_line = max_line
        self._buf = []
        self._overflow = False

    def push(self, ch):
        """Add one character. Returns a complete line (no newline), or None.
        A line that grew past max_line comes back as the marker OVERFLOW."""
        if ch == "\n" or ch == "\r":
            if not self._buf and not self._overflow:
                return None              # blank line, or the \n of a \r\n
            line = OVERFLOW if self._overflow else "".join(self._buf)
            self._buf = []
            self._overflow = False
            return line
        if self._overflow:
            return None
        if len(self._buf) >= self.max_line:
            self._overflow = True
            self._buf = []
            return None
        self._buf.append(ch)
        return None


OVERFLOW = "<overflow>"


def format_msg(tag, *fields):
    """One reply line, e.g. format_msg("OK", 250, -100) -> "OK 250 -100"."""
    return " ".join([tag] + [str(f) for f in fields])


class Link:
    """USB serial on the Pico. Non-blocking: poll() returns at most a few
    complete lines and never waits."""

    MAX_CHARS_PER_POLL = 128   # bound the time one poll() can take

    def __init__(self):
        import sys
        try:
            import uselect as select
        except ImportError:
            import select
        self._stdin = sys.stdin
        self._stdout = sys.stdout
        self._poller = select.poll()
        self._poller.register(sys.stdin, select.POLLIN)
        self._lines = LineBuffer()
        self.rx_lines = 0     # complete lines received since boot
        self.tx_lines = 0

    def poll(self):
        """Read whatever has arrived. Returns a list of complete lines."""
        out = []
        for _ in range(self.MAX_CHARS_PER_POLL):
            if not self._poller.poll(0):
                break
            line = self._lines.push(self._stdin.read(1))
            if line is not None:
                out.append(line)
        self.rx_lines += len(out)
        return out

    def send(self, tag, *fields):
        self._stdout.write(format_msg(tag, *fields) + "\n")
        self.tx_lines += 1
