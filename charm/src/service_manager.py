#!/usr/bin/env python3
# Copyright 2024 Adrian Wennström
# See LICENSE file for licensing details.

"""Service management for the collector charm."""

import logging
from subprocess import run

logger = logging.getLogger(__name__)


class ServiceManager:
    """Handles systemd service operations for the collector charm."""
    
    def __init__(self, unit_status_setter):
        """Initialize with a unit status setter function.
        
        Args:
            unit_status_setter: Function to set unit status (e.g., self.model.unit.status)
        """
        self.set_status = unit_status_setter
    
    def start_service(self) -> None:
        """Start the collector timer."""
        
        # Start the service
        logger.info("Starting collector timer...")
        run(["snap", "start", "haproxy-collector.timer"], check=True)
        logger.info("Collector timer started successfully.")

    def stop_service(self) -> None:
        """Stop the collector timer."""
        
        # Stop the service
        logger.info("Stopping collector timer...")
        run(["snap", "stop", "haproxy-collector.timer"])
        logger.info("Collector timer stopped successfully.")
    
    def restart_service(self) -> None:
        """Restart the collector timer."""
        
        # Restart the service
        logger.info("Restarting collector timer...")
        run(["snap", "restart", "haproxy-collector.timer"], check=True)
        logger.info("Collector timer restarted successfully.")
