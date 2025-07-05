#!/bin/bash

echo "Setting up configuration files for NachonekoBot-V2 Docker deployment..."

# Create conf_dir if it doesn't exist
mkdir -p conf_dir
echo ""

# Copy .env if it doesn't exist
if [ ! -f .env ]; then
    if [ -f .env.exp ]; then
        echo "Copying .env.exp to .env..."
        cp .env.exp .env
    else
        echo "WARNING: .env.exp not found. Please create .env manually."
    fi
else
    echo ".env already exists. Skipping..."
fi
echo ""

# Copy config.yaml if it doesn't exist
if [ ! -f conf_dir/config.yaml ]; then
    if [ -f conf_dir/config.yaml.exp ]; then
        echo "Copying config.yaml.exp to config.yaml..."
        cp conf_dir/config.yaml.exp conf_dir/config.yaml
    else
        echo "WARNING: conf_dir/config.yaml.exp not found. Please create conf_dir/config.yaml manually."
    fi
else
    echo "conf_dir/config.yaml already exists. Skipping..."
fi
echo ""

# Copy settings.toml if it doesn't exist
if [ ! -f conf_dir/settings.toml ]; then
    if [ -f conf_dir/settings.toml.example ]; then
        echo "Copying settings.toml.example to settings.toml..."
        cp conf_dir/settings.toml.example conf_dir/settings.toml
    else
        echo "WARNING: conf_dir/settings.toml.example not found. Please create conf_dir/settings.toml manually."
    fi
else
    echo "conf_dir/settings.toml already exists. Skipping..."
fi
echo ""


echo "Configuration setup complete."
echo ""
echo "IMPORTANT: Please edit the configuration files to add your specific settings:"
echo "- .env: Telegram bot token and proxy settings"
echo "- conf_dir/config.yaml: Main configuration"
echo "- conf_dir/settings.toml: Dynaconf settings"
echo ""
echo "After configuring, you can run 'docker-compose up -d' to start the application."
echo ""

# Make the script executable
chmod +x setup_docker_config.sh
