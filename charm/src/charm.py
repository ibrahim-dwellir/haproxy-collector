#!/usr/bin/env python3
# Copyright 2024 Adrian Wennström
# See LICENSE file for licensing details.

"""Charm the application."""

from subprocess import run
import logging

import ops
import os.path

from config import ConfigValidator, ConfigManager
from service_manager import ServiceManager
from github_client import GitHubClient
from file_manager import FileManager

logger = logging.getLogger(__name__)
dest_dir = FileManager.DEST_DIR


class CollectorCharm(ops.CharmBase):
    """Charm the application."""

    def __init__(self, framework: ops.Framework):
        super().__init__(framework)

        # Initialize managers
        self.config_manager = ConfigManager(self.model.config)
        self.service_manager = ServiceManager(lambda status: setattr(self.model.unit, 'status', status))

        framework.observe(self.on.install, self._on_install)
        framework.observe(self.on.config_changed, self._on_config_changed)

        framework.observe(self.on["db-integrator"].relation_joined, self._on_request_db)
        framework.observe(self.on["db-integrator"].relation_changed, self._on_update_credentials)

        framework.observe(self.on['start'].action, self._on_service_start)
        framework.observe(self.on['stop'].action, self._on_service_stop)
        framework.observe(self.on['restart'].action, self._on_service_restart)
        framework.observe(self.on['reload'].action, self._on_reload)

    def _on_install(self, event: ops.InstallEvent):
        """Handle the install event."""
        config = self.config_manager.get_config()
        try:
            logger.info("Validating configuration...")
            self.model.unit.status = ops.MaintenanceStatus("Validating configuration...")

            ConfigValidator.validate_config(config)

            logger.info("Configuration validated successfully.")
            self.model.unit.status = ops.MaintenanceStatus("Configuration validated successfully.")
        except ValueError as e:
            logger.error(f"Configuration validation failed: {e}")
            self.model.unit.status = ops.BlockedStatus(f"Configuration error: {e}")
            return

        # Store the configuration
        FileManager.store_config(config)
        
        # Generate the environment file
        FileManager.generate_environment_file()
        
        try:
            # Install dependencies
            logger.info("Installing dependencies...")
            self.model.unit.status = ops.MaintenanceStatus("Installing dependencies...")
            run(["apt", "install", "-y", "python3-pip"])

            logger.info("Dependencies installed successfully.")
            self.model.unit.status = ops.ActiveStatus("Running")
        except Exception as e:
            logger.error(f"Failed to install dependencies: {e}")
            self.model.unit.status = ops.BlockedStatus(f"Dependency installation failed: {e}")
            return

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

            if ("release_tag" in changed_configs or "github_repo" in changed_configs or "sub_directory" in changed_configs):
                # Fetch the collector from GitHub if the release tag, repo or sub-directory has changed
                try:
                    GitHubClient.fetch_collector(new_config, dest_dir)
                    logger.info("Collector fetched successfully.")

                    self.unit.set_workload_version(new_config.get("release_tag"))
                except Exception as e:
                    logger.error(f"Failed to fetch collector: {e}")
                    self.model.unit.status = ops.BlockedStatus(f"Failed to fetch collector: {e}")
                    return
                
                try:
                    logger.info("Installing dependencies...")
                    self.model.unit.status = ops.MaintenanceStatus("Installing dependencies...")
                    FileManager.install_dependencies()
                    logger.info("Dependencies installed successfully.")
                except Exception as e:
                    logger.error(f"Failed to install dependencies: {e}")
                    self.model.unit.status = ops.BlockedStatus(f"Dependency installation failed: {e}")
                    return
                else:
                    logger.info("No changes in collector configuration, skipping fetch.")
            
            if "entrypoint" in changed_configs or "frequency" in changed_configs:
                try:
                    # Generate the service file
                    FileManager.generate_service_file(new_config)
                except Exception as e:
                    logger.error(f"Failed to generate service file: {e}")
                    self.model.unit.status = ops.BlockedStatus(f"Service file generation failed: {e}")
                    return

            # Generate the environment file with the new configuration
            FileManager.generate_environment_file()
            # Reload the systemd daemon to recognize the new service and timer
            self.service_manager.reload_daemon()
            
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

    def _on_update_credentials(self, event):
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

        # Update the environment file with the new database credentials
        FileManager.generate_environment_file()
        logger.info("Database credentials updated successfully.")

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

    def _on_reload(self, event: ops.ActionEvent):
        """Refresh the collector service."""
        self.model.unit.status = ops.MaintenanceStatus("Refreshing collector service...")
        logger.info("Refreshing collector service with new configuration...")

        config = self.config_manager.get_config()

        # Validate the configuration
        self.model.unit.status = ops.MaintenanceStatus("Validating configuration...")
        logger.info("Validating configuration...")
        ConfigValidator.validate_config(config)
        logger.info("Configuration validated successfully.")
        
        # Store the configuration
        self.model.unit.status = ops.MaintenanceStatus("Storing configuration...")
        logger.info("Storing configuration...")
        FileManager.store_config(config)
        logger.info("Configuration stored successfully.")

        # Stop the service
        logger.info("Stopping collector service...")
        self.service_manager.stop_service()
        logger.info("Collector service stopped successfully.")

        try:
            # Fetch the collector from GitHub if needed
            self.model.unit.status = ops.MaintenanceStatus("Fetching collector from GitHub...")
            logger.info("Fetching collector from GitHub...")
            GitHubClient.fetch_collector(config, dest_dir)
            logger.info("Collector fetched successfully.")
        except Exception as e:
            logger.error(f"Failed to fetch collector: {e}")
            self.model.unit.status = ops.BlockedStatus(f"Failed to fetch collector from Github: {e}")
            return

        # Install dependencies
        self.model.unit.status = ops.MaintenanceStatus("Installing dependencies...")
        logger.info("Installing dependencies...")
        try:
            FileManager.install_dependencies()
            logger.info("Dependencies installed successfully.")
        except Exception as e:
            logger.error(f"Failed to install dependencies: {e}")
            self.model.unit.status = ops.BlockedStatus(f"Dependency installation failed: {e}")
            return

                
        # Install dependencies if the requirements file is present
        if os.path.exists(f"{dest_dir}/requirements.txt"):
            logger.info("Installing dependencies from requirements.txt...")
            self.model.unit.status = ops.MaintenanceStatus("Installing pip dependencies...")
            try:
                run(["pip3", "install", "-r", f"{dest_dir}/requirements.txt"], check=True)
                logger.info("Dependencies installed successfully.")
            except Exception as e:
                logger.error(f"Failed to install dependencies: {e}")
                self.model.unit.status = ops.BlockedStatus(f"Dependency installation failed: {e}")
                return

        try:
            # Generate the environment file
            self.model.unit.status = ops.MaintenanceStatus("Generating environment file...")
            logger.info("Generating environment file...")
            FileManager.generate_environment_file()
            logger.info("Environment file generated successfully.")

            # Generate the service file
            self.model.unit.status = ops.MaintenanceStatus("Generating service file...")
            logger.info("Generating service file...")
            FileManager.generate_service_file(config)
            logger.info("Service file generated successfully.")

            # Set the workload version
            logger.info("Setting workload version...")
            self.unit.set_workload_version(config.get("release_tag"))
            logger.info("Workload version set successfully.")

            # Start the service
            self.service_manager.start_service()

            # Update the status
            self.model.unit.status = ops.ActiveStatus("Running")
            logger.info("Collector service refreshed successfully.")
        except Exception as e:
            logger.error(f"Failed to refresh collector service: {e}")
            self.model.unit.status = ops.BlockedStatus(f"Service refresh failed: {e}")
            return

if __name__ == "__main__":  # pragma: nocover
    ops.main(CollectorCharm)  # type: ignore
