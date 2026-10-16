"""Value Change Dump (VCD) waveform generator compliant with IEEE 1364-1995."""

import io
from typing import Dict, List, Optional, Tuple, Union


class VCDTracer:
    """Waveform signal tracer for hardware logic analyzer inspection in PulseView / GTKWave."""

    def __init__(self, timescale: str = "1ns") -> None:
        self.timescale = timescale
        # Signal name -> (identifier, width)
        self._signals: Dict[str, Tuple[str, int]] = {}
        # Signal name -> current value
        self._current_values: Dict[str, int] = {}
        # Changes: list of (timestamp, identifier, width, value)
        self._changes: List[Tuple[int, str, int, int]] = []
        self._id_counter: int = 0
        self._timestamp: int = 0

    def _next_id(self) -> str:
        """Generate short ASCII identifier for VCD tokens."""
        char_idx = self._id_counter % 26
        token = chr(ord('!') + char_idx)
        self._id_counter += 1
        return token

    def register_signal(self, name: str, width: int = 1, initial_value: int = 0) -> None:
        """Register a digital signal or bus."""
        if name in self._signals:
            return
        token = self._next_id()
        self._signals[name] = (token, width)
        self._current_values[name] = initial_value & ((1 << width) - 1)
        self._changes.append((0, token, width, self._current_values[name]))

    def set_time(self, timestamp: int) -> None:
        """Advance simulation time in units of timescale."""
        self._timestamp = timestamp

    def change(self, name: str, value: int, timestamp: Optional[int] = None) -> None:
        """Log a signal state change."""
        if name not in self._signals:
            return
        t = self._timestamp if timestamp is None else timestamp
        token, width = self._signals[name]
        val = value & ((1 << width) - 1)
        if self._current_values.get(name) != val:
            self._current_values[name] = val
            self._changes.append((t, token, width, val))

    def generate(self) -> str:
        """Generate standard VCD header and event stream as a string."""
        buf = io.StringIO()
        # VCD Header
        buf.write("$date\n   2026-10-16\n$end\n")
        buf.write("$version\n   BoardLens VCD Waveform Tracer 1.0\n$end\n")
        buf.write(f"$timescale\n   {self.timescale}\n$end\n")
        buf.write("$scope module boardlens $end\n")

        for name, (token, width) in self._signals.items():
            sig_type = "wire"
            buf.write(f"$var {sig_type} {width} {token} {name} $end\n")

        buf.write("$upscope $end\n")
        buf.write("$enddefinitions $end\n")

        # Initial dumpvars
        buf.write("$dumpvars\n")
        initial_changes = [c for c in self._changes if c[0] == 0]
        for _, token, width, val in initial_changes:
            if width == 1:
                buf.write(f"{val}{token}\n")
            else:
                buf.write(f"b{val:0{width}b} {token}\n")
        buf.write("$end\n")

        # Time sorted changes
        last_t = 0
        sorted_changes = sorted(self._changes, key=lambda c: c[0])
        for t, token, width, val in sorted_changes:
            if t > last_t:
                buf.write(f"#{t}\n")
                last_t = t
            elif t == 0:
                continue

            if width == 1:
                buf.write(f"{val}{token}\n")
            else:
                buf.write(f"b{val:0{width}b} {token}\n")

        return buf.getvalue()

    def write_to_file(self, filepath: str) -> None:
        """Write VCD trace to disk."""
        content = self.generate()
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
