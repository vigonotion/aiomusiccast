from abc import ABC
from enum import Enum
from typing import Any, Callable, Dict

from aiomusiccast.musiccast_data import RangeStep


class EntityType(Enum):
    """Type of the Capability."""
    REGULAR = 1  # For major features
    CONFIG = 2  # For features to configure the device or a zone
    DIAGNOSTIC = 3  # For diagnostic values or settings


class Capability(ABC):
    """Base class for all capabilities."""
    id: str
    name: str
    entity_type: EntityType
    get_value: Callable

    def __init__(self, capability_id, name, entity_type, get_value):
        """
        Initialize the base class and set general vars.
        @param capability_id: Unique ID of this capability
        @param name: Name that should be displayed in a UI
        @param entity_type: Define of what type this capability is
        @param get_value: Callable to get the current values of this capability
        """
        self.id = capability_id
        self.name = name
        self.entity_type = entity_type
        self.get_value = get_value

    @property
    def current(self) -> Any:
        return self.get_value()


class SettableCapability(Capability, ABC):
    """Base class for a capability, which is not read only."""
    set_value: Callable

    def __init__(self, capability_id, name, entity_type, get_value, set_value):
        """
        Initialize the setable base class.
        @param capability_id: Unique ID of this capability
        @param name: Name that should be displayed in a UI
        @param entity_type: Define of what type this capability is
        @param get_value: Callable to get the current values of this capability
        @param set_value: Callable to set the value. Should only expect the new values as parameter
        """
        super().__init__(capability_id, name, entity_type, get_value)
        self.set_value = set_value

    async def set(self, value):
        await self.set_value(value)


class NumberSensor(Capability):
    pass


class BinarySensor(Capability):
    pass


class TextSensor(Capability):
    pass


class NumberSetter(SettableCapability):
    """Class to set numbers"""
    value_range: RangeStep

    def __init__(self, capability_id, name, entity_type, get_value, set_value, min_value, max_value, step):
        """
        Initialize a NumberSetter
        @param capability_id: Unique ID of this capability
        @param name: Name that should be displayed in a UI
        @param entity_type: Define of what type this capability is
        @param get_value: Callable to get the current values of this capability
        @param set_value: Callable to set the value. Should only expect the new values as parameter
        @param min_value: Minimum value, which can be set
        @param max_value: Maximum value, which can be set
        @param step: The step between minimum and maximum
        """
        super().__init__(capability_id, name, entity_type, get_value, set_value)
        self.value_range = RangeStep()
        self.value_range.minimum = min_value
        self.value_range.maximum = max_value
        self.value_range.step = step
        
    async def set(self, value):
        self.value_range.check(value)
        await super(NumberSetter, self).set(value)


class OptionSetter(SettableCapability):
    """A capability to set a value from a list of valid options."""
    options: Dict[str, str]

    def __init__(self, capability_id, name, entity_type, get_value, set_value, options):
        """
        Initialize a option setter
        @param capability_id: Unique ID of this capability
        @param name: Name that should be displayed in a UI
        @param entity_type: Define of what type this capability is
        @param get_value: Callable to get the current values of this capability
        @param set_value: Callable to set the value. Should only expect the new values as parameter
        @param options: A dictionary of valid options with the option as key and a label as value
        """
        super().__init__(capability_id, name, entity_type, get_value, set_value)
        self.options = options

    async def set(self, value):
        if value not in self.options.keys():
            raise ValueError("The given value is not a valid option")
        await super(OptionSetter, self).set(value)


class BinarySetter(SettableCapability):
    """A class to set boolean values."""
    async def set(self, value):
        if not isinstance(value, bool):
            raise ValueError("The given value is not a boolean value")
        await super().set(value)
