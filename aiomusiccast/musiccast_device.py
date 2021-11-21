from __future__ import annotations

import mimetypes
from aiomusiccast.const import DEVICE_FUNC_LIST_TO_FEATURE_MAPPING, DeviceFeature, ZONE_FUNC_LIST_TO_FEATURE_MAPPING, \
    ZoneFeature, MIME_TYPE_UPNP_CLASS, ALARM_WEEK_DAYS, ALARM_ONEDAY, ALARM_WEEKLY, MC_LINK, MC_LINK_SOURCES, NULL_GROUP
from aiomusiccast.exceptions import MusicCastException, MusicCastGroupException, MusicCastUnsupportedException
import asyncio
import logging
import math
from datetime import datetime, time
from typing import Dict, List, Callable
from xml.sax.saxutils import escape

from .capability_registry import build_device_capabilities, build_zone_capabilities
from .features import Feature
from .musiccast_data import MusicCastAlarmDetails, RangeStep, Dimmer, MusicCastData, MusicCastZoneData
from .pyamaha import AsyncDevice, Clock, Dist, NetUSB, System, Tuner, Zone

_LOGGER = logging.getLogger(__name__)


def _check_feature(feature: Feature):
    """Decorator to check, if a feature is supported.

    Should be used for all methods of MusicCastDevice, which rely on features.
    A decorated function relying on a Zone feature has to have the zone_id as first parameter.
    """
    def aux(func: Callable):
        if isinstance(feature, ZoneFeature):
            def inner(self: MusicCastDevice, zone_id, *xs, **kws):
                if zone_id not in self.data.zones.keys():
                    raise MusicCastException("Zone %s does not exist.", zone_id)
                if not feature & self.data.zones[zone_id].features:
                    raise MusicCastUnsupportedException("Zone %s doesn't support %s.", zone_id, feature.name)

                return func(self, zone_id, *xs, **kws)
        elif isinstance(feature, DeviceFeature):
            def inner(self: MusicCastDevice, *xs, **kws):
                if not feature & self.features:
                    raise MusicCastUnsupportedException("Device doesn't support %s.", feature.name)

                return func(self, *xs, **kws)
        else:
            raise MusicCastException("Unknown feature type ")

        return inner

    return aux


