"""reads 稳定性试点的只读 MCP 入口，不在网页请求中启动重型生信任务。"""

from mcp.server.mcpserver.exceptions import ToolError

from tara_agent.analysis.read_models import ReadStudyQuery, ReadStudyResult
from tara_agent.analysis.read_study import ReadStudyService
from tara_agent.mcp.tools import READ_ONLY


def register_read_tools(server, service: ReadStudyService) -> None:
    @server.tool(
        title="比较原始 reads 重算与已发布功能谱",
        annotations=READ_ONLY,
        description=(
            "查询管理员离线完成的ENA原始reads试点；job_id省略时列出可用任务，"
            "指定返回同一MATOU文库的重算与已发布Pfam排名、份额、Top N重合及描述性Spearman。"
            "不下载数据、不启动任意命令，不把单文库或子集参考结果当作全局稳定性证明。"
        ),
    )
    def raw_read_study(query: ReadStudyQuery) -> ReadStudyResult:
        try:
            return service.analyze(query)
        except (OSError, ValueError, KeyError) as error:
            raise ToolError("reads任务无法核验或计算，请检查离线任务产物与MATOU版本") from error
