from aiomusiccast.features import DeviceFeature, ZoneFeature


DEVICE_FUNC_LIST_TO_FEATURE_MAPPING = {
    "wired_lan": DeviceFeature.WIRED_LAN,
    "wireless_lan": DeviceFeature.WIRELESS_LAN,
    "wireless_direct": DeviceFeature.WIRELESS_DIRECT,
    "extend_1_band": DeviceFeature.EXTEND_1_BAND,
    "dfs_option": DeviceFeature.DFS_OPTION,
    "network_standby": DeviceFeature.NETWORK_STANDBY,
    "network_standby_auto": DeviceFeature.NETWORK_STANDBY_AUTO,
    "bluetooth_standby": DeviceFeature.BLUETOOTH_STANDBY,
    "bluetooth_tx_setting": DeviceFeature.BLUETOOTH_TX_SETTING,
    'bluetooth_tx_connectivity_type': DeviceFeature.BLUETOOTH_TX_CONNECTIVITY_TYPE,
    "auto_power_standby": DeviceFeature.AUTO_POWER_STANDBY,
    "ir_sensor": DeviceFeature.IR_SENSOR,
    "speaker_a": DeviceFeature.SPEAKER_A,
    "speaker_b": DeviceFeature.SPEAKER_B,
    "headphone": DeviceFeature.HEADPHONE,
    "dimmer": DeviceFeature.DIMMER,
    "zone_b_volume_sync": DeviceFeature.ZONE_B_VOLUME_SYNC,
    "hdmi_out_1": DeviceFeature.HDMI_OUT_1,
    "hdmi_out_2": DeviceFeature.HDMI_OUT_2,
    "hdmi_out_3": DeviceFeature.HDMI_OUT_3,
    "airplay": DeviceFeature.AIRPLAY,
    "stereo_pair": DeviceFeature.STEREO_PAIR,
    "speaker_settings": DeviceFeature.SPEAKER_SETTINGS,
    "disklavier_settings": DeviceFeature.DISKLAVIER_SETTINGS,
    "background_download": DeviceFeature.BACKGROUND_DOWNLOAD,
    "remote_info": DeviceFeature.REMOTE_INFO,
    "network_reboot": DeviceFeature.NETWORK_REBOOT,
    "system_reboot": DeviceFeature.SYSTEM_REBOOT,
    "auto_play": DeviceFeature.AUTO_PLAY,
    "speaker_pattern": DeviceFeature.SPEAKER_PATTERN,
    "party_mode": DeviceFeature.PARTY_MODE,
    'analytics': DeviceFeature.ANALYTICS,
    "ypao_volume": DeviceFeature.YPAO_VOLUME,
    "party_volume": DeviceFeature.PARTY_VOLUME,
    "party_mute": DeviceFeature.PARTY_MUTE,
    "name_text_avr": DeviceFeature.NAME_TEXT_AVR,
    "hdmi_standby_through": DeviceFeature.HDMI_STANDBY_THROUGH,
}


ZONE_FUNC_LIST_TO_FEATURE_MAPPING = {
    "power": ZoneFeature.POWER,
    "sleep": ZoneFeature.SLEEP,
    "volume": ZoneFeature.VOLUME,
    "mute": ZoneFeature.MUTE,
    "sound_program": ZoneFeature.SOUND_PROGRAM,
    "surround_3d": ZoneFeature.SURROUND_3D,
    "direct": ZoneFeature.DIRECT,
    "pure_direct": ZoneFeature.PURE_DIRECT,
    "enhancer": ZoneFeature.ENHANCER,
    "tone_control": ZoneFeature.TONE_CONTROL,
    "equalizer": ZoneFeature.EQUALIZER,
    "balance": ZoneFeature.BALANCE,
    "dialogue_level": ZoneFeature.DIALOGUE_LEVEL,
    "dialogue_lift": ZoneFeature.DIALOGUE_LIFT,
    "clear_voice": ZoneFeature.CLEAR_VOICE,
    "subwoofer_volume": ZoneFeature.SUBWOOFER_VOLUME,
    "bass_extension": ZoneFeature.BASS_EXTENSION,
    "signal_info": ZoneFeature.SIGNAL_INFO,
    "prepare_input_change": ZoneFeature.PREPARE_INPUT_CHANGE,
    "link_control": ZoneFeature.LINK_CONTROL,
    "link_audio_delay": ZoneFeature.LINK_AUDIO_DELAY,
    "link_audio_quality": ZoneFeature.LINK_AUDIO_QUALITY,
    "scene": ZoneFeature.SCENE,
    "contents_display": ZoneFeature.CONTENTS_DISPLAY,
    "cursor": ZoneFeature.CURSOR,
    "menu": ZoneFeature.MENU,
    "actual_volume": ZoneFeature.ACTUAL_VOLUME,
    "audio_select": ZoneFeature.AUDIO_SELECT,
    "surr_decoder_type": ZoneFeature.SURR_DECODER_TYPE,
    "extra_bass": ZoneFeature.EXTRA_BASS,
    "adaptive_drc": ZoneFeature.ADAPTIVE_DRC,
    "dts_dialogue_control": ZoneFeature.DTS_DIALOGUE_CONTROL,
    "adaptive_dsp_level": ZoneFeature.ADAPTIVE_DSP_LEVEL,
    "mono": ZoneFeature.MONO,
}

MIME_TYPE_UPNP_CLASS = {
    "application/x-mpegurl": "object.item.videoItem",
    "image": "object.item.imageItem",
    "video": "object.item.videoItem",
    "application/dash+xml": "object.item.videoItem",
    "application/vnd.apple.mpegurl": "object.item.videoItem",
    "audio": "object.item.audioItem",
}

ALARM_WEEK_DAYS = [
    "sunday",
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
]

ALARM_ONEDAY = "oneday"
ALARM_WEEKLY = "weekly"
MC_LINK = "mc_link"
MAIN_SYNC = "main_sync"
MC_LINK_SOURCES = [MC_LINK, MAIN_SYNC]
NULL_GROUP = "00000000000000000000000000000000"

DISPLAY_DIMMER_SPECIALS = {
    -1: "auto"
}
