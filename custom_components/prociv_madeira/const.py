"""Constants for prociv_madeira."""

from logging import Logger
from logging import getLogger

LOGGER: Logger = getLogger(__package__)

DOMAIN = "prociv_madeira"
ATTRIBUTION = "Data provided by ProCiv Madeira"

CONF_SCAN_INTERVAL = "scan_interval"
DEFAULT_SCAN_INTERVAL = 30  # minutes
MIN_SCAN_INTERVAL = 5  # minutes
MAX_SCAN_INTERVAL = 1440  # minutes (24 hours)
