from __future__ import annotations

from abc import ABC
from collections.abc import Awaitable, Callable, Mapping
from enum import Enum
from typing import Any

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
    get_value: Callable[[], Any]

    def __init__(
        self,
        capability_id: str,
        name: str,
        entity_type: EntityType,
        get_value: Callable[[], Any],
    ) -> None:
        """Initialize the base class and set general vars.

        Parameters
        ----------
        capability_id : Any
            Unique ID of this capability.
        name : Any
            Name that should be displayed in a UI.
        entity_type : Any
            Defines the type of entity the capability represents.
        get_value : Callable[[], Any]
            Callback that returns the current value of the capability.
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

    set_value: Callable[[Any], Awaitable[None]]

    def __init__(
        self,
        capability_id: str,
        name: str,
        entity_type: EntityType,
        get_value: Callable[[], Any],
        set_value: Callable[[Any], Awaitable[None]],
    ) -> None:
        """Initialize the setable base class.

        Parameters
        ----------
        capability_id : Any
            Unique ID of this capability.
        name : Any
            Name that should be displayed in a UI.
        entity_type : Any
            Defines the type of entity this capability represents.
        get_value : Callable[[], Any]
            Callback used to obtain the current value.
        set_value : Callable[[Any], Awaitable[None]]
            Asynchronous callback that persists new values supplied by the caller.
        """
        super().__init__(capability_id, name, entity_type, get_value)
        self.set_value = set_value

    async def set(self, value: Any) -> None:
        await self.set_value(value)


class NumberSensor(Capability):
    pass


class BinarySensor(Capability):
    pass


class TextSensor(Capability):
    pass


class NumberSetter(SettableCapability):
    """Class to set numbers."""

    value_range: RangeStep

    def __init__(
        self,
        capability_id: str,
        name: str,
        entity_type: EntityType,
        get_value: Callable[[], Any],
        set_value: Callable[[Any], Awaitable[None]],
        min_value: int,
        max_value: int,
        step: int,
    ) -> None:
        """Initialize a NumberSetter.

        Parameters
        ----------
        capability_id : Any
            Unique ID of this capability
        name : Any
            Name that should be displayed in a UI
        entity_type : Any
            Define of what type this capability is
        get_value : Any
            Callable to get the current values of this capability
        set_value : Any
            Callable to set the value. Should only expect the new values as parameter
        min_value : Any
            Minimum value, which can be set
        max_value : Any
            Maximum value, which can be set
        step : Any
            The step between minimum and maximum
        """
        super().__init__(capability_id, name, entity_type, get_value, set_value)
        self.value_range = RangeStep(min_value, max_value, step)

    async def set(self, value: int) -> None:
        self.value_range.check(value)
        await super().set(value)


class OptionSetter(SettableCapability):
    """A capability to set a value from a list of valid options."""

    options: Mapping[str | int, str]

    def __init__(
        self,
        capability_id: str,
        name: str,
        entity_type: EntityType,
        get_value: Callable[[], Any],
        set_value: Callable[[Any], Awaitable[None]],
        options: Mapping[str | int, str],
    ) -> None:
        """Initialize an option setter.

        Parameters
        ----------
        capability_id : Any
            Unique ID of this capability
        name : Any
            Name that should be displayed in a UI
        entity_type : Any
            Define of what type this capability is
        get_value : Any
            Callable to get the current values of this capability
        set_value : Any
            Callable to set the value. Should only expect the new values as parameter
        options : Any
            A dictionary of valid options with the option as key and a label as value
        """
        super().__init__(capability_id, name, entity_type, get_value, set_value)
        self.options = options

    async def set(self, value: str | int) -> None:
        if value not in self.options:
            raise ValueError("The given value is not a valid option")
        await super().set(value)


class BinarySetter(SettableCapability):
    """A class to set boolean values."""

    async def set(self, value: bool) -> None:
        if not isinstance(value, bool):
            raise ValueError("The given value is not a boolean value")
        await super().set(value)
