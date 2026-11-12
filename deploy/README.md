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
## 原始 reads 试点

### 范围和状态

1. **小规模流程验证**：一个明确对应的 Tara 样本，各技术 Run 抽取少量双端 reads，使用
   LHC（PF00504）候选参考，验证质控、比对、计数和网页工具。
   这能检验输入输出与候选检测，不提供完整 Top100 稳定性结论。
2. **同文库功能谱敏感性分析**：使用完整版本化参考目录、类群基因全集和同文库已发布数据，
   比较功能排名、份额和共同已观测家族的 Spearman。必须说明重算算法、抽样和质控差异。
3. **跨环境科学结论稳定性**：仍需多个独立样本、具有代表性的抽样及匹配的方法和分母，
   重新检验原有统计关系。当前工具未实现自动完成这一层验证。

当前验证记录：已按 Supplementary Data 8 的准确 Run 编号下载一个采样背景的
MetaG/MetaT头部试点数据，保留配对及SHA256；完成相关软件测试。
独立工作镜像已构建，fastp 0.23.2/Bowtie2 2.5.0 的真实小样本流程已完成；
隔离API的自然语言问答也已验证。尚未切换公网生产后端，浏览器界面仍需人工验收。
原始归档大小约 MetaG 28.53 GiB、MetaT 41.48 GiB，不应在小型网站服务器直接下载全部。
2核/约4GiB内存的网站服务器先采用候选参考和小样本，并将工作容器限为1核、1.5GiB；
预检不保证生信任务成功，内存不足时停止任务或转移计算环境，不扩大在线进程配额。

真实试跑记录：`lhc-metag-head-10000-v3`与`lhc-metat-head-10000-v3`。
四个Run分别为ERR868465、ERR868424、ERR1740118、ERR1740132，
质控后reads分别为17,832、18,732、17,842、17,700，初始主比对分别为1、6、5、6，
通过MAPQ/identity/coverage全部规则的候选比对均为0。结果不是“功能不存在”的证据。
只保留头部小抽样和单功能候选参考，不能据此判断原有排名或跨环境结论稳定。
初次fastp默认重复率评估在内存限额下终止，失败目录保留；后续关闭该报告项。
未核验接头序列前关闭自动剪切，保留质量/长度过滤；真实参数与软件版本均写入产物。

### 数据来源

