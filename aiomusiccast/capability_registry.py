from typing import List

from .const import DISPLAY_DIMMER_SPECIALS
from .features import ZoneFeature, DeviceFeature
from .capabilities import OptionSetter, EntityType, NumberSetter, BinarySetter, Capability

"""Dictionary of all DeviceFeatures with a callable as value. 
The callable expects an ID and a MusicCastDevice as parameters."""
_device_capabilities = {
    DeviceFeature.DIMMER: lambda capability_id, device: OptionSetter(
        capability_id,
        "Display Brightness",
        EntityType.CONFIG,
        lambda: device.data.dimmer.dimmer_current,
        lambda value: device.set_dimmer(int(value)),
        {
            x: str(DISPLAY_DIMMER_SPECIALS.get(x, x))
            for x in range(
                int(device.data.dimmer.minimum),
                int(device.data.dimmer.maximum+1),
                int(device.data.dimmer.step)
            )
        }
    ),
    DeviceFeature.SPEAKER_A: lambda capability_id, device: BinarySetter(
        capability_id,
        "Speaker A",
        EntityType.CONFIG,
        lambda: device.data.speaker_a,
        lambda val: device.set_speaker_a(val),
    ),
    DeviceFeature.SPEAKER_B: lambda capability_id, device: BinarySetter(
        capability_id,
        "Speaker B",
        EntityType.CONFIG,
        lambda: device.data.speaker_b,
        lambda val: device.set_speaker_b(val),
    ),
    DeviceFeature.PARTY_MODE: lambda capability_id, device: BinarySetter(
        capability_id,
        "Party Mode",
        EntityType.CONFIG,
        lambda: device.data.party_enable,
        lambda val: device.set_party_mode(val),
    ),
}


