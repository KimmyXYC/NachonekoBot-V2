@echo off
echo Setting up configuration files for NachonekoBot-V2 Docker deployment...

if not exist conf_dir mkdir conf_dir
echo.

if not exist .env (
    if exist .env.exp (
        echo Copying .env.exp to .env...
        copy .env.exp .env
    ) else (
        echo WARNING: .env.exp not found. Please create .env manually.
    )
) else (
    echo .env already exists. Skipping...
)
echo.

if not exist conf_dir\config.yaml (
    if exist conf_dir\config.yaml.exp (
        echo Copying config.yaml.exp to config.yaml...
        copy conf_dir\config.yaml.exp conf_dir\config.yaml
    ) else (
        echo WARNING: conf_dir\config.yaml.exp not found. Please create conf_dir\config.yaml manually.
    )
) else (
    echo conf_dir\config.yaml already exists. Skipping...
)
echo.

if not exist conf_dir\settings.toml (
    if exist conf_dir\settings.toml.example (
        echo Copying settings.toml.example to settings.toml...
        copy conf_dir\settings.toml.example conf_dir\settings.toml
    ) else (
        echo WARNING: conf_dir\settings.toml.example not found. Please create conf_dir\settings.toml manually.
    )
) else (
    echo conf_dir\settings.toml already exists. Skipping...
)
echo.


echo Configuration setup complete.
echo.
echo IMPORTANT: Please edit the configuration files to add your specific settings:
echo - .env: Telegram bot token and proxy settings
echo - conf_dir\config.yaml: Main configuration
echo - conf_dir\settings.toml: Dynaconf settings
echo.
echo After configuring, you can run 'docker-compose up -d' to start the application.
echo.

pause