- [MATOU原始论文](https://www.nature.com/articles/s41467-017-02342-1)：Supplementary Data 8
  中N列Sample Code、B列BioSamples、C列Type和L列Run accession是映射依据。
- [ENA MetaG项目](https://www.ebi.ac.uk/ena/browser/view/PRJEB4352) 与
  [ENA MetaT项目](https://www.ebi.ac.uk/ena/browser/view/PRJEB6609)。按具体Run验证实验类型、
  双端布局和BioSample，不从同一BioSample的所有实验中任意挑选。
- [fastp](https://github.com/OpenGene/fastp)、
  [Bowtie2](https://bowtie-bio.sourceforge.net/bowtie2/manual.shtml)、
  [SAM规范](https://samtools.github.io/hts-specs/SAMv1.pdf)：当前独立重算方法的工具与格式依据。

### 下载清单与小样本

以下在具有项目Python环境的机器执行；所有路径为管理员明确指定的独立目录。

```bash
cd backend
uv run tara-reads plan --supplement /path/to/supplementary-data-8.xlsx \
  --samples 100DCM1GGMM11 --output /pilot/metag.json
uv run tara-reads plan --supplement /path/to/supplementary-data-8.xlsx \
  --samples 100DCM1GGMM14 --output /pilot/metat.json
uv run tara-reads sample --manifest /pilot/metag.json --pairs 10000 \
  --directory /pilot/sampled-metag --output /pilot/metag-head-10000.json
uv run tara-reads sample --manifest /pilot/metat.json --pairs 10000 \
  --directory /pilot/sampled-metat --output /pilot/metat-head-10000.json
```

`sample`从每个Run的HTTPS gzip流抽取完整FASTQ记录，逐对核对编号。仅下载所需前部，
保存新文件自己的MD5/SHA256，**未核验完整归档的MD5，不称随机抽样**。
完整下载另用`download --manifest /pilot/metag.json --directory /pilot/raw --max-gb 30`，
完成后才按ENA文件大小与MD5核验；中断的`.partial`文件不视为有效文件，首版不自动覆盖或续传。

### 独立工作容器

先确认当前网站部署目录、MATOU缓存位置和镜像构建资源。下列操作不重启网站、不运行迁移。
构建较重时应在独立构建机生成镜像后导入，避免与在线服务抢资源。
默认使用Debian官方HTTPS源；国内连接较慢时，可在构建参数中指定
`--build-arg DEBIAN_MIRROR=https://mirrors.tuna.tsinghua.edu.cn/debian`。
只调整试验镜像的软件源，仍使用Debian签名验证，不修改主机或在线容器的软件源。

```bash
# 在包含本分支代码的仓库根目录构建独立镜像；BACKEND_IMAGE取当前核验的后端镜像。
docker build --build-arg TARA_BACKEND_IMAGE="$BACKEND_IMAGE" \
  -f deploy/Dockerfile.reads -t tara-reads-pilot:dev .
```

把试点资料解压到`/home/ubuntu/tara-read-pilot`，包含候选FASTA及来源JSON、两份
抽样输入清单、8个FASTQ和与现有MATOU清单匹配的`gene_ids.tsv`。
先设置`MATOU_DIR`为**当前服务实际使用**的MATOU处理目录，不凭本地旧路径猜测。

```bash
# 此变量必须换成核验过的实际服务器路径。
MATOU_DIR=/absolute/path/to/current/matou
PILOT_DIR="$HOME/tara-read-pilot"
mkdir -p "$PILOT_DIR/jobs"

docker run --rm --network none --read-only --tmpfs /tmp:size=64m \
  --cpus=1 --memory=1536m --memory-swap=1536m --user "$(id -u):$(id -g)" \
  -v "$PILOT_DIR:/pilot" tara-reads-pilot:dev \
  index --reference /pilot/LHC-candidate.fna --scope candidate_subset \
  --output /pilot/lhc-index --threads 1 --hours 2

docker run --rm --network none --read-only --tmpfs /tmp:size=64m \
  --cpus=1 --memory=1536m --memory-swap=1536m --user "$(id -u):$(id -g)" \
  -v "$PILOT_DIR:/pilot" -v "$MATOU_DIR:/matou:ro" tara-reads-pilot:dev \
  quantify --manifest /pilot/plans/metat-head-10000.json --fastq /pilot/sampled-metat \
  --index /pilot/lhc-index --matou-dir /matou --gene-ids /pilot/gene_ids.tsv \
  --jobs /pilot/jobs --job-id lhc-metat-head-10000 --threads 1 --hours 2
```

DNA试点将输入改为`plans/metag-head-10000.json`、`sampled-metag`及独立的
`lhc-metag-head-10000`任务编号。一次处理一个文库的全部已列技术runs，DNA与RNA不混算。
输出目录不能复用；失败时保留日志，使用新任务编号重跑，只有最后生成的`result.json`
代表流程完成。结果、输入清单及基因谱摘要在读取时重新校验，基线变更后拒绝静默混用。

候选参考可从已有核验序列导出：
`uv run tara-reads reference --matou-dir /matou --pfam PF00504 --output /pilot/LHC-candidate.fna`。
完整参考索引只用于资源充足且核验过完整目录的环境；首版不提供原始reads重新组装。

### 网页接入与验收

先在隔离发布目录和测试端口运行新版后端。设置`TARA_READ_JOBS_DIR=/data/read-jobs`，
把服务器`jobs`目录只读挂载到该路径；`deploy/compose.reads.yaml`是附加配置示例，
使用前核对现有生产Compose文件，**不能用仓库示例直接覆盖当前部署**。
未设置此配置时，现有工具和分析行为不变。

1. 先独立检查`tara-reads`输出、fastp报告、Bowtie2日志、两端记录和实际版本。
2. 网页问：“有哪些已经完成的原始reads重算试点？列出任务编号、文库和实验类型。”
   应调用`raw_read_study`，`query={}`，只列出真实完成任务。
3. 问：“查看lhc-metat-head-10000的质控及候选LHC检测结果，说明能否据此判断功能排名稳定。”
   候选参考应返回逐Run统计，并明确`not_comparable_reference_subset`，不得声称完整排名稳定。
4. 在完整参考结果就绪后问：“比较指定重算任务与同一文库已发布的Top20功能，报告重合和份额差异。”
   应返回实际比较表、散点、样本范围与限制，不能使用论文预期值作为计算输入。
5. 刷新会话并检查同一Trace的工具输入、结果、来源和警告；未知任务、改动过的产物或基线
   应明确失败，不生成科学结论。未上线或无任务时不把功能可用当作计算已完成。

### GitHub合并

数据包单独上传，Git只合并代码、测试和说明。开发分支为`codex/raw-reads-pilot`，
基于`Ruuuuur/tara-agent`当前核验的主分支。没有该仓库直接写权限时，推送到自己的fork后
向`Ruuuuur/tara-agent:main`创建PR；先保持草稿，待Docker、生信端到端和隔离网页验收后再请求合并。
合并代码不会自动上传数据、构建镜像或启用网站上的工具，这些是独立部署步骤。

## 外部 MCP 服务

在已有生产 Compose 中叠加 `deploy/compose.mcp.yaml`，设置 `TARA_MCP_IMAGE`（含本次已验证代码的后端镜像）、`TARA_MCP_PUBLIC_URL`（HTTPS 地址，路径必须为 `/mcp`）、`TARA_MCP_PROCESSED_DIR` 和 `TARA_MCP_AUTH_DIR`。保护令牌目录，令其由容器运行 UID 读取；挂载整个目录保证管理命令原子替换注册表后立即生效。不要把认证文件放进现有 Caddy 的配置挂载目录。先离线签发访问令牌，再启动服务：

```bash
docker compose -f compose.yaml -f compose.mcp.yaml up -d --no-deps mcp
```

单进程限制是并发与速率计数的前提，不可直接增加 workers 或复制容器。独立容器限制 768 MiB、0.75 CPU；核心数据只读，无模型/数据库 env_file，不对宿主机发布额外端口。健康失败可观察；进程退出自动重启，Docker 重启后恢复服务。此首批配置仅挂载核心数据，不给外部客户端任意文件、Shell 或 SQL 能力。

在同一 Docker 网络中的 Caddy 公网站点，放在现有 catch-all handle 之前，并保持所有其他站点配置：

```caddyfile
handle /mcp {
    request_body { max_size 64KiB }
    reverse_proxy mcp:8012
}
```

先 `caddy validate`，再热加载。不要开放公网 `/healthz`，不要启用记录 Authorization 的访问日志。保存原 Compose/Caddyfile 及镜像版本以供回退；移除 `/mcp` 路由并停用 `mcp` 服务即可撤回，原网站和数据不变。凭据注册表属于访问控制配置，应备份在受保护位置；处理后科学数据沿用原备份，不为 MCP 再复制一份。

验收必须从服务器外通过有效 TLS 连接，检查无令牌/错误/过期/撤销 401、非法来源和超大请求拒绝、HTTP 429 及恢复、工具发现和来源资源，并比较 MCP 返回与同版本分析服务的完整科学结果。公网验收不调用外部 LLM，不把真实数据额外发送给模型供应商。具体接入边界见根目录 MCP接入说明.md。