"""Dictionary of all ZoneFeatures with a callable as value. 
The callable expects an ID, a MusicCastDevice and a zone_id as parameters."""
_zone_capabilities = {
    ZoneFeature.SURR_DECODER_TYPE: lambda capability_id, device, zone_id: OptionSetter(
        capability_id,
        "Surround Decoder Device",
        EntityType.CONFIG,
        lambda: device.data.zones[zone_id].surr_decoder_type,
        lambda val: device.set_surround_decoder(zone_id, val),
        {key: key for key in device.data.zones[zone_id].surr_decoder_type_list},
    ),
    ZoneFeature.SLEEP: lambda capability_id, device, zone_id: OptionSetter(
        capability_id,
        "Sleep Timer",
        EntityType.CONFIG,
        lambda: device.data.zones[zone_id].sleep_time,
        lambda val: device.set_sleep_timer(zone_id, val),
        {0: "off", 30: "30 min", 60: "60 min", 90: "90 min", 120: "120 min"},
    ),
    ZoneFeature.EQUALIZER: {
        "mode": lambda capability_id, device, zone_id: OptionSetter(
            capability_id,
            "Equalizer Mode",
            EntityType.CONFIG,
            lambda: device.data.zones[zone_id].equalizer_mode,
            lambda val: device.set_equalizer(zone_id, mode=val),
            {key: key for key in device.data.zones[zone_id].equalizer_mode_list},
        ),
        "low": lambda capability_id, device, zone_id: NumberSetter(
            capability_id,
            "Equalizer Low",
            EntityType.CONFIG,
            lambda: device.data.zones[zone_id].equalizer_low,
            lambda val: device.set_equalizer(zone_id, low=int(val)),
            device.data.zones[zone_id].range_step["equalizer"].minimum,
            device.data.zones[zone_id].range_step["equalizer"].maximum,
            device.data.zones[zone_id].range_step["equalizer"].step,
        ),
        "mid": lambda capability_id, device, zone_id: NumberSetter(
            capability_id,
            "Equalizer Mid",
            EntityType.CONFIG,
            lambda: device.data.zones[zone_id].equalizer_mid,
            lambda val: device.set_equalizer(zone_id, mid=int(val)),
            device.data.zones[zone_id].range_step["equalizer"].minimum,
            device.data.zones[zone_id].range_step["equalizer"].maximum,
            device.data.zones[zone_id].range_step["equalizer"].step,
        ),
        "high": lambda capability_id, device, zone_id: NumberSetter(
            capability_id,
            "Equalizer High",
            EntityType.CONFIG,
            lambda: device.data.zones[zone_id].equalizer_high,
            lambda val: device.set_equalizer(zone_id, high=int(val)),
            device.data.zones[zone_id].range_step["equalizer"].minimum,
            device.data.zones[zone_id].range_step["equalizer"].maximum,
            device.data.zones[zone_id].range_step["equalizer"].step,
        ),
    },
    ZoneFeature.TONE_CONTROL: {
        "mode": lambda capability_id, device, zone_id: OptionSetter(
            capability_id,
            "Tone Control Mode",
            EntityType.CONFIG,
            lambda: device.data.zones[zone_id].tone_mode,
            lambda val: device.set_tone_control(zone_id, mode=val),
            {key: key for key in device.data.zones[zone_id].tone_control_mode_list},
        ),
        "bass": lambda capability_id, device, zone_id: NumberSetter(
            capability_id,
            "Tone Control Bass",
            EntityType.CONFIG,
            lambda: device.data.zones[zone_id].tone_bass,
            lambda val: device.set_tone_control(zone_id, bass=int(val)),
            device.data.zones[zone_id].range_step["tone_control"].minimum,
            device.data.zones[zone_id].range_step["tone_control"].maximum,
            device.data.zones[zone_id].range_step["tone_control"].step,
        ),
        "treble": lambda capability_id, device, zone_id: NumberSetter(
            capability_id,
            "Tone Control Treble",
            EntityType.CONFIG,
            lambda: device.data.zones[zone_id].tone_treble,
            lambda val: device.set_tone_control(zone_id, treble=int(val)),
            device.data.zones[zone_id].range_step["tone_control"].minimum,
            device.data.zones[zone_id].range_step["tone_control"].maximum,
            device.data.zones[zone_id].range_step["tone_control"].step,
        ),
    },
    ZoneFeature.DIALOGUE_LEVEL: lambda capability_id, device, zone_id: NumberSetter(
        capability_id,
        "Dialogue Level",
        EntityType.CONFIG,
        lambda: device.data.zones[zone_id].dialogue_level,
        lambda val: device.set_dialogue_level(zone_id, int(val)),
        device.data.zones[zone_id].range_step["dialogue_level"].minimum,
        device.data.zones[zone_id].range_step["dialogue_level"].maximum,
        device.data.zones[zone_id].range_step["dialogue_level"].step,
    ),
    ZoneFeature.DIALOGUE_LIFT: lambda capability_id, device, zone_id: NumberSetter(
        capability_id,
        "Dialogue Lift",
        EntityType.CONFIG,
        lambda: device.data.zones[zone_id].dialogue_lift,
        lambda val: device.set_dialogue_lift(zone_id, int(val)),
        device.data.zones[zone_id].range_step["dialogue_lift"].minimum,
        device.data.zones[zone_id].range_step["dialogue_lift"].maximum,
        device.data.zones[zone_id].range_step["dialogue_lift"].step,
    ),
    ZoneFeature.DTS_DIALOGUE_CONTROL: lambda capability_id, device, zone_id: NumberSetter(
        capability_id,
        "DTS Dialogue Control",
        EntityType.CONFIG,
        lambda: device.data.zones[zone_id].dts_dialogue_control,
        lambda val: device.set_dts_dialogue_control(zone_id, int(val)),
        device.data.zones[zone_id].range_step["dts_dialogue_control"].minimum,
        device.data.zones[zone_id].range_step["dts_dialogue_control"].maximum,
        device.data.zones[zone_id].range_step["dts_dialogue_control"].step,
    ),
    ZoneFeature.LINK_AUDIO_DELAY: lambda capability_id, device, zone_id: OptionSetter(
        capability_id,
        "Link Audio Delay",
        EntityType.CONFIG,
        lambda: device.data.zones[zone_id].link_audio_delay,
        lambda val: device.set_link_audio_delay(zone_id, val),
        {key: key for key in device.data.zones[zone_id].link_audio_delay_list},
    ),
    ZoneFeature.LINK_CONTROL: lambda capability_id, device, zone_id: OptionSetter(
        capability_id,
        "Link Control",
        EntityType.CONFIG,
        lambda: device.data.zones[zone_id].link_control,
        lambda val: device.set_link_control(zone_id, val),
        {key: key for key in device.data.zones[zone_id].link_control_list},
    ),
    ZoneFeature.LINK_AUDIO_QUALITY: lambda capability_id, device, zone_id: OptionSetter(
        capability_id,
        "Link Audio Quality",
        EntityType.CONFIG,
        lambda: device.data.zones[zone_id].link_audio_quality,
        lambda val: device.set_link_audio_quality(zone_id, val),
        {key: key for key in device.data.zones[zone_id].link_audio_quality_list},
    ),
    ZoneFeature.BASS_EXTENSION: lambda capability_id, device, zone_id: BinarySetter(
        capability_id,
        "Bass Extension",
        EntityType.CONFIG,
        lambda: device.data.zones[zone_id].bass_extension,
        lambda val: device.set_bass_extension(zone_id, val),
    ),
    ZoneFeature.EXTRA_BASS: lambda capability_id, device, zone_id: BinarySetter(
        capability_id,
        "Extra Bass",
        EntityType.CONFIG,
        lambda: device.data.zones[zone_id].extra_bass,
        lambda val: device.set_extra_bass(zone_id, val),
    ),
    ZoneFeature.ENHANCER: lambda capability_id, device, zone_id: BinarySetter(
        capability_id,
        "Enhancer",
        EntityType.CONFIG,
        lambda: device.data.zones[zone_id].enhancer,
        lambda val: device.set_enhancer(zone_id, val),
    ),
    ZoneFeature.PURE_DIRECT: lambda capability_id, device, zone_id: BinarySetter(
        capability_id,
        "Pure Direct",
        EntityType.CONFIG,
        lambda: device.data.zones[zone_id].pure_direct,
        lambda val: device.set_pure_direct(zone_id, val),
    ),
    ZoneFeature.ADAPTIVE_DRC: lambda capability_id, device, zone_id: BinarySetter(
        capability_id,
        "Adaptive DRC",
        EntityType.CONFIG,
        lambda: device.data.zones[zone_id].adaptive_drc,
        lambda val: device.set_adaptive_drc(zone_id, val),
    ),
}


