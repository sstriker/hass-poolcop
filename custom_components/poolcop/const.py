"""Constants for the PoolCop integration."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Final

DOMAIN: Final = "poolcop"
LOGGER = logging.getLogger(__package__)

# Tokens are good for 90 requests and valid for 900s,
# the interval of 12 allows for 15 service requests
# next to status updates.
SCAN_INTERVAL = timedelta(seconds=12)
