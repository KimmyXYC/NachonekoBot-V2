# NachonekoBot-V2

![Ruff](https://github.com/KimmyXYC/NachonekoBot-V2/actions/workflows/ruff.yml/badge.svg)
![Docker Build](https://github.com/KimmyXYC/NachonekoBot-V2/actions/workflows/docker-build.yml/badge.svg)

## Description

NachonekoBot is a multifunctional Telegram Bot with various useful and interesting features. It's designed to be easy to deploy and configure, with support for both standard Python installation and Docker deployment.

## Features

- Multi-language support
- Modular plugin system
- PostgreSQL database integration
- Easy configuration with YAML and TOML files
- Docker support for simple deployment

## Installation

### Prerequisites

- Python 3.11 or higher
- PostgreSQL database (for standard installation)
- Docker and Docker Compose (for Docker installation)

### Standard Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/KimmyXYC/NachonekoBot-V2.git
   cd NachonekoBot-V2
   ```

2. Install dependencies using PDM:
   ```bash
   pip install pdm
   pdm install
   ```

3. Set up PostgreSQL:
   - Install PostgreSQL if not already installed
   - Create a database for the bot
   - Note the database connection details (host, port, database name, username, password)

4. Set up configuration files:
   ```bash
   cp .env.exp .env  # Configuration file for Telegram bot token
   cp conf_dir/config.yaml.exp conf_dir/config.yaml
   ```

5. Edit the configuration files with your own values:
   ```bash
   nano .env  # Edit this configuration file to set your Telegram bot token
   nano conf_dir/config.yaml  # Configure database connection and other settings
   ```

   The `.env` file contains the following configuration options:
   ```
   TELEGRAM_BOT_TOKEN=your_bot_token_here
   # TELEGRAM_BOT_PROXY_ADDRESS=socks5://127.0.0.1:7890
   ```
   - `TELEGRAM_BOT_TOKEN`: Your Telegram bot token obtained from BotFather
   - `TELEGRAM_BOT_PROXY_ADDRESS`: (Optional) Proxy address for connecting to Telegram API, uncomment if needed

6. Run the bot:
   ```bash
   pdm run python main.py
   ```

### Docker Installation

#### Prerequisites

- [Docker](https://docs.docker.com/get-docker/)
- [Docker Compose](https://docs.docker.com/compose/install/)

#### Configuration

Before running the application, set up the configuration files in the `conf_dir` directory:
- `config.yaml`: Main configuration file for the bot
- `settings.toml`: Settings for Dynaconf

Example configuration files are provided:
- `config.yaml.exp`: Example main configuration
- `settings.toml.example`: Example Dynaconf settings

You can copy and rename these files:
```bash
cp .env.exp .env  # Configuration file for Telegram bot token
cp conf_dir/config.yaml.exp conf_dir/config.yaml
cp conf_dir/settings.toml.example conf_dir/settings.toml
```

The `.env` file contains the following configuration options:
```
TELEGRAM_BOT_TOKEN=your_bot_token_here
# TELEGRAM_BOT_PROXY_ADDRESS=socks5://127.0.0.1:7890
```
- `TELEGRAM_BOT_TOKEN`: Your Telegram bot token obtained from BotFather
- `TELEGRAM_BOT_PROXY_ADDRESS`: (Optional) Proxy address for connecting to Telegram API, uncomment if needed

At minimum, configure the database connectionn in `config.yaml`:
```yaml
database:
  host: postgres
  port: 5432
  dbname: nachonekobot
  user: postgres
  password: postgres

  # Other Telegram settings
```

#### Environment Variables

You can customize the deployment by setting environment variables:
- `POSTGRES_USER`: PostgreSQL username (default: postgres)
- `POSTGRES_PASSWORD`: PostgreSQL password (default: postgres)
- `POSTGRES_DB`: PostgreSQL database name (default: nachonekobot)
- `DEBUG`: Set to "true" to enable debug mode (default: false)

#### Running with Docker Compose

1. Start the application:
   ```bash
   docker-compose up -d
   ```

2. View logs:
   ```bash
   docker-compose logs -f app
   ```

3. Stop the application:
   ```bash
   docker-compose down
   ```

4. Stop the application and remove volumes:
   ```bash
   docker-compose down -v
   ```

#### Data Persistence

The following data is persisted:
- PostgreSQL data: Stored in a Docker volume
- Configuration files: Mounted from the host's `conf_dir` directory
- Application data: Stored in the `data` directory
- Logs: Stored in `run.log`

#### Troubleshooting

1. If the application fails to connect to the database, check:
   - PostgreSQL container is running: `docker-compose ps`
   - Database credentials in `config.yaml` match the environment variables
   - Database initialization was successful: `docker-compose logs postgres`

2. If the bot doesn't respond, check:
   - Application logs: `docker-compose logs app`
   - Telegram token in configuration
   - Network connectivity

#### Security Notes

- In production, never use default passwords
- Consider using Docker secrets or a secure environment variable management system
- Restrict access to the PostgreSQL port (5432) if exposed

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License — see the LICENSE.md file for details