def build_device_capabilities(device: "MusicCastDevice") -> List[Capability]:
    """
    Function to build all Capabilities of a given device.
    The ID of the capabilities will be set to '{feature.name.lower()}_{key}'
    @param device: The MusicCastDevice to generate the capabilities for
    @return: the list of capabilities of the device
    """
    result = []
    for feature in [f for f in DeviceFeature if f in device.features]:
        feature_entry = _device_capabilities.get(feature)
        if feature_entry is not None:
            if isinstance(feature_entry, dict):
                for key, capability in feature_entry.items():
                    capability_id = f"{feature.name}_{key}"
                    result.append(capability(capability_id, device))
            else:
                result.append(feature_entry(feature.name, device))
    return result


def build_zone_capabilities(device: "MusicCastDevice", zone_id) -> List[Capability]:
    """
    Function to build all Capabilities of a given zone of a device.
    The ID of the capabilities will be set to 'zone_{feature.name.lower()}_{key}'
    @param device: The MusicCastDevice to generate the capabilities for
    @param zone_id: The zone to generate the capabilities for
    @return: The list of capabilities of the given zone
    """
    result = []
    for feature in [f for f in ZoneFeature if f in device.data.zones[zone_id].features]:
        feature_entry = _zone_capabilities.get(feature)
        if feature_entry is not None:
            if isinstance(feature_entry, dict):
                for key, capability in feature_entry.items():
                    capability_id = f"zone_{feature.name}_{key}"
                    result.append(capability(capability_id, device, zone_id))
            else:
                result.append(feature_entry(f"zone_{feature.name}", device, zone_id))
    return result
