# HAProxy Collector

The HAProxy Collector is a Python package for collecting, parsing, and storing data from HAProxy instances. It is designed for integration with database systems and supports advanced HAProxy configurations, including backend switching and ACLs.

## Features

- Collects HAProxy configuration and runtime data via the HAProxy API
- Maps domains to backend server IPs using backend switching rules and ACLs
- Stores collected data in a database
- Modular and extensible codebase

## Requirements

- Python 3.8 or newer
- See `requirements.txt` for dependencies

## Installation

### 1. Set up a Python environment (recommended)

```sh
python -m venv venv
source venv/bin/activate
```

### 2. Build and install the package

```sh
pip install .
```

Or, to build a wheel:

```sh
pip install build
python -m build
pip install dist/haproxy_collector-*.whl
```

## Usage

Set the following environment variables before running the collector:

- `HAPROXY_NAME` or `HAPROXY_ID`: The name or ID of the HAProxy instance in your database
- `HAPROXY_URL`: The base URL of the HAProxy API
- `HAPROXY_USERNAME` and `HAPROXY_PASSWORD`: API credentials
- `DB_URL`: The database connection URL (required by `DatabaseManager`)
- `OWNER_ID`: The owner ID for database records

Then run the collector:

```sh
python haproxy_collector/haproxy_collector.py
```

## Project Structure

- `haproxy_collector/haproxy_collector.py`: Main entry point
- `haproxy_collector/haproxy_service.py`: Logic for fetching and mapping HAProxy data
- `haproxy_collector/haproxy_api_client.py`: HTTP client for the HAProxy API
- `haproxy_collector/haproxy_data_parser.py`: Parsers for HAProxy API responses
- `haproxy_collector/database_manager.py`: Database connection and management
- `requirements.txt`: Python dependencies
- `pyproject.toml`: Build and packaging configuration

## Development

- Update dependencies in `pyproject.toml` and `requirements.txt` as needed.
- Run tests and scripts locally using:
  ```sh
  python haproxy_collector/haproxy_collector.py
  ```
- For development installs (editable mode):
  ```sh
  pip install -e .
  ```
- Ensure your environment variables are set for local development and testing.

## Deployment

- Build the package:
  ```sh
  python -m build
  ```
- Install the built wheel in your deployment environment:
  ```sh
  pip install dist/haproxy_collector-*.whl
  ```
- Set all required environment variables (`HAPROXY_NAME`/`HAPROXY_ID`, `HAPROXY_URL`, `HAPROXY_USERNAME`, `HAPROXY_PASSWORD`, `DB_URL`, `OWNER_ID`).
- Run the collector as a module or script:
  ```sh
  python -m haproxy-collector
  # or
  python haproxy_collector/haproxy_collector.py
  ```

## License

MIT License