class MusicCastDevice:
    """Dummy MusicCastDevice (device for HA) for Hello World example."""

    device: AsyncDevice
    features: DeviceFeature = DeviceFeature.NONE

    def __init__(self, ip, client, upnp_description=None):
        """Init dummy MusicCastDevice."""
        self.ip = ip
        self.client = client

        try:
            self.event_loop = asyncio.get_running_loop()
        except RuntimeError:
            self.event_loop = asyncio.new_event_loop()

        self.device = AsyncDevice(client, ip, self.event_loop, self.handle, upnp_description)
        self._callbacks = set()
        self._group_update_callbacks = set()
        self.group_reduce_by_source = False
        self.data = MusicCastData()

        # the following data must not be updated frequently
        self._zone_ids: List = []
        self._network_status = None
        self._device_info = None
        self._features: Dict = {}
        self._netusb_play_info = None
        self._tuner_play_info = None
        self._clock_info = None
        self._func_status = None
        self._distribution_info: Dict = {}
        self._name_text = None

    @classmethod
    async def check_yamaha_ssdp(cls, location, client):
        res = await client.get(location)
        text = await res.text()
        return text.find('<yamaha:X_yxcControlURL>/YamahaExtendedControl/v1/</yamaha:X_yxcControlURL>') != -1

    @classmethod
    async def get_device_info(cls, ip, client):
        try:
            event_loop = asyncio.get_running_loop()
        except RuntimeError:
            event_loop = asyncio.new_event_loop()
        device = AsyncDevice(client, ip, event_loop)
        return await device.request_json(System.get_device_info())

    # -----UDP messaging-----

    async def handle(self, message):
        """Handle udp events."""
        if message is None:
            await self.fetch()

        for parameter in message:
            if parameter in ["main", "zone2", "zone3", "zone4"]:
                new_zone_data = message[parameter]

                zone = self.data.zones.get(parameter)

                if zone:
                    zone.current_volume = new_zone_data.get(
                        "volume", zone.current_volume
                    )
                    zone.power = new_zone_data.get(
                        "power", zone.power
                    )
                    zone.mute = new_zone_data.get(
                        "mute", zone.mute
                    )
                    await self._update_input(parameter, new_zone_data.get("input", zone.input))
                else:
                    _LOGGER.warning("Zone %s does not exist. Available zones are: %s", parameter,
                                    self.data.zones.keys())

                if new_zone_data.get("play_info_updated") or new_zone_data.get(
                        "status_updated"
                ):
                    await self._fetch_zone(parameter)

        if "netusb" in message.keys():
            if message.get("netusb").get("play_info_updated"):
                await self._fetch_netusb()

            play_time = message.get("netusb").get("play_time")
            if play_time:
                self.data.netusb_play_time = play_time
                self.data.netusb_play_time_updated = datetime.utcnow()

            if message.get("netusb").get("preset_info_updated"):
                await self._fetch_netusb_presets()

        if "tuner" in message.keys():
            if message.get("tuner").get("play_info_updated"):
                await self._fetch_tuner()

        if "dist" in message.keys():
            if message.get("dist").get("dist_info_updated"):
                await self._fetch_distribution_data()

        if "clock" in message.keys():
            if message.get("clock").get("settings_updated"):
                await self._fetch_clock_data()

        if "system" in message.keys():
            if message.get("system").get("func_status_updated"):
                await self._fetch_func_status()

        for callback in self._callbacks:
            callback()

    def register_callback(self, callback):
        """Register callback, called when MusicCastDevice changes state."""
        self._callbacks.add(callback)

    def remove_callback(self, callback):
        """Remove previously registered callback."""
        self._callbacks.discard(callback)

    async def _update_input(self, zone_id, new_input):
        """If the input of a zone changes from or to MC_LINK, a group update has to be triggered."""
        trigger_group_cb = (
                self.data.zones[zone_id].input == MC_LINK or
                new_input == MC_LINK
                           ) and not self.data.group_update_lock.locked()

        self.data.zones[zone_id].input = new_input
        if trigger_group_cb:
            if self.data.zones[zone_id].input != MC_LINK:
                self.group_reduce_by_source = True
            try:
                for cb in self._group_update_callbacks:
                    await cb()
            finally:
                self.group_reduce_by_source = False

    # -----Data Fetching-----

    async def _fetch_netusb(self):
        """Fetch NetUSB data."""
        _LOGGER.debug("Fetching netusb...")
        self._netusb_play_info = await self.device.request_json(NetUSB.get_play_info())

        self.data.netusb_input = self._netusb_play_info.get(
            "input", self.data.netusb_input
        )
        self.data.netusb_playback = self._netusb_play_info.get(
            "playback", self.data.netusb_playback
        )
        self.data.netusb_repeat = self._netusb_play_info.get(
            "repeat", self.data.netusb_repeat
        )
        self.data.netusb_shuffle = self._netusb_play_info.get(
            "shuffle", self.data.netusb_shuffle
        )
        self.data.netusb_artist = self._netusb_play_info.get(
            "artist", self.data.netusb_artist
        )
        self.data.netusb_album = self._netusb_play_info.get(
            "album", self.data.netusb_album
        )
        self.data.netusb_track = self._netusb_play_info.get(
            "track", self.data.netusb_track
        )
        self.data.netusb_albumart_url = self._netusb_play_info.get(
            "albumart_url", self.data.netusb_albumart_url
        )
        self.data.netusb_total_time = self._netusb_play_info.get("total_time", None)
        self.data.netusb_play_time = self._netusb_play_info.get("play_time", None)

        self.data.netusb_play_time_updated = datetime.utcnow()

    async def _fetch_tuner(self):
        """Fetch tuner data."""
        _LOGGER.debug("Fetching tuner...")
        self._tuner_play_info = await self.device.request_json(Tuner.get_play_info())

        self.data.band = self._tuner_play_info.get("band", self.data.band)

        self.data.fm_freq = self._tuner_play_info.get("fm", {}).get(
            "freq", self.data.fm_freq
        )
        self.data.am_freq = self._tuner_play_info.get("am", {}).get(
            "freq", self.data.am_freq
        )
        self.data.rds_text_a = (
            self._tuner_play_info.get("rds", {})
                .get("radio_text_a", self.data.rds_text_a)
                .strip()
        )
        self.data.rds_text_b = (
            self._tuner_play_info.get("rds", {})
                .get("radio_text_b", self.data.rds_text_b)
                .strip()
        )
        self.data.dab_service_label = (
            self._tuner_play_info.get("dab", {})
                .get("service_label", self.data.dab_service_label)
                .strip()
        )
        self.data.dab_dls = (
            self._tuner_play_info.get("dab", {}).get("dls", self.data.dab_dls).strip()
        )

    async def _fetch_zone(self, zone_id):
        _LOGGER.debug("Fetching zone %s...", zone_id)
        zone = await self.device.request_json(Zone.get_status(zone_id))
        zone_data: MusicCastZoneData = self.data.zones.get(zone_id, MusicCastZoneData())

        self.data.party_enable = zone.get("party_enable")

        zone_data.power = zone.get("power")
        zone_data.current_volume = zone.get("volume")
        zone_data.mute = zone.get("mute")
        zone_data.sound_program = zone.get("sound_program")
        zone_data.sleep_time = zone.get("sleep")

        zone_data.extra_bass = zone.get("extra_bass")
        zone_data.bass_extension = zone.get("bass_extension")
        zone_data.adaptive_drc = zone.get("adaptive_drc")
        zone_data.enhancer = zone.get("enhancer")
        zone_data.pure_direct = zone.get("pure_direct")

        zone_data.surr_decoder_type = zone.get("surr_decoder_type")

        zone_data.equalizer_mode = zone.get("equalizer", {}).get("mode")
        zone_data.equalizer_high = zone.get("equalizer", {}).get("high")
        zone_data.equalizer_mid = zone.get("equalizer", {}).get("mid")
        zone_data.equalizer_low = zone.get("equalizer", {}).get("low")

        zone_data.tone_mode = zone.get("tone_control", {}).get("mode")
        zone_data.tone_bass = zone.get("tone_control", {}).get("bass")
        zone_data.tone_treble = zone.get("tone_control", {}).get("treble")

        zone_data.dialogue_level = zone.get("dialogue_level")
        zone_data.dialogue_lift = zone.get("dialogue_lift")
        zone_data.dts_dialogue_control = zone.get("dts_dialogue_control")

        zone_data.link_audio_delay = zone.get("link_audio_delay")
        zone_data.link_audio_quality = zone.get("link_audio_quality")
        zone_data.link_control = zone.get("link_control")

        self.data.zones[zone_id] = zone_data
        await self._update_input(zone_id, zone.get("input"))

    async def _fetch_distribution_data(self):
        _LOGGER.debug("Fetching Distribution data...")
        self._distribution_info = (
            await self.device.request_json(Dist.get_distribution_info())
        )
        self.data.last_group_role = self.data.group_role
        self.data.last_group_id = self.data.group_id
        self.data.group_id = self._distribution_info.get("group_id", None)
        self.data.group_name = self._distribution_info.get("group_name", None)
        self.data.group_role = self._distribution_info.get("role", None)
        self.data.group_server_zone = self._distribution_info.get("server_zone", None)
        self.data.group_client_list = [
            client.get("ip_address", "")
            for client in self._distribution_info.get("client_list", [])
        ]
        if not self.data.group_update_lock.locked():
            for cb in self._group_update_callbacks:
                await cb()

    async def _fetch_clock_data(self):
        _LOGGER.debug("Fetching Clock data...")
        self._clock_info = (
            await self.device.request_json(Clock.get_clock_settings())
        )

        self.data.alarm_on = self._clock_info.get('alarm', {}).get('alarm_on', False)
        self.data.alarm_volume = self._clock_info.get('alarm', {}).get("volume", None)
        self.data.alarm_mode = self._clock_info.get('alarm', {}).get("mode", None)

        days = []
        if DeviceFeature.ALARM_WEEKLY in self.features:
            days += ALARM_WEEK_DAYS

        if DeviceFeature.ALARM_ONEDAY in self.features:
            days += [ALARM_ONEDAY]

        for day in days:
            if day not in self.data.alarm_details:
                self.data.alarm_details[day] = MusicCastAlarmDetails()

            day_info = self._clock_info.get('alarm', {}).get(day, {})
            time_str = day_info.get('time')
            if isinstance(time_str, str):
                time_str = f"{time_str[:2]}:{time_str[2:]}"

            self.data.alarm_details[day].enabled = day_info.get('enable')
            self.data.alarm_details[day].beep = day_info.get('beep')
            self.data.alarm_details[day].time = time_str
            self.data.alarm_details[day].playback_type = day_info.get('playback_type')
            self.data.alarm_details[day].resume_input = day_info.get('resume', {}).get('input')
            self.data.alarm_details[day].preset = day_info.get('preset', {}).get('num')
            self.data.alarm_details[day].preset_type = day_info.get('preset', {}).get('type')
            self.data.alarm_details[day].preset_info = (
                day_info.get('preset', {}).get('netusb_info', {})
                if self.data.alarm_details[day].preset_type == "netusb"
                else day_info.get('preset', {}).get('tuner_info', {})
            )

    async def _fetch_func_status(self):
        _LOGGER.debug("Fetching func status...")

        self._func_status = (
            await self.device.request_json(System.get_func_status())
        )

        if DeviceFeature.SPEAKER_A in self.features:
            self.data.speaker_a = self._func_status.get("speaker_a")

        if DeviceFeature.SPEAKER_B in self.features:
            self.data.speaker_b = self._func_status.get("speaker_b")

        if DeviceFeature.DIMMER in self.features and "dimmer" in self._func_status and self.data.dimmer:
            self.data.dimmer.dimmer_current = self._func_status.get("dimmer")

    async def fetch(self):
        """Fetch data from musiccast device."""
        if not self._network_status:
            self._network_status = await self.device.request_json(System.get_network_status())

            self.data.network_name = self._network_status.get("network_name")
            self.data.mac_addresses = self._network_status.get("mac_address")

        if not self._device_info:
            self._device_info = await self.device.request_json(System.get_device_info())

            self.data.device_id = self._device_info.get("device_id")
            self.data.model_name = self._device_info.get("model_name")
            self.data.system_version = self._device_info.get("system_version")
            self.data.api_version = self._device_info.get("api_version")

        self._name_text = await self.device.request_json(System.get_name_text(None))
        zone_names = {
            zone.get("id"): zone.get("text")
            for zone in self._name_text.get("zone_list")
        }

        if not self._features:
            self._features = await self.device.request_json(System.get_features())

            # feature flags from func list
            for feature in self._features.get("system", {}).get("func_list", []):
                feature_bit = DEVICE_FUNC_LIST_TO_FEATURE_MAPPING.get(feature)

                if feature_bit:
                    self.features |= feature_bit
                else:
                    _LOGGER.info(
                        "The model %s supports the feature %s which is not known to aiomusiccast. Please consider "
                        "opening an issue on GitHub to tell us about this feature so we can implement it.",
                        self.data.model_name, feature)

            self._zone_ids = [zone.get("id") for zone in self._features.get("zone", [])]

            for zone in self._features.get("zone", []):
                zone_id = zone.get("id")

                zone_data: MusicCastZoneData = self.data.zones.get(
                    zone_id, MusicCastZoneData()
                )

                zone_data.sound_program_list = zone.get("sound_program_list", [])

                zone_data.tone_control_mode_list = zone.get("tone_control_mode_list", ["manual"])
                zone_data.surr_decoder_type_list = zone.get("surr_decoder_type_list", None)
                zone_data.link_control_list = zone.get("link_control_list", None)
                zone_data.link_audio_delay_list = zone.get("link_audio_delay_list", None)
                zone_data.link_audio_quality_list = zone.get("link_audio_quality_list", None)
                zone_data.equalizer_mode_list = zone.get("equalizer_mode_list", ["manual"])

                for range_step in zone.get("range_step", []):
                    current = RangeStep()
                    current.minimum = range_step.get("min")
                    current.maximum = range_step.get("max")
                    current.step = range_step.get("step")
                    zone_data.range_step[range_step.get("id")] = current

                zone_data.input_list = zone.get("input_list", [])
                zone_data.func_list = zone.get('func_list')

                zone_data.name = zone_names.get(zone_id)

                for feature in zone_data.func_list:
                    feature_bit = ZONE_FUNC_LIST_TO_FEATURE_MAPPING.get(feature)

                    if feature_bit:
                        zone_data.features |= feature_bit
                    else:
                        _LOGGER.info(
                            "Zone %s of model %s supports the feature %s which is not known to aiomusiccast. Please "
                            "consider opening an issue on GitHub to tell us about this feature so we can implement it.",
                            zone_id, self.data.model_name, feature)

                if ZoneFeature.VOLUME in zone_data.features:
                    range_volume = next(
                        item for item in zone.get("range_step") if item["id"] == "volume"
                    )

                    zone_data.min_volume = range_volume.get("min")
                    zone_data.max_volume = range_volume.get("max")

                self.data.zones[zone_id] = zone_data

            if "clock" in self._features.keys():
                if "alarm" in self._features.get('clock', {}).get('func_list', []):
                    if ALARM_ONEDAY in self._features.get('clock', {}).get('alarm_mode_list', []):
                        self.features |= DeviceFeature.ALARM_ONEDAY
                    if ALARM_WEEKLY in self._features.get('clock', {}).get('alarm_mode_list', []):
                        self.features |= DeviceFeature.ALARM_WEEKLY

                if "date_and_time" in self._features.get('clock', {}).get(
                        'func_list', []
                ):
                    self.features |= DeviceFeature.CLOCK

                for value_range in self._features.get('clock', {}).get(
                        'range_step', []
                ):
                    if value_range.get('id') == "alarm_volume":
                        self.data.alarm_volume_range = (
                            value_range.get('min', 0),
                            value_range.get('max', 0),
                        )
                        self.data.alarm_volume_step = value_range.get('step', 1)

                    if value_range.get('id') == "alarm_fade":
                        self.data.alarm_fade_range = (
                            value_range.get('min', 0),
                            value_range.get('max', 0),
                        )
                        self.data.alarm_fade_step = value_range.get('step', 1)

                self.data.alarm_preset_list = self._features.get('clock', {}).get(
                    'alarm_preset_list', []
                )
                self.data.alarm_resume_input_list = self._features.get('clock', {}).get(
                    'alarm_input_list', []
                )

        self.data.input_names = {
            source.get("id"): source.get("text")
            for source in self._name_text.get("input_list")
        }

        if "netusb" in self._features.keys() and self._features.get("netusb").get("func_list"):
            await self._fetch_netusb()
            await self._fetch_netusb_presets()

        if "tuner" in self._features.keys():
            await self._fetch_tuner()
        await self._fetch_distribution_data()
        if DeviceFeature.ALARM_ONEDAY in self.features or DeviceFeature.ALARM_WEEKLY in self.features:
            await self._fetch_clock_data()

        for zone in self._zone_ids:
            await self._fetch_zone(zone)

        ranges = self._features.get("system").get("range_step")
        
        if DeviceFeature.DIMMER in self.features and ranges:
            dimmer_range = next(filter(lambda x: x.get("id") == "dimmer", ranges))
            self.data.dimmer = Dimmer(
                dimmer_range.get("min"),
                dimmer_range.get("max"),
                dimmer_range.get("step"),
                0
            )

        await self._fetch_func_status()

    def build_capabilities(self):
        """This function generates the capabilities of a device and its zones."""
        self.data.capabilities = build_device_capabilities(self)

        for zone_id in self.data.zones.keys():
            self.data.zones[zone_id].capabilities = build_zone_capabilities(self, zone_id)

    # -----Commands-----
    async def turn_on(self, zone_id):
        """Turn the media player on."""
        await self.device.request(
            Zone.set_power(zone_id, "on")
        )

    async def turn_off(self, zone_id):
        """Turn the media player off."""
        await self.device.request(
            Zone.set_power(zone_id, "standby")
        )

    async def mute_volume(self, zone_id, mute):
        """Mute the volume."""
        await self.device.request(
            Zone.set_mute(zone_id, mute)
        )

    async def set_volume_level(self, zone_id, volume):
        """Set the volume level, range 0..1."""
        vol = self.data.zones[zone_id].min_volume + (
                self.data.zones[zone_id].max_volume - self.data.zones[zone_id].min_volume
        ) * volume

        await self.device.request(
            Zone.set_volume(zone_id, round(vol), 1)
        )

    async def volume_up(self, zone_id, step=None):
        """Turn up the volume by step or by the default step of the zone."""

        await self.device.request(
            Zone.set_volume(zone_id, "up", step)
        )

    async def volume_down(self, zone_id, step=None):
        """Turn down the volume by step or by the default step of the zone."""

        await self.device.request(
            Zone.set_volume(zone_id, "down", step)
        )

    @_check_feature(ZoneFeature.TONE_CONTROL)
    async def set_tone_control(self, zone_id, mode=None, bass=None, treble=None):
        """Set treble, bass, mode using tone_control."""
        await self.device.request(
            Zone.set_tone_control(
                zone_id,
                mode,
                bass,
                treble
            )
        )

    @_check_feature(ZoneFeature.EQUALIZER)
    async def set_equalizer(self, zone_id, mode=None, low=None, mid=None, high=None):
        """Set low, mid, high, mode using equalizer."""
        await self.device.request(
            Zone.set_equalizer(
                zone_id,
                mode,
                low,
                mid,
                high
            )
        )

    @_check_feature(ZoneFeature.DIALOGUE_LEVEL)
    async def set_dialogue_level(self, zone_id, level):
        """Set the level by which the dialogues should be increased/lowered"""
        await self.device.request(
            Zone.set_dialogue_level(
                zone_id,
                level
            )
        )

    @_check_feature(ZoneFeature.DIALOGUE_LIFT)
    async def set_dialogue_lift(self, zone_id, level):
        """Set the vertical position of the dialogues."""
        await self.device.request(
            Zone.set_dialogue_lift(
                zone_id,
                level
            )
        )

    @_check_feature(ZoneFeature.DTS_DIALOGUE_CONTROL)
    async def set_dts_dialogue_control(self, zone_id, value):
        """Set the level by which the dialogues should be increased/lowered - for DTS sound programs"""
        await self.device.request(
            Zone.set_dts_dialogue_control(
                zone_id,
                value
            )
        )

    @_check_feature(ZoneFeature.EXTRA_BASS)
    async def set_extra_bass(self, zone_id, value):
        """Set extra bass for a higher bass level."""
        await self.device.request(
            Zone.set_extra_bass(
                zone_id,
                value
            )
        )

    @_check_feature(ZoneFeature.BASS_EXTENSION)
    async def set_bass_extension(self, zone_id, value):
        """Set bass extension for a higher bass level."""
        await self.device.request(
            Zone.set_bass_extension(
                zone_id,
                value
            )
        )

    @_check_feature(ZoneFeature.ENHANCER)
    async def set_enhancer(self, zone_id, value):
        """Set the enhancer to enhance the audio stream on the device."""
        await self.device.request(
            Zone.set_enhancer(
                zone_id,
                value
            )
        )

    @_check_feature(DeviceFeature.PARTY_MODE)
    async def set_party_mode(self, value):
        """Set the party mode."""
        await self.device.request(
            System.set_partymode(
                value
            )
        )

    @_check_feature(ZoneFeature.ADAPTIVE_DRC)
    async def set_adaptive_drc(self, zone_id, value):
        """Set the dynamic range control."""
        await self.device.request(
            Zone.set_adaptive_drc(
                zone_id,
                value
            )
        )

    @_check_feature(ZoneFeature.PURE_DIRECT)
    async def set_pure_direct(self, zone_id, value):
        """Set pure direct mode to pass through the signal without any adjustments."""
        await self.device.request(
            Zone.set_pure_direct(
                zone_id,
                value
            )
        )

    @_check_feature(ZoneFeature.LINK_AUDIO_DELAY)
    async def set_link_audio_delay(self, zone_id, option):
        """Set the audio delay to prefer lip sync or sync of multi room audio."""
        await self.device.request(
            Zone.set_link_audio_delay(
                zone_id,
                option
            )
        )

    @_check_feature(ZoneFeature.LINK_AUDIO_QUALITY)
    async def set_link_audio_quality(self, zone_id, option):
        """Set the audio quality for musiccast linked speakers."""
        await self.device.request(
            Zone.set_link_audio_quality(
                zone_id,
                option
            )
        )

    @_check_feature(ZoneFeature.LINK_CONTROL)
    async def set_link_control(self, zone_id, option):
        """Set link control."""
        await self.device.request(
            Zone.set_link_control(
                zone_id,
                option
            )
        )

    @_check_feature(ZoneFeature.SURR_DECODER_TYPE)
    async def set_surround_decoder(self, zone_id, option):
        """Set surround decoder for sound mode 'surr_decoder'."""
        await self.device.request(
            Zone.set_surr_decoder_type(
                zone_id,
                option
            )
        )

    @_check_feature(DeviceFeature.DIMMER)
    async def set_dimmer(self, dimmer: int):
        """Set the dimmer on the device."""
        self.data.dimmer.check(dimmer)

        await self.device.request(
            System.set_dimmer(dimmer)
        )

    async def netusb_play(self):
        await self.device.request(NetUSB.set_playback("play"))

    async def netusb_pause(self):
        await self.device.request(NetUSB.set_playback("pause"))

    async def netusb_stop(self):
        await self.device.request(NetUSB.set_playback("stop"))

    async def netusb_shuffle(self, shuffle: bool):
        if self.data.api_version < 1.19:
            if (self.data.netusb_shuffle == "on") != shuffle:
                await self.device.request(NetUSB.toggle_shuffle())
        else:
            await self.device.request(NetUSB.set_shuffle("on" if shuffle else "off"))

    @_check_feature(DeviceFeature.SPEAKER_A)
    async def set_speaker_a(self, speaker_a: bool):
        """Set speaker a."""
        await self.device.request(
            System.set_speaker_a(speaker_a)
        )

    @_check_feature(DeviceFeature.SPEAKER_B)
    async def set_speaker_b(self, speaker_b: bool):
        """Set speaker b."""
        await self.device.request(
            System.set_speaker_b(speaker_b)
        )

    async def select_sound_mode(self, zone_id, sound_mode):
        """Select sound mode."""
        await self.device.request(
            Zone.set_sound_program(zone_id, sound_mode)
        )

    async def netusb_previous_track(self):
        await self.device.request(
            NetUSB.set_playback("previous")
        )

    async def netusb_next_track(self):
        await self.device.request(
            NetUSB.set_playback("next")
        )

    async def tuner_previous_station(self):
        if self.data.band in ("fm", "am"):
            await self.device.request(
                Tuner.set_freq(self.data.band, "auto_down", 0)
            )
        elif self.data.band == "dab":
            await self.device.request(
                Tuner.set_dab_service("previous")
            )

    async def tuner_next_station(self):
        if self.data.band in ("fm", "am"):
            await self.device.request(
                Tuner.set_freq(self.data.band, "auto_up", 0)
            )
        elif self.data.band == "dab":
            await self.device.request(
                Tuner.set_dab_service("next")
            )

    async def netusb_repeat(self, mode):
        """Sets the repeat mode.
        @param mode: Value : "off" / "one" / "all"
        """
        if self.data.api_version < 1.19:
            if self.data.netusb_repeat != mode and self.data.netusb_repeat != "one":
                await self.device.request(NetUSB.toggle_repeat())
        else:
            await self.device.request(NetUSB.set_repeat(mode))

    async def select_source(self, zone_id, source, mode=""):
        await self.device.request(
            Zone.set_input(zone_id, source, mode)
        )

    async def recall_netusb_preset(self, zone_id, preset):
        """Play the selected preset."""
        await self.device.get(NetUSB.recall_preset(zone_id, preset))

    async def store_netusb_preset(self, preset):
        """Play the selected preset."""
        await self.device.get(NetUSB.store_preset(preset))

    async def set_sleep_timer(self, zone_id, sleep_time=0):
        """Set sleep time"""
        sleep_time = math.ceil(sleep_time / 30) * 30
        await self.device.get(Zone.set_sleep(zone_id, sleep_time))

    async def configure_alarm(
            self,
            alarm_on: bool = None,
            volume: float = None,
            alarm_time=None,
            source: str = None,
            mode: str = None,
            day: str = None,
            enable_day: bool = None,
            beep: bool = None
    ):
        """
        Configure an alarm.
        @param alarm_on: Define whether the alarm should be turned on (bool)
        @param volume: Alarm volume 0..1 (float)
        @param alarm_time: Alarm time in str in hh:mm form or as time object (valid only with mode and day)
        @param source: Source for the alarm in PLAYBACKTYPE:SOURCE[:ID] form e.g. preset:netusb:2
        (valid only with mode and day)
        @param mode: 'oneday' or 'weekly' must be set together with day
        @param day: Must be set with mode
        @param enable_day: Define whether to enable the alarm for the defined day (valid only with mode and day)
        @param beep: Define to enable the beep mode (valid only with mode and day)
        """
        resume_input = None
        preset_type = None
        preset_num = None
        playback_type = None

        if day is None or mode is None:
            assert source is None, "if no day or mode is defined, the source cannot be set"
            assert alarm_time is None, "if no day or mode is defined, the alarm_time cannot be set"
            assert enable_day is None, "if no day or mode is defined, the enable_day cannot be set"
            assert beep is None, "if no day or mode is defined, the beep cannot be set"
            assert day is None, "day must not be defined without mode"
            assert mode is None, "mode must not be defined without day"
        else:
            # For some reason beep can only be set, if the alarm time or source are send together with it.
            # To ensure that this is working as expected in all cases, the alarm time will always be send with details.
            alarm_time = alarm_time if alarm_time is not None else self.data.alarm_details[day].time

        if source is not None:
            source_parts = source.split(':')
            if len(source_parts) > 0 and source_parts[0] != "":
                playback_type = source_parts[0]
                if playback_type == "resume":
                    resume_input = source_parts[1]
                elif playback_type == "preset":
                    preset_type = source_parts[1]
                    preset_num = int(source_parts[2])

        if volume is not None:
            volume = self.data.alarm_volume_range[0] + (
                    self.data.alarm_volume_range[1] - self.data.alarm_volume_range[0]
            ) * volume
            volume = self.data.alarm_volume_step * round(volume/self.data.alarm_volume_step)

        if isinstance(alarm_time, str) and alarm_time.find(":") != -1:
            time_parts = alarm_time.split(':')
            alarm_time = time_parts[0] + time_parts[1]

        if isinstance(alarm_time, time):
            alarm_time = alarm_time.strftime("%H%M")

        await self.device.post(
            *Clock.set_alarm_settings(
                alarm_on=alarm_on,
                volume=volume,
                mode=mode,
                day=day,
                playback_type=playback_type,
                alarm_time=alarm_time,
                preset_num=preset_num,
                preset_type=preset_type,
                enable=enable_day,
                resume_input=resume_input,
                beep=beep
            )
        )

    # -----NetUSB Browsing-----
    async def get_list_info(self, source, start_index):
        return (
            await self.device.request_json(
                NetUSB.get_list_info(source, start_index, 8, "en", "main")
            )
        )

    async def select_list_item(self, item, zone_id):
        await self.device.request(
            NetUSB.set_list_control(
                "main", "select", item, zone_id
            )
        )

    async def return_in_list(self, zone_id):
        await self.device.request(
            NetUSB.set_list_control("main", "return", "", zone_id)
        )

    async def play_list_media(self, item, zone_id):
        await self.device.request(
            NetUSB.set_list_control("main", "play", item, zone_id)
        )

    async def play_url_media(self, zone_id, media_url, title, mime_type=None):
        await self.select_source(zone_id, "server", "autoplay_disabled")

        await self.device.dlna_avt_request("Stop", {"InstanceID": 0})

        if not mime_type:
            mime_type, _ = mimetypes.guess_type(media_url)

        if not mime_type:
            mime_type = "application/octet-stream"

        obj_class = None
        for mime, upnp in MIME_TYPE_UPNP_CLASS.items():
            if mime_type.startswith(mime):
                obj_class = upnp
                break

        if not obj_class:
            obj_class = "object.item"

        meta = (
            '<DIDL-Lite xmlns="urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/" '
            'xmlns:upnp="urn:schemas-upnp-org:metadata-1-0/upnp/" '
            'xmlns:sec="http://www.sec.co.kr/">'
            '<item id="0" parentID="-1" restricted="false">'
            f'<dc:title>{title}</dc:title><upnp:class>{obj_class}</upnp:class>'
            f'<res protocolInfo="http-get:*:{mime_type}:*">{media_url}</res>'
            '</item>'
            '</DIDL-Lite>'
        )

        await self.device.dlna_avt_request(
            "SetAVTransportURI",
            {
                "InstanceID": 0,
                "CurrentURI": media_url,
                "CurrentURIMetaData": escape(meta),
            }
        )

        await self.device.dlna_avt_request(
            "Play",
            {
                "InstanceID": 0,
                "Speed": 1,
            }
        )

    # -----Properties-----

    @property
    def media_image_url(self):
        """Return the image url of current playing media."""
        return (
            f"http://{self.device.ip}{self.data.netusb_albumart_url}"
            if self.data.netusb_albumart_url else ""
        )

    @property
    def tuner_media_title(self):
        if self.data.band == "dab":
            return self.data.dab_dls
        else:
            if (
                    self.data.rds_text_a == ""
                    and self.data.rds_text_b != ""
            ):
                return self.data.rds_text_b
            elif (
                    self.data.rds_text_a != ""
                    and self.data.rds_text_b == ""
            ):
                return self.data.rds_text_a
            elif (
                    self.data.rds_text_a != ""
                    and self.data.rds_text_b != ""
            ):
                return f"{self.data.rds_text_a} / {self.data.rds_text_b}"

    @property
    def tuner_media_artist(self):
        if self.data.band == "dab":
            return self.data.dab_service_label
        elif self.data.band == "fm":
            return self.data.fm_freq_str
        elif self.data.band == "am":
            return self.data.am_freq_str

        return None

    @property
    def alarm_input_list(self):
        inputs = {
            "resume:" + inp: "Resume " + self.data.input_names.get(inp, inp)
            for inp in self.data.alarm_resume_input_list
        }

        if "netusb" in self.data.alarm_preset_list:
            inputs = {
                **inputs,
                **{
                    "preset:netusb:" + str(index): self.data.input_names.get(entry[0], entry[0]) + " - " + entry[1]
                    for index, entry in self.data.netusb_preset_list.items()
                }
            }

        return inputs

    # -----Group Management------

    def register_group_update_callback(self, callback):
        """Register async methods called after changes of the distribution data here."""
        self._group_update_callbacks.add(callback)

    def remove_group_update_callback(self, callback):
        """Remove async methods called after changes of the distribution data here."""
        self._group_update_callbacks.discard(callback)

    # Simple check functions for better code readability

    def _check_clients_removed(self, clients):
        return all([client not in self.data.group_client_list for client in clients])

    def _check_clients_added(self, clients):
        return all([client in self.data.group_client_list for client in clients])

    def _check_group_id(self, group_id):
        return self.data.group_id == group_id

    def _check_source(self, source, zone):
        return self.data.zones[zone].input == source

    def _check_group_role(self, role):
        return self.data.group_role == role

    def _check_group_server_zone(self, zone):
        return self.data.group_server_zone == zone

    def _check_power_status(self, zone_id, status):
        return self.data.zones[zone_id].power == status

    # Group update checking functions

    async def wait_for_data_update(self, checks):
        while True:
            if all([check() for check in checks]):
                return
            await asyncio.sleep(0.1)

    async def check_group_data(self, checks):
        try:
            await asyncio.wait_for(self.wait_for_data_update(checks), 1)
        except asyncio.exceptions.TimeoutError:
            _LOGGER.warning(
                "Coordinator of %s did not receive the expected group data update via UDP. "
                "Fetching manually.",
                self.ip,
            )
            await self._fetch_distribution_data()
        return all([check() for check in checks])

    # Group server functions

    async def mc_server_group_extend(self, zone, client_ips, group_id, distribution_num, retry=True):
        """Extend the given group by the given clients.

        If the group does not exist, it will be created.
        """
        async with self.data.group_update_lock:
            await self.device.post(
                *Dist.set_server_info(group_id, zone, "add", client_ips)
            )
            await self.device.get(Dist.start_distribution(distribution_num))
            if await self.check_group_data(
                    [
                        lambda: self._check_clients_added(client_ips),
                        lambda: self._check_group_id(group_id),
                        lambda: self._check_group_role("server"),
                        lambda: self._check_group_server_zone(zone),
                    ]
            ):
                return

        if retry:
            await self.mc_server_group_extend(zone, client_ips, group_id, distribution_num, False)
        else:
            raise MusicCastGroupException(
                self.ip + ": Failed to extent group by clients " + str(client_ips)
            )

    async def mc_server_group_reduce(self, zone, client_ips_for_removal, distribution_num, retry=True):
        """Reduce the current group by the given clients."""
        async with self.data.group_update_lock:
            await self.device.post(
                *Dist.set_server_info(
                    self.data.group_id,
                    zone,
                    "remove",
                    client_ips_for_removal,
                )
            )
            if await self.check_group_data(
                    [lambda: self._check_clients_removed(client_ips_for_removal)]
            ):
                if self.data.group_client_list:
                    await self.device.get(Dist.start_distribution(distribution_num))
                return

        if retry:
            await self.mc_server_group_reduce(zone, client_ips_for_removal, distribution_num, False)
        else:
            raise MusicCastGroupException(
                self.ip
                + ": Failed to reduce group by clients "
                + str(client_ips_for_removal)
            )

    async def mc_server_group_close(self, retry=True):
        """Close the current group."""
        async with self.data.group_update_lock:
            await self.device.get(Dist.stop_distribution())
            await self.device.post(*Dist.set_server_info(""))
            if await self.check_group_data([lambda: self._check_group_id(NULL_GROUP)]):
                return

        if retry:
            await self.mc_server_group_close(False)
        else:
            raise MusicCastGroupException(self.ip + ": Failed to close group.")

    # Group client functions

    async def mc_client_join(self, server_ip, group_id, zone, retry=True):
        """Join the given group as a client."""
        async with self.data.group_update_lock:
            await self.device.post(*Dist.set_client_info(group_id, zone, server_ip))
            await self.device.request(Zone.set_input(zone, MC_LINK, ""))
            if await self.check_group_data(
                    [
                        lambda: self._check_group_id(group_id),
                        lambda: self._check_group_role("client"),
                        lambda: self._check_source(MC_LINK, zone),
                    ]
            ):
                return

        if retry:
            await self.mc_client_join(server_ip, group_id, zone, False)
        else:
            raise MusicCastGroupException(self.ip + ": Failed to join the group.")

    async def mc_client_unjoin(self, retry=True):
        """Unjoin the current group."""
        async with self.data.group_update_lock:
            await self.device.post(*Dist.set_client_info(""))
            if await self.check_group_data([lambda: self._check_group_id(NULL_GROUP)]):
                return

        if retry:
            await self.mc_client_unjoin(False)
        else:
            raise MusicCastGroupException(self.ip + ": Failed to leave group")

    async def zone_unjoin(self, zone_id, retry=True):
        """Stop the musiccast playback for one of the zones, but keep the device in the group."""
        async with self.data.group_update_lock:
            save_inputs = self.get_save_inputs(zone_id)
            if len(save_inputs):
                await self.select_source(zone_id, save_inputs[0])
            else:
                _LOGGER.warning(self.ip + ": did not find a save input for zone " + zone_id)
            # Then turn off the zone
            await self.turn_off(zone_id)
            if await self.check_group_data([lambda: self._check_power_status(zone_id, "standby")]):
                return

        if retry:
            await self.zone_unjoin(zone_id, False)
        else:
            raise MusicCastGroupException(self.ip + ": Failed to leave group with zone " + zone_id)

    async def zone_join(self, zone_id, retry=True):
        """Join a musiccast group with a zone when another zone of the same device is already client in that group."""
        async with self.data.group_update_lock:
            await self.select_source(zone_id, MC_LINK)

            if await self.check_group_data([lambda: self._check_source(MC_LINK, zone_id)]):
                return

        if retry:
            await self.zone_join(zone_id, False)
        else:
            raise MusicCastGroupException(self.ip + ": Failed to join group with zone " + zone_id)

    # Misc

    def get_save_inputs(self, zone_id):
        """Return a save save source for the given zone_id.

        A save input can be any input except netusb ones if the netusb module is
        already in use."""

        netusb_in_use = any(
            [zone.input == self.data.netusb_input for zone in self.data.zones.values()]
        )

        zone = self.data.zones.get(zone_id)

        return [
            source.get('id')
            for source in self._features.get('system', {}).get('input_list', [])
            if source.get('distribution_enable') and
            (source.get('play_info_type') != 'netusb' or not netusb_in_use) and
            source.get('id') not in MC_LINK_SOURCES and
            source.get('id') in (zone.input_list if zone else [])
        ]

    async def _fetch_netusb_presets(self):
        result = await self.device.request_json(NetUSB.get_preset_info())
        self.data.netusb_preset_list = {
            index + 1: (entry.get('input'), entry.get('text'))
            for index, entry in enumerate(result.get('preset_info', []))
            if entry.get('input') != 'unknown'
        }
