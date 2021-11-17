from abc import ABC
from enum import Enum
from typing import Any, Callable, Dict


class EntityTypes(Enum):
    """Type of the Capability."""
    REGULAR = 1  # For major features
    CONFIG = 2  # For features to configure the device or a zone
    DIAGNOSTIC = 3  # For diagnostic values or settings
    SYSTEM = 4  # Features for internal usage only


class Capability(ABC):
    """Base class for all capabilities."""
    id: str
    name: str
    entity_type: EntityTypes
    get_current: Callable

    def __init__(self, capability_id, name, entity_type, get_current):
        """
        Initialize the base class and set general vars.
        @param capability_id: Unique ID of this capability
        @param name: Name that should be displayed in a UI
        @param entity_type: Define of what type this capability is
        @param get_current: Callable to get the current values of this capability
        """
        self.id = capability_id
        self.name = name
        self.entity_type = entity_type
        self.get_current = get_current

    @property
    def current(self) -> Any:
        return self.get_current()


class SetableCapability(Capability, ABC):
    """Base class for a capability, which is not read only."""
    set_current: Callable

    def __init__(self, capability_id, name, entity_type, get_current, set_current):
        """
        Initialize the setable base class.
        @param capability_id: Unique ID of this capability
        @param name: Name that should be displayed in a UI
        @param entity_type: Define of what type this capability is
        @param get_current: Callable to get the current values of this capability
        @param set_current: Callable to set the value. Should only expect the new values as parameter
        """
        super().__init__(capability_id, name, entity_type, get_current)
        self.set_current = set_current

    async def set(self, value):
        await self.set_current(value)


class NumberSensor(Capability):
    pass


class BinarySensor(Capability):
    pass


class TextSensor(Capability):
    pass


class NumberSetter(SetableCapability):
    """Class to set numbers"""
    min_value: float
    max_value: float
    step: float

    def __init__(self, capability_id, name, entity_type, get_current, set_current, min_value, max_value, step):
        """
        Initialize a NumberSetter
        @param capability_id: Unique ID of this capability
        @param name: Name that should be displayed in a UI
        @param entity_type: Define of what type this capability is
        @param get_current: Callable to get the current values of this capability
        @param set_current: Callable to set the value. Should only expect the new values as parameter
        @param min_value: Minimum value, which can be set
        @param max_value: Maximum value, which can be set
        @param step: The step between minimum and maximum
        """
        super().__init__(capability_id, name, entity_type, get_current, set_current)
        self.min_value = min_value
        self.max_value = max_value
        self.step = step


class OptionSetter(SetableCapability):
    """A capability to set a value from a list of valid options."""
    options: Dict[str, str]

    def __init__(self, capability_id, name, entity_type, get_current, set_current, options):
        """
        Initialize a option setter
        @param capability_id: Unique ID of this capability
        @param name: Name that should be displayed in a UI
        @param entity_type: Define of what type this capability is
        @param get_current: Callable to get the current values of this capability
        @param set_current: Callable to set the value. Should only expect the new values as parameter
        @param options: A dictionary of valid options with the option as key and a label as value
        """
        super().__init__(capability_id, name, entity_type, get_current, set_current)
        self.options = options

    async def set(self, value):
        if value not in self.options.keys():
            raise ValueError("The given value is not a valid option")
        await super(OptionSetter, self).set(value)


class BinarySetter(SetableCapability):
    """A class to set boolean values."""
    pass
