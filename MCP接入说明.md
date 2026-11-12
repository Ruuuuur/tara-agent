# Tara MCP 外部客户端接入

现有 `tara-mcp` 服务通过标准输入输出（stdio）提供只读科学工具。外部 AI 客户端负责启动这个进程，通过 MCP 发现 Schema 并调用工具；无需启动网站、PostgreSQL，也无需给 MCP 配置模型密钥。数据必须已在运行服务的主机准备好。MCP 复用同一批分析服务，不另写算法。

## 接入前准备

在持有数据的主机执行：

```bash
cd '<项目根目录>/backend'
uv sync --locked
uv run tara-mcp --help
```

`--processed-data-dir` 指向包含核心 `manifest.json` 和对应 generation 子目录的派生目录，不是原始 TSV 目录。仅开放当前已验收的核心能力时加 `--core-only`；这会显式忽略环境中的 MATOU 配置。

若同时提供 MATOU，去掉 `--core-only`，改加 `--matou-data-dir '<MATOU派生目录>'`。MATOU 工具沿用现有数据/资料包检查：`function_study` 仅在参考包完整时注册；序列、环境映射等前置条件缺失时明确失败或返回 blocked/partial，不伪造成功。数据启动失败时退出码为 2，原因写 stderr，stdout 仅传输协议。

## 配置外部 AI 客户端

适用于支持 `mcpServers` JSON 的客户端。复制 [本机示例](backend/examples/mcp/local.example.json)，替换两个绝对路径，再导入客户端的 MCP 设置：

```json
{
  "mcpServers": {
    "tara": {
      "command": "/ABSOLUTE/PATH/TO/backend/.venv/bin/tara-mcp",
      "args": ["--processed-data-dir", "/ABSOLUTE/PATH/TO/processed", "--core-only"]
    }
  }
}
```

Windows 使用 `.venv/Scripts/tara-mcp.exe`。客户端使用其他配置格式时，将同样的 command/args 填到对应字段即可。命令使用绝对路径，不依赖工作目录或交互终端激活的虚拟环境；也可使用虚拟环境 Python 加 `-m tara_agent.mcp` 启动。

数据在远程服务器时，使用 [SSH 示例](backend/examples/mcp/ssh.example.json)：本机配置 OpenSSH 别名 `tara-data-host` 和密钥认证，远端命令指向远端已安装的 `tara-mcp` 及数据目录。`ssh -T` 不分配伪终端；`BatchMode=yes` 在认证不可用时及时失败，避免 MCP 在密码提示处挂住。先在终端完成首次 SSH 主机指纹核验。远端 shell 启动文件不能向 stdout 打印欢迎语；远端路径有空格时须按远端 shell 规则引用。

已有 Docker 部署可把 SSH 的最后一个远端命令替换为：

```bash
docker compose -f /srv/tara-agent/compose.yaml exec -T backend tara-mcp --core-only
```

这会使用容器已配置的只读派生数据，需先将包含本次改动的后端版本部署到容器。不要使用 `-t`，不要把密码或 API Key 写进配置。SSH 接入继承主机权限；本方案无需另开公网 MCP 端口，也不把自有 HTTP 数据网关的 `/tools`、`/call` 冒充标准 MCP 接口。

## 已选择的核心能力

| 工具 | 用途及主要边界 |
| --- | --- |
| `find_samples` | 背景样本筛选和分页，返回 PANGAEA 样本 ID |
| `get_sample_info` | 一个准确 PANGAEA ID 的背景和环境信息 |
| `find_taxa` | 指定 V4/V9 的分类、ASV 和出现样本，分别分页 |
| `taxon_abundance` | 样本内类群 reads / 全部 reads；支持排序、站位和组成分析 |
| `diversity_analysis` | 未稀释抽样的观测 ASV 丰富度和 Shannon；读深影响比较 |
| `environment_association` | 一个类群与一个白名单环境变量的成对完整观测 Spearman 关联 |
| `community_analysis` | 独立标记的群落分布、多样性及可选环境分析；检查各 section 状态 |

