import logging
import sys
import threading
import time
from collections import namedtuple

import spotify

from .util import calculate_duration

try:
    from queue import Queue, Empty
except ImportError:
    # python 2.7
    from Queue import Queue, Empty

logger = logging.getLogger(__name__)


class Sink(object):

    def __init__(self, device='default'):
        self._device_name = device

        import alsaaudio  # Crash early if not available
        self._alsaaudio = alsaaudio
        self._device = None

    def on_music_delivery(self, audio_format, frames, num_frames):
        assert (
            audio_format.sample_type == spotify.SampleType.INT16_NATIVE_ENDIAN)

        if self._device is None:
            mode = self._alsaaudio.PCM_NORMAL
            if hasattr(self._alsaaudio, 'pcms'):  # pyalsaaudio >= 0.8
                self._device = self._alsaaudio.PCM(
                    mode=mode,
                    device=self._device_name)
            else:  # pyalsaaudio == 0.7
                self._device = self._alsaaudio.PCM(
                    mode=mode, card=self._device_name)
            if sys.byteorder == 'little':
                self._device.setformat(self._alsaaudio.PCM_FORMAT_S16_LE)
            else:
                self._device.setformat(self._alsaaudio.PCM_FORMAT_S16_BE)
            self._device.setrate(audio_format.sample_rate)
            self._device.setchannels(audio_format.channels)
            self._device.setperiodsize(num_frames * audio_format.frame_size)

        return self._device.write(frames)


AudioFormat = namedtuple(
    'AudioFormat',
    ('sample_type', 'sample_rate', 'frame_size', 'channels')
)


class SpoppyAlsaSink(threading.Thread):

    def __init__(self, player, session, service_stop_event):
        self.play()
        self.player = player
        self.sink = Sink()
        self.audio_queue = Queue()
        super(SpoppyAlsaSink, self).__init__()
        self.service_stop_event = service_stop_event
        self._settings = None
        self.should_run = True
        self.seconds_sent = 0

    def clear(self):
        while True:
            try:
                self.audio_queue.get(False, 0)
            except Empty:
                break

    def pause(self):
        self.playing = False

    def play(self):
        self.playing = True

    def setup(self, sample_rate, num_frames):
        self._settings = {
            'sample_rate': sample_rate,
            'num_frames': num_frames
        }

    def run(self):
        while not self.service_stop_event.is_set():
            while not self.playing:
                time.sleep(.1)
            try:
                data = self.audio_queue.get(True, .5)
            except Empty:
                continue
            else:
                session, audio_format, frames, num_frames = data
                frame_duration = calculate_duration(
                    self._settings['num_frames'],
                    self._settings['sample_rate']
                )
                self.player.music_delivered(
                    audio_format.sample_rate, num_frames
                )
                self.sink.on_music_delivery(
                    audio_format, frames, num_frames
                )
        self.clear()

    def on_music_delivery(self, session, audio_format, frames, num_frames):
        if not self._settings:
            self.setup(audio_format.sample_rate, num_frames)
        cloned_format = AudioFormat(
            audio_format.sample_type, audio_format.sample_rate,
            audio_format.frame_size(), audio_format.channels
        )
        self.audio_queue.put((session, cloned_format, frames, num_frames))
        return num_frames
