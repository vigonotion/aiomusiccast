from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .exceptions import MusicCastException
from .features import ZoneFeature


@dataclass(slots=True)
class MusicCastAlarmDetails:
    enabled: bool | None = None
    time: str | None = None
    playback_type: str | None = None
    resume_input: str | None = None
    preset: int | None = None
    preset_type: str | None = None
    preset_info: dict[str, Any] | None = None
    beep: bool | None = None

    @property
    def input(self) -> str | None:
        return (
            f"preset:{self.preset_type}:{self.preset}"
            if self.playback_type == "preset"
            else f"resume:{self.resume_input}"
            if self.playback_type == "resume"
            else None
        )


class MusicCastData:
    """Object that holds data for a MusicCast device."""

    def __init__(self):
        """Ctor."""
        # device info
        self.device_id: str | None = None
        self.model_name: str | None = None
        self.system_version: str | None = None
        self.api_version: str | None = None

        # network status
        self.mac_addresses: dict[str, str] | None = None
        self.network_name: str | None = None

        # Network status, refreshed on every fetch
        # "wired_lan", "wireless_lan", "wireless_direct", "extend_1", ...
        self.network_connection: str | None = None
        self.ip_address: str | None = None
        self.wlan_ssid: str | None = None
        self.wlan_channel: int | None = None
        # signal strength in percent, None when not on Wi-Fi
        self.wlan_strength: int | None = None

        # Path of the device's own web page, e.g. "/AdvancedSettings.html?mc=true"
        self.web_control_url: str | None = None

        # features
        self.zones: dict[str, MusicCastZoneData] = {}
        self.input_names: dict[str, str] = {}
        self.sound_program_names: dict[str, str] = {}

        # NetUSB data
        self.netusb_input: str | None = None
        self.netusb_playback: str | None = None
        self.netusb_repeat: str | None = None
        self.netusb_shuffle: str | None = None
        self.netusb_artist: str | None = None
        self.netusb_album: str | None = None
        self.netusb_track: str | None = None
        self.netusb_albumart_url: str | None = None
        self.netusb_play_time: int | None = None
        self.netusb_play_time_updated: datetime | None = None
        self.netusb_total_time: int | None = None

        self.netusb_preset_list: dict[Any, Any] = {}

        # Tuner
        self.band: str | None = None
        self.am_freq: int = 1
        self.fm_freq: int = 1
        self.rds_text_a: str = ""
        self.rds_text_b: str = ""

        self.dab_service_label: str = ""
        self.dab_dls: str = ""

        # Preset number of the current FM / DAB station, 0 if none
        self.fm_preset: int | None = None
        self.dab_preset: int | None = None
        self.rds_program_service: str = ""
        self.rds_program_type: str = ""
        self.dab_ensemble_label: str = ""
        self.dab_channel_label: str = ""
        self.dab_program_type: str = ""
        # kbps
        self.dab_bit_rate: int | None = None
        # signal quality, 0-100
        self.dab_quality: int | None = None
        self.dab_plus: bool | None = None

        # Group
        self.last_group_role: str | None = None
        self.last_group_id: str | None = None
        self.group_id: str | None = None
        self.group_name: str | None = None
        self.group_role: str | None = None
        self.group_server_zone: str | None = None
        self.group_client_list: list[str] = []
        self.group_update_lock = asyncio.locks.Lock()

        # Dimmer
        self.dimmer: Dimmer | None = None

        # Alarm
        self.alarm_on: bool | None = None
        self.alarm_volume: int | None = None
        self.alarm_volume_range: tuple[int, int] = (0, 0)
        self.alarm_volume_step: int = 1
        self.alarm_fade_range: tuple[int, int] = (0, 0)
        self.alarm_fade_step: int = 1
        self.alarm_resume_input_list: list[str] = []
        self.alarm_preset_list: list[str] = []
        self.alarm_mode: str | None = None
        self.alarm_details: dict[str, MusicCastAlarmDetails] = {}

        # Speaker A/B
        self.speaker_a: bool | None = None
        self.speaker_b: bool | None = None

        # Speaker Pattern
        self.speaker_pattern: int | None = None
        self.speaker_pattern_list: list[int] = []

        self.party_enable: bool | None = None

        self.capabilities: list[str] = []

    @property
    def fm_freq_str(self) -> str:
        """Return a formatted string with fm frequency."""
        return f"FM {self.fm_freq / 1000:.2f} MHz"

    @property
    def am_freq_str(self) -> str:
        """Return a formatted string with am frequency."""
        return f"AM {self.am_freq:.2f} KHz"