V4/V9 始终独立，不合并读数；测序相对信号不等于细胞丰度或因果关系。外部客户端每次以 `tools/list` 返回的实际工具和 Schema 为准，不硬编码工具总数或假定 MATOU 总可用。简单查询不默认执行 NMDS 等重计算。

可直接对外部 AI 提问：

> 使用 Tara 工具查找表层样本，返回第一个样本的背景信息，并明确数据来源和缺失值。请先发现可用工具，沿用其真实返回的样本 ID。

或请求独立标记分析：

> 使用 Tara 工具计算 V9 中 Bacillariophyta 的样本内相对测序丰度，返回最高的五个样本，说明分母、警告和来源。不要将其解释为细胞丰度。

MCP 实际调用参数示例（除 `get_sample_info` 外，分析参数均放入 `query` 对象）：

```json
{"name":"taxon_abundance","arguments":{"query":{"marker":"v9","taxon":"Bacillariophyta","order_by":"relative_abundance","limit":5}}}
```

## 返回、错误和来源

- 成功：`isError=false`，`structuredContent` 保留分析服务原始结果 Schema，`content` 同时提供等价 JSON 文本，兼容只读文本的客户端。
- 科学限制：始终保留 `metadata.warnings`、`metadata.provenance`，包括源数据、有效筛选条件、纳入与排除数量。缺失值保留 null；`blocked`/`partial` 是科学流程状态，不得改成 completed。
- 版本目录：通过 `resources/list` 发现 `tara://data/catalog`，用 `resources/read` 读取核心 generation、处理管线、源文件/产物 SHA-256，以及可选 MATOU/研究资料版本。目录表示已配置资料；单次计算实际使用哪些资料，以其 provenance 为准。服务固定使用启动时加载的数据版本，发布新数据后重启 MCP 进程。
- 单次返回 `_meta["org.tara-agent/context"]` 给出工具名、契约版本、启动时固定的数据版本和目录 URI。失败再提供 `error.code/message/fields`；SDK 的 Python 客户端对应属性为 `result.meta`、`result.is_error`、`result.structured_content`。部分 AI 主机不向模型转发 `_meta`，错误文本也会带错误类型和字段位置。

| 错误类型 | 含义 |
| --- | --- |
| `invalid_arguments` | 参数缺失、越界、未知字段、非法枚举等；字段位置和约束来自现有 Pydantic 契约 |
| `unknown_tool` | 工具未开放；重新发现可用工具，不执行任意 Python/Shell/SQL |
| `not_found` | 请求的实体不存在，如未知 PANGAEA ID |
| `analysis_error` | 数据或分析前提不满足，保留领域层明确原因 |
| `internal_error` | 非预期内部失败；客户端收到通用说明，具体异常保留服务端日志 |

错误返回 `isError=true` 且不含成功科学结果。单次失败不会关闭 MCP 会话；错误参数修正后可继续调用。不在 MCP 层自动重试科学计算。

## 可重复验收

复制并改好一份可信的客户端配置，例如 `/tmp/tara-mcp.json`。在后端目录运行独立 SDK 客户端，命令会真实启动配置中的进程（可以是 SSH），发现工具、读取来源目录、调用工具、验证输出 Schema，并可保存完整 JSON 报告：

```bash
uv run python deploy/check_mcp.py --config /tmp/tara-mcp.json --output /tmp/tara-mcp-check.json
```

验证其他工具时增加 `--tool` 和 `--arguments`（JSON 字符串），例如：

```bash
uv run python deploy/check_mcp.py --config /tmp/tara-mcp.json --tool diversity_analysis --arguments '{"query":{"marker":"v9","limit":2}}'
```

真实子进程的协议兼容检查也已纳入自动测试：

```bash
uv run pytest tests/test_mcp.py tests/test_mcp_external.py
```

测试使用有明确预期的小型科学数据，比较所有七个核心工具在 V4/V9 下的完整结果、warning 和来源，另验证条件式 MATOU 工具、错误恢复、内部错误遮蔽，以及任意工作目录的模块/命令入口。大规模真实数据的性能、第三方 AI 主机界面和模型解释质量不由这组协议测试证明；使用对应配置和报告单独验收。

