#!/usr/bin/env python3
# Copyright 2024 Adrian Wennström
# See LICENSE file for licensing details.

"""Charm the application."""

from subprocess import run
import logging

import ops

from config import ConfigValidator, ConfigManager
from service_manager import ServiceManager
from file_manager import FileManager

logger = logging.getLogger(__name__)

class CollectorCharm(ops.CharmBase):
    """Charm the application."""

    def __init__(self, framework: ops.Framework):
        super().__init__(framework)

        # Initialize managers
        self.config_manager = ConfigManager(self.model.config)
        self.service_manager = ServiceManager(lambda status: setattr(self.model.unit, 'status', status))

        framework.observe(self.on.config_changed, self._on_config_changed)
        framework.observe(self.on.update_status, self._on_update_status)

        framework.observe(self.on["db-integrator"].relation_joined, self._on_request_db)
        framework.observe(self.on["db-integrator"].relation_changed, self._on_update_db_credentials)

        framework.observe(self.on['start'].action, self._on_service_start)
        framework.observe(self.on['stop'].action, self._on_service_stop)
        framework.observe(self.on['restart'].action, self._on_service_restart)

    def _on_config_changed(self, event: ops.ConfigChangedEvent):
        """Handle configuration changes."""
        logger.info("Configuration changed, updating...")
        self.model.unit.status = ops.MaintenanceStatus("Updating configuration...")

        # Read the old and new configurations
        old_config = FileManager.read_config()
        new_config = self.config_manager.get_config()

        logger.info(f"Snapshot: {event.snapshot()}")
        logger.info(f"Old configuration: {old_config}")
        logger.info(f"New configuration: {new_config}")

        try:
            # Validate the new configuration
            ConfigValidator.validate_config(new_config)
        except ValueError as e:
            logger.error(f"Configuration validation failed: {e}")
            self.model.unit.status = ops.BlockedStatus(f"Configuration error: {e}")
            return

        # Check for changes in the configuration
        changed_configs = {field: new_config[field] for field in new_config if old_config.get(field) != new_config[field]}

        # If there are changes, update the configuration and generate the environment file
        if changed_configs:
            logger.info(f"Configuration changed: {changed_configs}")
            FileManager.store_config(new_config)

            if ("channel" in changed_configs or "revision" in changed_configs):
                # Fetch the collector from GitHub if the release tag, repo or sub-directory has changed
                try:
                    # Install dependencies
                    self.model.unit.status = ops.MaintenanceStatus("Installing haproxy-collector")
                    self._install_collector(changed_configs)
                    self.unit.set_workload_version(self._get_version())
                except Exception as e:
                    logger.error(f"Failed to install haproxy-collector: {e}")
                    self.model.unit.status = ops.BlockedStatus(f"Dependency installation failed: {e}")
                    return

            try:
                # Register collector service args
                self.model.unit.status = ops.MaintenanceStatus("Registering service args...")
                self._register_service_args()
            except Exception as e:
                logger.error(f"Failed to register service args: {e}")
                self.model.unit.status = ops.BlockedStatus(f"Service args registration failed: {e}")
                return
            
            logger.info("Configuration updated successfully.")
            self._on_service_restart(event)
        else:
            logger.info("No configuration changes detected.")
            self.model.unit.status = ops.ActiveStatus("Running")
            
    def _on_request_db(self, event):
        """Request a database relation."""
        logger.info("Requesting database relation...")
        event.relation.data[self.unit]["name"] = self.config.get("collector-name")
        logger.info("Database relation requested successfully.")

    def _on_update_db_credentials(self, event):
        """Update the database credentials."""
        logger.info("Updating database credentials...")
        owner_id = event.relation.data[event.unit].get("owner_id")
        db_url = event.relation.data[event.unit].get("credentials")
        if not owner_id or not db_url:
            logger.error("Missing database credentials or owner ID.")
            self.model.unit.status = ops.BlockedStatus("Missing database credentials or owner ID.")
            return
        
        # Store the database credentials in the configuration file
        db_config = {
            "owner_id": owner_id,
            "db_url": db_url
        }
        FileManager.store_db_config(db_config)

        # Update the service args with the new database credentials
        try:
            self.model.unit.status = ops.MaintenanceStatus("Update service args...")
            self._register_service_args()
            self._on_service_restart(None)
            logger.info("Database credentials updated successfully.")
        except Exception as e:
            logger.error(f"Failed to update database credentials: {e}")
            self.model.unit.status = ops.BlockedStatus(f"Database credentials update failed: {e}")
            return
        
    def _on_update_status(self, event: ops.EventBase):
        # Update the unit status with the current workload version
        try:
            self.unit.set_workload_version(self._get_version())
        except Exception as e:
            logger.error(f"Failed to update workload version: {e}")
            return

    def _on_service_start(self, event: ops.ActionEvent):
        """Start the collector service."""
        try:
            self.model.unit.status = ops.MaintenanceStatus("Starting service...")
            self.service_manager.start_service()
            self.model.unit.status = ops.ActiveStatus("Running")
        except Exception as e:
            logger.error(f"Failed to start service: {e}")
            self.model.unit.status = ops.BlockedStatus(f"Service start failed: {e}")
            return
        
    def _on_service_stop(self, event: ops.ActionEvent):
        """Stop the collector service."""
        try:
            self.model.unit.status = ops.MaintenanceStatus("Stopping service...")
            self.service_manager.stop_service()
            self.model.unit.status = ops.BlockedStatus("Stopped")
        except Exception as e:
            logger.error(f"Failed to stop service: {e}")
            self.model.unit.status = ops.BlockedStatus(f"Service stop failed: {e}")
            return
    
    def _on_service_restart(self, event):
        """Restart the collector service."""
        try:
            self.model.unit.status = ops.MaintenanceStatus("Restarting service...")
            self.service_manager.restart_service()
            self.model.unit.status = ops.ActiveStatus("Running")
        except Exception as e:
            logger.error(f"Failed to restart service: {e}")
            self.model.unit.status = ops.BlockedStatus(f"Service restart failed: {e}")
            return
    
    def _install_collector(self, config):
        logger.info("Installing haproxy-collector")
        haproxy_install_command = ["snap", "install", "haproxy-collector"]
        if config.get("revision"):
            haproxy_install_command.append(f"--revision={config['revision']}")
        elif config.get("channel"):
            haproxy_install_command.append(f"--channel={config['channel']}")
        run(haproxy_install_command)    
        logger.info("Haproxy installed successfully.")
    
    def _get_version(self):
        """Get the version of the collector."""
        try:
            output = run(["snap", "info", "haproxy-collector"], text=True, capture_output=True)
            for line in output.stdout.splitlines():
                if line.startswith("installed:"):
                    return line.split()[1]
        except Exception as e:
            print(f"Error getting collector version: {e}")
        return "unknown"

    def _register_service_args(self):
        # Register collector service args
        logger.info("Registering service args...")
        service_args = FileManager.get_service_args()
        run(["snap", "set", "haproxy-collector", f"args={service_args}"], check=True)
        logger.info("Service args Registered successfully.")

if __name__ == "__main__":  # pragma: nocover
    ops.main(CollectorCharm)  # type: ignore
