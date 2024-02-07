from dataclasses import dataclass


@dataclass
class ScanFreq:
    id: int
    pick_freq: float
    start_freq: float
    end_freq: float
    squelch: float
    spec: float
    detected: bool = True
    time: int = 0
    blocked: bool = False
    deleted: bool = False

    @property
    def band_width(self):
        return int(self.end_freq - self.start_freq)

    @property
    def center_freq(self):
        return self.start_freq + (self.end_freq - self.start_freq) / 2

    def intersect(self, freq):
        return self.start_freq <= freq.start_freq <= self.end_freq or self.start_freq <= freq.end_freq <= self.end_freq

    def distance(self, freq):
        if self.intersect(freq):
            return 0
        else:
            return (
                freq.start_freq - self.end_freq if self.pick_freq < freq.pick_freq else self.start_freq - freq.end_freq
            )