## 本次验收记录（2026-11-11）

- Ruff 通过，后端常规回归 564 项通过、9 项集成测试未纳入本机回归。
- 独立 MCP 验收及已有契约测试共 27 项通过，包含模块/控制台入口和经典握手兼容。
- 本机客户端经 SSH 在云端独立只读容器发现并调用七个核心工具；真实数据七工具 × V4/V9 的 14 项完整结果与直接科学函数逐项一致。为控制资源，计算型请求仅取各标记前三个样本，群落只验收分布和多样性，不宣称全数据重分析。
- 独立 DeepSeek 客户端从 MCP 发现工具后，自主连续调用 find_samples、get_sample_info 并给出回答。模型验收只使用人工夹具；真实数据未用于第三方模型联调，该尝试曾被自动审批以未明确授权数据外发为由拒绝。
- 真实数据验收代码运行于独立容器；正式网站服务和数据库未切换到本分支。本机/SSH 示例供目标 AI 主机导入，未擅自修改用户全局客户端配置。

## 公网 Streamable HTTP 接入

外部用户不必登录云服务器。维护者分别签发令牌，用户在支持自定义 HTTP 请求头的 MCP 客户端中配置 HTTPS `/mcp` 地址和 `Authorization: Bearer <令牌>`；模板见 `backend/examples/mcp/http.example.json`。不同客户端配置字段可能不同，不能直接把此模板用于所有客户端。令牌等同该用户的访问凭证，不贴到聊天、Git、截图或日志中。

此入口提供 MCP 工具发现、调用和来源资源，使用官方 SDK Streamable HTTP，无状态 JSON 响应；兼容现代发现和经典 initialize。当前不提供 OAuth 登录与动态客户端注册；仅接受 OAuth 的客户端暂不能直接连接，确定目标客户端后再增加经验证的授权方式。网页账号密码不能替代 MCP 令牌。

首批公网部署只挂载核心处理后数据，开放七个已验收核心查询/计算工具；MATOU、论文功能研究及 raw reads 不随此部署自动公开。可在后续资源评估与资料验收后，通过 `TARA_MCP_MATOU_DATA_DIR` 和只读挂载启用 MATOU 能力。原 stdio 服务继续支持可选 MATOU 与完成的 reads 任务查询，网站能力不受影响。

每个令牌默认有效 90 天，最多 365 天，每个身份每分钟 60 个 HTTP 请求（含发现和失败请求），同时至多一个 POST；实例总计至多两个 POST。忙时立即返回 HTTP 429 和 Retry-After，客户端稍后重试，不无限排队。单请求体 64 KiB，Host/Origin 验证由 MCP SDK 执行。缺失、错误、过期或已撤销令牌返回 401；损坏的凭据注册表返回 503 并拒绝访问。删除注册表内的令牌立即阻止其后续请求，已执行的计算不会被强制中断。

服务只保存令牌 SHA-256 摘要，不持久化明文。管理者在受保护目录依次执行管理命令，注册表和明文输出文件权限为 0600，目录为 0700。为不同外部用户签发不同 client_id，不共用一个令牌。

```bash
python -m tara_agent.mcp.tokens --registry /PRIVATE/tokens.json create alice --output /PRIVATE/alice.token --days 90
python -m tara_agent.mcp.tokens --registry /PRIVATE/tokens.json revoke alice
```

`/healthz` 仅用于容器健康检查，不代理到公网。MCP 不读取网站数据库或模型 API Key，也不产生网页会话历史；返回的 provenance 和来源资源仍须保留。容器内存不足可能终止该 MCP 进程，由 restart 策略重启；不承诺当前 2核4G 支持任意高并发或所有高成本计算。

部署和回退见 [deploy/README.md](deploy/README.md)。

HTTP 配置也可用同一个验收入口（配置文件需为仅本人可读）：

```bash
uv run python deploy/check_mcp.py --config /PRIVATE/client.private.json --output /PRIVATE/http-check.json
```

验收报告包含科学结果及来源，不包含配置中的 Authorization 请求头；不要把凭据配置本身当报告发布。
