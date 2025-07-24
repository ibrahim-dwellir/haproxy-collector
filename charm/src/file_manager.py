#!/usr/bin/env python3
# Copyright 2024 Adrian Wennström
# See LICENSE file for licensing details.

"""File and environment management for the collector charm."""

import json
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class FileManager:
    """Handles file operations for the collector charm."""
    
    CONFIG_DIR = ".collector"
    CONFIG_FILE = ".collector/config.json"
    DB_CONFIG_FILE = ".collector/config_db.json"
    
    @classmethod
    def store_config(cls, config: Dict[str, Any]) -> None:
        """Store the configuration in a file.
        
        Args:
            config: Configuration dictionary to store
        """
        from subprocess import run
        
        # Store configuration in .collector folder
        run(["mkdir", "-p", cls.CONFIG_DIR])
        with open(cls.CONFIG_FILE, "w") as config_file:
            config_file.write(json.dumps(config))
    
    @classmethod
    def read_config(cls) -> Dict[str, Any]:
        """Read the configuration from a file.
        
        Returns:
            Configuration dictionary, empty dict if file not found
        """
        try:
            with open(cls.CONFIG_FILE, "r") as config_file:
                return json.loads(config_file.read())
        except FileNotFoundError:
            logger.error("Configuration file not found.")
            return {}
        except json.JSONDecodeError:
            logger.error("Error decoding configuration file.")
            return {}
    
    @classmethod
    def store_db_config(cls, config: Dict[str, Any]) -> None:
        """Store the database configuration in a file.
        
        Args:
            config: DB configuration dictionary to store
        """
        from subprocess import run
        
        # Store configuration in .collector folder
        run(["mkdir", "-p", cls.CONFIG_DIR])
        with open(cls.DB_CONFIG_FILE, "w") as config_file:
            config_file.write(json.dumps(config))
    
    @classmethod
    def read_db_config(cls) -> Dict[str, Any]:
        """Read the database configuration from a file.
        
        Returns:
            DB configuration dictionary, empty dict if file not found
        """
        try:
            with open(cls.DB_CONFIG_FILE, "r") as config_file:
                return json.loads(config_file.read())
        except FileNotFoundError:
            logger.error("DB configuration file not found.")
            return {}
        except json.JSONDecodeError:
            logger.error("Error decoding db configuration file.")
            return {}
        
    @classmethod
    def get_service_args(cls) -> None:
        """Register args for the collector service.
        
        Args:
            config: Configuration dictionary containing HAProxy credentials
        """
        config = cls.read_config() # Read main config
        config.update(cls.read_db_config()) # Merge DB config into main config

        args = f"HAPROXY_URL={config['haproxy_url']} HAPROXY_USERNAME={config['haproxy_username']} HAPROXY_PASSWORD={config['haproxy_password']}"
        # Write additional configurations if they exist
        if "owner_id" in config and "db_url" in config:
            args += f" OWNER_ID={config['owner_id']} DB_URL={config['db_url']}"
        return args
