#!/usr/bin/env python3
"""
This script is used to collect HAProxy data from various sources.
Due to the ALOHA project, it's a bit of a moving target, but since the
modules for the old methods were already extant from an old prototype,
I decided to add them in the meantime.
"""
import asyncio
from os import environ

from haproxy_collector.database_manager import DatabaseManager
from haproxy_collector.haproxy_service import HAProxyService

async def main():
    dbm = DatabaseManager()
    entry_id = await dbm.connect()
    haproxy_name = environ.get("HAPROXY_NAME")
    haproxy_id = environ.get("HAPROXY_ID")
    haproxy_url = environ.get("HAPROXY_URL")
    haproxy_username = environ.get("HAPROXY_USERNAME")
    haproxy_password = environ.get("HAPROXY_PASSWORD")

    if not any([haproxy_name, haproxy_id]):
        raise ValueError("Please provide either HAPROXY_NAME or HAPROXY_ID.")
    
    if haproxy_name:
        haproxy_id = await dbm.db.execute(
            "SELECT id FROM haproxy WHERE name = :name LIMIT 1",
            {
                "name": haproxy_name,
            },
        )
    else:
        haproxy_id = await dbm.db.execute(
            "SELECT id FROM haproxy WHERE id = :id LIMIT 1",
            {"id": int(haproxy_id)}
        )

    if not haproxy_id:
        raise ValueError("Please add HAProxy to DB before running this script.")

    await dbm.db.execute("CALL setup_haproxy_temp_tables_v1()")

    haproxy_service = HAProxyService(haproxy_url, haproxy_username, haproxy_password)
    domain_to_ip = haproxy_service.get_domains_to_ips()

    await dbm.db.execute_many(
        "INSERT INTO temp_haproxy_map"
        "   (row_source, haproxy, domain, ip) VALUES"
        "   (:entry_id, :haproxy, :domain, :ip)",
        [
            {
                "entry_id": entry_id,
                "haproxy": haproxy_id,
                "domain": domain,
                "ip": ip
            }
            for domain, ip in domain_to_ip
        ]
    )
    await dbm.db.execute("CALL insert_haproxy_data_v1(:owner)", {"owner": dbm.owner_id})
    await dbm.commit()

def detect_type(haproxy_file):
    if "dynamic-update" in haproxy_file:
        return "aloha"
    elif "X-Destination-Backend" in haproxy_file:
        return "api-platform"
    else:
        return "plain"

if __name__ == "__main__":
    asyncio.run(main())