class MusicCastZoneData:
    """Object that holds data for a MusicCast device zone."""

    features: ZoneFeature = ZoneFeature.NONE

    def __init__(self):
        """Ctor."""
        self.power: bool | None = None
        self.name: str | None = None
        self.min_volume: int = 0
        self.max_volume: int = 100
        self.current_volume: int = 0
        self.mute: bool = False
        self.input_list: list[str] = []
        self.input: str | None = None
        self.sound_program_list: list[str] = []
        self.sound_program: str | None = None
        self.sleep_time: int | None = None
        self.subwoofer_volume: int | None = None

        # Equalizer
        self.equalizer_mode: str | None = None
        self.equalizer_low: int | None = None
        self.equalizer_mid: int | None = None
        self.equalizer_high: int | None = None

        # Tone Control
        self.tone_mode: str | None = None
        self.tone_bass: int | None = None
        self.tone_treble: int | None = None

        # Dialogue
        self.dialogue_level: int | None = None
        self.dialogue_lift: int | None = None
        self.dts_dialogue_control: int | None = None

        self.link_audio_delay: str | None = None
        self.link_audio_quality: str | None = None
        self.link_control: str | None = None

        self.tone_control_mode_list: list[str] | None = None
        self.surr_decoder_type_list: list[str] | None = None
        self.link_control_list: list[str] | None = None
        self.link_audio_delay_list: list[str] | None = None
        self.link_audio_quality_list: list[str] | None = None
        self.equalizer_mode_list: list[str] | None = None

        self.range_step: dict[str, RangeStep] = {}

        self.func_list: list[str] = []
        self.capabilities: list[str] = []

        self.extra_bass: bool | None = None
        self.bass_extension: bool | None = None
        self.adaptive_drc: bool | None = None
        self.enhancer: bool | None = None
        self.pure_direct: bool | None = None
        self.clear_voice: bool | None = None
        self.surround_3d: bool | None = None
        self.surround_ai: bool | None = None

        self.surr_decoder_type: str | None = None

        # Only for zones with "signal_info" in their func_list
        self.signal_info: MusicCastSignalInfo | None = None


@dataclass(slots=True)
class MusicCastSignalInfo:
    """The audio signal a zone plays, from getSignalInfo."""

    # e.g. "PCM", "MP3", "Dolby Digital"; "---" without a signal, None in standby
    format: str | None = None
    # e.g. "44.1 kHz", as reported
    sample_rate: str | None = None
    # e.g. "16 bit", as reported (not every device reports it)
    bit_depth: str | None = None
    # bits per second, 0 when unknown (not every device reports it)
    bitrate: int | None = None
    # error code of the signal; 0 for none
    error: int | None = None


@dataclass(slots=True)
class RangeStep:
    minimum: int = 0
    maximum: int = 0
    step: int = 1

    def check(self, value: int) -> None:
        if value > self.maximum or value < self.minimum or value % self.step:
            raise MusicCastException(
                "Given value %s is not in range of %s to %s with step %s", value, self.minimum, self.maximum, self.step
            )


class Dimmer(RangeStep):
    """Dimmer.

    Not all devices support dimming. A value of -1 indicates auto
    dimming.
    """

    dimmer_current: int

    def __init__(self, dimmer_min: int, dimmer_max: int, dimmer_step: int, dimmer_current: int) -> None:
        super().__init__(dimmer_min, dimmer_max, dimmer_step)
        self.dimmer_current = dimmer_current
