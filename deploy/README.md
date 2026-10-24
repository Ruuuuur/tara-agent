# 部署与维护

当前本地开发不放置科学数据集，通过 SSH 隧道连接校内数据服务，步骤见[根目录 README](../README.md)。服务器数据服务的启动、更新和新增数据见[README 第 3 节](../README.md#3-服务器启动更新与新增数据)。

本文说明服务器上已部署网站的 Docker 运维，以及仓库完整部署模板的适用范围。服务器命令使用 Bash，真实目录、地址、账号及凭据不写入文档。

## 1. 管理服务器上已部署的网站

进入维护者确认的当前部署目录（包含实际使用的 `compose.yaml` 和 `.env`）：

```bash
cd '<当前网站部署目录>'
# 查看运行状态。
docker compose --env-file .env -f compose.yaml ps
# 启动或恢复服务，复用已有镜像和数据。
docker compose --env-file .env -f compose.yaml up -d --wait
# 查看后端最近日志。
docker compose --env-file .env -f compose.yaml logs --tail 100 backend
# 停止容器，保留数据卷。
docker compose --env-file .env -f compose.yaml down
```

文件名和服务名以实际部署配置为准。不要混用不同部署目录、Compose 项目名或数据卷；当前服务器部署不等同于仓库的 `compose.production.yaml` 模板。

网站运行与供本地开发使用的独立数据服务分别管理：停止网站容器不等于停止独立数据服务。修改前确认本次操作针对哪一个服务。

## 2. 更新网站

1. 保留当前可用发布版本，备份数据库及私有部署配置。
2. 准备新发布包和对应镜像；离线服务器使用配套镜像包，不依赖在线拉取或现场构建。
3. 核对新版本的环境变量、数据挂载和数据库迁移，保持原 Compose 项目名及数据卷。沿用已有部署配置中的镜像更新方式。
4. 在当前部署目录执行启动命令应用新镜像或配置：

```bash
docker compose --env-file .env -f compose.yaml up -d --wait
docker compose --env-file .env -f compose.yaml ps
docker compose --env-file .env -f compose.yaml logs --tail 100 backend
```

通过实际网站地址访问 `/api/v1/ready`，HTTP 200 表示后端就绪；再验证登录、真实科学问题、刷新后会话和链路恢复。就绪检查不代表模型调用或全部科学功能已验收。

科学代码、计算依赖或数据版本变化时，还需按根目录 README 更新独立数据服务并重启本机开发后端。更新可能短暂停机；数据库结构有变化时，回滚前确认旧代码与迁移后的数据库兼容，不能只替换旧镜像。

### 2.1 修复功能分析参考资料缺失

报错 `Error executing tool function_study: 未准备论文功能参考资料` 表示实际计算服务未读到 `TARA_MATOU_DATA_DIR/paper_task2/manifest.json`。MATOU 量化数据已接入、网站 `/ready` 返回 200，均不证明这份功能辅助资料已经准备。它提供功能名称、合并规则所用描述、海区/环境信息及明确区分的作者参考表，不是要用参考答案代替当前数据。

1. 确认网站是直接读取本机 MATOU，还是连接独立数据服务。远程模式在数据服务所在主机修复，本地模式在网站后端的数据主机修复；记录真实 MATOU 派生目录和容器挂载位置，不根据开发机路径猜测。
2. 将新版本后端代码放入独立发布目录。进入含 `pyproject.toml` 的后端目录，使用已有锁定环境，在 Bash 执行：

```bash
export TARA_MATOU_DATA_DIR='<实际计算服务使用的MATOU派生目录>'
uv run --locked python deploy/prepare_function_reference.py --matou-dir "$TARA_MATOU_DATA_DIR" --check
# 仅在首次缺少资料时执行；已有完整包核验后复用，损坏包拒绝覆盖。
uv run --locked python deploy/prepare_function_reference.py --matou-dir "$TARA_MATOU_DATA_DIR" --download
```

离线主机可使用已经核验的公开原文件配合 `--source-dir`，或由维护者传入完整资料包，再运行 `--check`。不要只复制 `manifest.json`。已有 LHC 缓存必须与当前 MATOU 清单摘要一致。

3. 保证主机生成的 `paper_task2` 被挂载到计算进程实际的 MATOU 目录中；容器只读挂载无需改成可写。先在测试端口启动新版本验证。远程模式同步两端科学代码、锁定依赖，再重启数据服务及网站后端，保持现有数据库和数据卷。
4. 在实际计算容器中也运行 `python deploy/prepare_function_reference.py --matou-dir '<容器内MATOU目录>' --check`。网站健康响应的 `matou.paper_reference_ready` 应为 `true`，再运行 [后端独立功能验收](../backend/README.md#论文图9图10功能对照)，最后新建对话询问“列出硅藻转录信号最高的 Top 100 功能，合并相关功能类别并报告相对贡献、样本覆盖和归一化方式”，确认结果、来源和完成状态。LHC 等项目未满足前提时仍须显示未完成。

本次代码在启动时校验参考包，有 MATOU 但没有参考包时不会注册 `function_study`，其他工具保留。合并 PR 不会把服务器资料自动补齐；只有完成准备、挂载、重启和真实问题验收，才算公网修复完成。

## 3. 备份与停止

需备份：数据库、私有 `.env` 和部署配置、独立保存的科学数据及版本清单。配置和备份含敏感信息，不提交 Git。

在当前部署目录生成数据库备份，文件名每次使用不同时间戳：

```bash
# 使用数据库容器内实际配置的账号和库名。
docker compose --env-file .env -f compose.yaml exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc -f /tmp/tara-agent.dump'
docker compose --env-file .env -f compose.yaml cp postgres:/tmp/tara-agent.dump "./postgres-$(date +%Y%m%d-%H%M%S).dump"
```

将备份复制到独立存储，并在独立测试数据库验证恢复。重建容器通常保留数据卷，但不能代替备份。不要使用 `down -v`，它会删除该部署的数据卷。删除旧发布包或备份前，确认当前服务没有引用它且不再需要回滚或恢复。

## 4. 仓库完整部署模板

仓库的 `compose.production.yaml` 用于**持有核心科学数据的部署主机**，前后端使用正式构建。当前模板直接挂载原始数据，启动时运行 `tara-data`；它尚未提供无本机数据的远程数据服务部署配置，也未配置 MATOU 挂载。本地开发连接校内数据服务时，使用根目录 README 的流程。

### 4.1 首次配置

需要 Docker 和 Docker Compose。在项目根目录创建配置；已有配置时不要覆盖：

```bash
cp deploy/.env.example deploy/.env
```

Windows PowerShell 对应命令为 `Copy-Item deploy/.env.example deploy/.env`。

编辑 `deploy/.env`：

- 设置 `POSTGRES_PASSWORD`、`DEEPSEEK_API_KEY`。
- 将 `TARA_SOURCE_DATA_DIR` 指向该部署主机的核心原始数据目录，包含 `context_general.tsv`、`context_stat.tsv`、`TARA-Oceans_18S-V4_dada2_table.tsv`、`TARA-Oceans_18S-V9_dada2_table.tsv`。这不是要求开发者在本机下载数据。
- 其余默认值只用于回环地址上的部署测试，网站为 `http://localhost:8080`。

原始数据只读挂载，不打入镜像。数据库密码由启动程序组装为连接地址，无需另外手填。

### 4.2 构建与启动

在项目根目录执行；该方式需要访问镜像和依赖仓库，离线环境使用维护者准备的发布包：

```bash
docker compose --env-file deploy/.env -f compose.production.yaml up -d --build --wait --wait-timeout 300
```

启动顺序：数据库就绪 → 后端配置校验、迁移及核心数据预处理 → 前后端健康检查 → 网站入口就绪。数据和处理版本未变时复用已校验的产物，失败时不通过就绪检查。

后续启动、日志和停止使用同一组 `--env-file`、`-f` 参数，分别执行 `up -d --wait`、`logs --tail 100 backend` 和 `down`。代码更新需重新构建镜像；原始数据或预处理代码变化时先停止应用，再更新并启动。

### 4.3 保存位置与正式对外部署

| 内容 | 模板保存位置 |
| --- | --- |
| 核心原始数据 | `TARA_SOURCE_DATA_DIR` 指定的主机目录 |
| 用户、会话、消息、分析链路 | Compose 的 `postgres_data` 卷 |
| 核心派生数据 | Compose 的 `processed_data` 卷 |
| Caddy 证书与配置状态 | Compose 的 `caddy_data`、`caddy_config` 卷 |

卷的实际名称取决于 Compose 项目名，不将模板卷名当作服务器现有卷名。服务器磁盘故障仍会导致数据丢失，需独立备份。

正式对外部署时设置生产环境、真实域名与 HTTPS，在 `deploy/.env` 配置：

```dotenv
TARA_ENVIRONMENT=production
TARA_SITE_ADDRESS=你的域名
TARA_PUBLIC_ORIGIN=https://你的域名
TARA_BIND_ADDRESS=0.0.0.0
TARA_HTTP_PORT=80
TARA_HTTPS_PORT=443
```

同时将 Compose 后端配置中的 `TARA_AUTH_GUEST_LOGIN_ENABLED` 改为 `"false"`；当前模板默认开启共享游客入口。域名解析及网络需支持网站访问和证书申请，生产登录依赖 HTTPS。完成数据库恢复演练、权限和真实分析验收后再开放使用。

## 自动启动预热

Docker 服务已设置开机启动且容器采用 `restart: unless-stopped` 时，后端每次启动会重新执行预热。生产模板默认 `TARA_STARTUP_WARMUP_ENABLED=true`，只读预热数据库连接、认证/会话查询、少量样本与V4/V9计算和问题推荐，不调用模型或产生产品记录。预热默认最多30秒，失败记录警告后继续启动；数据库不可用仍按原启动规则处理。通过 `Startup warmup completed` 日志确认成功，可用 `TARA_STARTUP_WARMUP_ENABLED=false` 关闭。预热降低冷启动延迟，不替代将大型镜像构建与在线服务错峰或隔离。
