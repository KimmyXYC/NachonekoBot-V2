# NachonekoBot-V2

![Ruff](https://github.com/KimmyXYC/NachonekoBot-V2/actions/workflows/ruff.yml/badge.svg)
![Docker Build](https://github.com/KimmyXYC/NachonekoBot-V2/actions/workflows/docker-build.yml/badge.svg)

## 描述

NachonekoBot 是一个多功能的 Telegram 机器人，具有各种实用和有趣的功能。它设计为易于部署和配置，同时支持标准 Python 安装和 Docker 部署。

## 功能特点

- 多语言支持
- 模块化插件系统
- PostgreSQL 数据库集成
- 使用 YAML 和 TOML 文件进行简单配置
- 支持 Docker 简化部署

## 安装

### 前提条件

- Python 3.11 或更高版本
- PostgreSQL 数据库（标准安装需要）
- Docker 和 Docker Compose（Docker 安装需要）

### 标准安装

1. 克隆仓库：
   ```bash
   git clone https://github.com/KimmyXYC/NachonekoBot-V2.git
   cd NachonekoBot-V2
   ```

2. 使用 PDM 安装依赖：
   ```bash
   pip install pdm
   pdm install
   ```

3. 设置 PostgreSQL：
   - 如果尚未安装，请安装 PostgreSQL
   - 为机器人创建一个数据库
   - 记下数据库连接详情（主机、端口、数据库名称、用户名、密码）

4. 设置配置文件：
   ```bash
   cp .env.exp .env  # Telegram 机器人令牌的配置文件
   cp conf_dir/config.yaml.exp conf_dir/config.yaml
   ```

5. 编辑配置文件，填入您自己的值：
   ```bash
   nano .env  # 编辑此配置文件以设置您的 Telegram 机器人令牌
   nano conf_dir/config.yaml  # 配置数据库连接和其他设置
   ```

   `.env` 文件包含以下配置选项：
   ```
   TELEGRAM_BOT_TOKEN=您的机器人令牌
   # TELEGRAM_BOT_PROXY_ADDRESS=socks5://127.0.0.1:7890
   ```
   - `TELEGRAM_BOT_TOKEN`：从 BotFather 获取的 Telegram 机器人令牌
   - `TELEGRAM_BOT_PROXY_ADDRESS`：（可选）连接到 Telegram API 的代理地址，如需使用请取消注释

6. 运行机器人：
   ```bash
   pdm run python main.py
   ```

### Docker 安装

#### 前提条件

- [Docker](https://docs.docker.com/get-docker/)
- [Docker Compose](https://docs.docker.com/compose/install/)

#### 配置

在运行应用程序之前，需要在 `conf_dir` 目录中设置配置文件：
- `config.yaml`：机器人的主要配置文件
- `settings.toml`：Dynaconf 的设置

提供了示例配置文件：
- `config.yaml.exp`：主要配置示例
- `settings.toml.example`：Dynaconf 设置示例

您可以复制并重命名这些文件：
```bash
cp .env.exp .env  # Telegram 机器人令牌的配置文件
cp conf_dir/config.yaml.exp conf_dir/config.yaml
cp conf_dir/settings.toml.example conf_dir/settings.toml
```

`.env` 文件包含以下配置选项：
```
TELEGRAM_BOT_TOKEN=您的机器人令牌
# TELEGRAM_BOT_PROXY_ADDRESS=socks5://127.0.0.1:7890
```
- `TELEGRAM_BOT_TOKEN`：从 BotFather 获取的 Telegram 机器人令牌
- `TELEGRAM_BOT_PROXY_ADDRESS`：（可选）连接到 Telegram API 的代理地址，如需使用请取消注释

至少需要在 `config.yaml` 中配置数据库连接：
```yaml
database:
  host: postgres
  port: 5432
  dbname: nachonekobot
  user: postgres
  password: postgres

  # 其他 Telegram 设置
```

#### 环境变量

您可以通过设置环境变量来自定义部署：
- `POSTGRES_USER`：PostgreSQL 用户名（默认：postgres）
- `POSTGRES_PASSWORD`：PostgreSQL 密码（默认：postgres）
- `POSTGRES_DB`：PostgreSQL 数据库名称（默认：nachonekobot）
- `DEBUG`：设置为 "true" 启用调试模式（默认：false）

#### 使用 Docker Compose 运行

1. 启动应用程序：
   ```bash
   docker-compose up -d
   ```

2. 查看日志：
   ```bash
   docker-compose logs -f app
   ```

3. 停止应用程序：
   ```bash
   docker-compose down
   ```

4. 停止应用程序并删除卷：
   ```bash
   docker-compose down -v
   ```

#### 数据持久化

以下数据将被持久化：
- PostgreSQL 数据：存储在 Docker 卷中
- 配置文件：从主机的 `conf_dir` 目录挂载
- 应用程序数据：存储在 `data` 目录中
- 日志：存储在 `run.log` 中

#### 故障排除

1. 如果应用程序无法连接到数据库，请检查：
   - PostgreSQL 容器是否正在运行：`docker-compose ps`
   - `config.yaml` 中的数据库凭据是否与环境变量匹配
   - 数据库初始化是否成功：`docker-compose logs postgres`

2. 如果机器人没有响应，请检查：
   - 应用程序日志：`docker-compose logs app`
   - 配置中的 Telegram 令牌
   - 网络连接

#### 安全注意事项

- 在生产环境中，切勿使用默认密码
- 考虑使用 Docker secrets 或安全的环境变量管理系统
- 如果暴露 PostgreSQL 端口 (5432)，请限制访问

## 贡献

欢迎贡献！请随时提交 Pull Request。

## 许可证

本项目采用 MIT 许可证 — 详情请参阅 LICENSE.md 文件
