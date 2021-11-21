import asyncio
from typing import Dict

from .exceptions import MusicCastException
from .features import ZoneFeature


class MusicCastAlarmDetails:
    def __init__(self):
        self.enabled = None
        self.time = None
        self.playback_type = None
        self.resume_input = None
        self.preset = None
        self.preset_type = None
        self.preset_info = None
        self.beep = None

    @property
    def input(self):
        return (f"preset:{self.preset_type}:{self.preset}"
                if self.playback_type == "preset" else
                f"resume:{self.resume_input}"
                if self.playback_type == "resume" else None)


class MusicCastData:
    """Object that holds data for a MusicCast device."""

    def __init__(self):
        """Ctor."""
        # device info
        self.device_id = None
        self.model_name = None
        self.system_version = None
        self.api_version = None

        # network status
        self.mac_addresses = None
        self.network_name = None

        # features
        self.zones: Dict[str, MusicCastZoneData] = {}
        self.input_names: Dict[str, str] = {}

        # NetUSB data
        self.netusb_input = None
        self.netusb_playback = None
        self.netusb_repeat = None
        self.netusb_shuffle = None
        self.netusb_artist = None
        self.netusb_album = None
        self.netusb_track = None
        self.netusb_albumart_url = None
        self.netusb_play_time = None
        self.netusb_play_time_updated = None
        self.netusb_total_time = None

        self.netusb_preset_list = {}

        # Tuner
        self.band = None
        self.am_freq = 1
        self.fm_freq = 1
        self.rds_text_a = ""
        self.rds_text_b = ""

        self.dab_service_label = ""
        self.dab_dls = ""

        # Group
        self.last_group_role = None
        self.last_group_id = None
        self.group_id = None
        self.group_name = None
        self.group_role = None
        self.group_server_zone = None
        self.group_client_list = []
        self.group_update_lock = asyncio.locks.Lock()

        # Dimmer
        self.dimmer: Dimmer | None = None

        # Alarm
        self.alarm_on = None
        self.alarm_volume = None
        self.alarm_volume_range = (0, 0)
        self.alarm_volume_step = 1
        self.alarm_fade_range = (0, 0)
        self.alarm_fade_step = 1
        self.alarm_resume_input_list = []
        self.alarm_preset_list = []
        self.alarm_mode = None
        self.alarm_details: Dict[str, MusicCastAlarmDetails] = {}

        # Speaker A/B
        self.speaker_a: bool | None = None
        self.speaker_b: bool | None = None

        self.party_enable: bool | None = None

        self.capabilities = []

    @property
    def fm_freq_str(self):
        """Return a formatted string with fm frequency."""
        return "FM {:.2f} MHz".format(self.fm_freq / 1000)

    @property
    def am_freq_str(self):
        """Return a formatted string with am frequency."""
        return f"AM {self.am_freq:.2f} KHz"


class MusicCastZoneData:
    """Object that holds data for a MusicCast device zone."""

    features: ZoneFeature = ZoneFeature.NONE

    def __init__(self):
        """Ctor."""
        self.power = None
        self.name: str | None = None
        self.min_volume = 0
        self.max_volume = 100
        self.current_volume = 0
        self.mute: bool = False
        self.input_list = []
        self.input = None
        self.sound_program_list = []
        self.sound_program = None
        self.sleep_time = None

        # Equalizer
        self.equalizer_mode = None
        self.equalizer_low = None
        self.equalizer_mid = None
        self.equalizer_high = None

        # Tone Control
        self.tone_mode = None
        self.tone_bass = None
        self.tone_treble = None

        # Dialogue
        self.dialogue_level = None
        self.dialogue_lift = None
        self.dts_dialogue_control = None

        self.link_audio_delay = None
        self.link_audio_quality = None
        self.link_control = None

        self.tone_control_mode_list = None
        self.surr_decoder_type_list = None
        self.link_control_list = None
        self.link_audio_delay_list = None
        self.link_audio_quality_list = None
        self.equalizer_mode_list = None

        self.range_step: dict[str, RangeStep] = {}

        self.func_list = []
        self.capabilities = []

        self.extra_bass: bool | None = None
        self.bass_extension: bool | None = None
        self.adaptive_drc: bool | None = None
        self.enhancer: bool | None = None
        self.pure_direct: bool | None = None

        self.surr_decoder_type: str | None = None


class RangeStep:
    minimum: int = 0
    maximum: int = 0
    step: int = 1

    def check(self, value):
        if value > self.maximum or value < self.minimum or value % self.step:
            raise MusicCastException("Given value %s is not in range of %s to %s with step %s",
                                     value, self.minimum, self.maximum, self.step)


class Dimmer(RangeStep):
    """Dimmer. Not all devices support dimming. A value of -1 indicates auto dimming."""

    dimmer_current: int

    def __init__(self, dimmer_min, dimmer_max, dimmer_step, dimmer_current):
        self.minimum = dimmer_min
        self.maximum = dimmer_max
        self.step = dimmer_step
        self.dimmer_current = dimmer_current
