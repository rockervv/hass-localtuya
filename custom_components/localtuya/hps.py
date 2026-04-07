 url=https://github.com/rockervv/hass-localtuya/blob/master/custom_components/localtuya/hps.py
"""Platform to present Tuya DP as a human presence sensor."""

import logging
from functools import partial

import voluptuous as vol
from homeassistant.helpers.selector import NumberSelector, NumberSelectorConfig
from homeassistant.helpers.event import async_call_later
from homeassistant.core import callback, CALLBACK_TYPE
from homeassistant.const import CONF_DEVICE_CLASS
from homeassistant.components.binary_sensor import (
    DEVICE_CLASSES_SCHEMA,
    DOMAIN,
    BinarySensorEntity,
)

from .entity import LocalTuyaEntity, async_setup_entry
from .const import CONF_STATE_ON, CONF_RESET_TIMER

CONF_STATE_OFF = "state_off"

_LOGGER = logging.getLogger(__name__)


def flow_schema(dps):
    """Return schema used in config flow."""
    return {
        vol.Required(CONF_STATE_ON, default="presence,1,on"): str,
        vol.Optional(CONF_DEVICE_CLASS, default="occupancy"): DEVICE_CLASSES_SCHEMA,
        vol.Optional(CONF_RESET_TIMER, default=0): NumberSelector(
            NumberSelectorConfig(min=0, unit_of_measurement="Seconds", mode="box")
        ),
    }


class LocalTuyaHumanPresenceSensor(LocalTuyaEntity, BinarySensorEntity):
    """Representation of a Tuya human presence sensor (model 000004yodl)."""

    def __init__(
        self,
        device,
        config_entry,
        sensorid,
        **kwargs,
    ):
        """Initialize the Tuya human presence sensor."""
        super().__init__(device, config_entry, sensorid, _LOGGER, **kwargs)
        self._is_on = False
        self._last_trigger_time = None

        self._reset_timer: float = self._config.get(CONF_RESET_TIMER, 0)
        self._reset_timer_interval: CALLBACK_TYPE | None = None

    @property
    def is_on(self):
        """Return sensor state."""
        return self._is_on

    @property
    def device_class(self):
        """Return device class - occupancy for presence sensors."""
        return self._config.get(CONF_DEVICE_CLASS, "occupancy")

    @property
    def extra_state_attributes(self):
        """Return extra state attributes."""
        attrs = {}
        
        # Add illuminance if available
        if illuminance := self.dp_value("illuminance_value"):
            attrs["illuminance"] = illuminance
        
        # Add sensitivity if available
        if sensitivity := self.dp_value("sensitivity"):
            attrs["sensitivity"] = sensitivity
        
        # Add detection distances if available
        if near_dist := self.dp_value("near_detection"):
            attrs["near_detection_distance"] = near_dist
        
        if far_dist := self.dp_value("far_detection"):
            attrs["far_detection_distance"] = far_dist
        
        # Add timing parameters if available
        if holding_time := self.dp_value("holding_time"):
            attrs["holding_time"] = holding_time
        
        if delay_time := self.dp_value("delay_time"):
            attrs["delay_time"] = delay_time
        
        # Add current scene if available
        if scene := self.dp_value("scene"):
            attrs["scene"] = scene
        
        # Add current detection distance if available
        if dis_current := self.dp_value("dis_current"):
            attrs["current_distance"] = dis_current
        
        # Add last trigger time
        if self._last_trigger_time:
            attrs["last_trigger"] = self._last_trigger_time

        return attrs

    def status_updated(self):
        """Device status was updated."""
        super().status_updated()

        state = str(self.dp_value(self._dp_id)).lower()
        # Check if state matches configured "on" states
        if state in self._config[CONF_STATE_ON].lower().split(","):
            self._is_on = True
            self._last_trigger_time = self.hass.loop.time()
        else:
            self._is_on = False

        # Handle reset timer for auto-off functionality
        if self._reset_timer and self._is_on:
            if self._reset_timer_interval is not None:
                self._reset_timer_interval()
                self._reset_timer_interval = None

            @callback
            def async_reset_state(now):
                """Set the state of the entity to off after timeout."""
                self._status[self._dp_id] = "reset_state_hps"
                self._is_on = False
                self.async_write_ha_state()

            self._reset_timer_interval = async_call_later(
                self.hass, self._reset_timer, async_reset_state
            )

    # No need to restore state for a sensor
    async def restore_state_when_connected(self):
        """Do nothing for a sensor."""
        return


async_setup_entry = partial(
    async_setup_entry, DOMAIN, LocalTuyaHumanPresenceSensor, flow_schema
)
