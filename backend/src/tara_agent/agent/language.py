"""从提问及近期回答选择语言，不依赖浏览器界面语言。"""

from __future__ import annotations

import re
from collections.abc import Iterable

from tara_agent.agent.models import AnswerLanguage, ConversationMessage

# 仅把明确的输出语言要求作为指令；科学名称和文中提到的语言不算要求。
_LANGUAGE_REQUEST = re.compile(
    r"(?:请|麻烦)?(?:用|使用|以|改用|改成|切换到)\s*"
    r"(?P<zh>中文|汉语|简体中文|英语|英文)"
    r"(?=\s*(?:来?(?:回答|回复|解释|说明|输出|作答)|[，。；：,;:!?！？]|$))"
    r"|(?:^|[，。；：,;:!?！？])\s*(?:请)?"
    r"(?P<post>中文|汉语|简体中文|英文|英语)\s*(?:回答|回复|解释|作答)"
    r"|(?:answer|reply|respond|explain|write)(?:\s+(?:this|it|the answer))?\s+in\s+"
    r"(?P<en>English|Chinese|Mandarin|Simplified Chinese)\b"
    r"|\b(?:use|switch to)\s+(?P<use>English|Chinese|Mandarin)\b"
    r"|\b(?P<only>English|Chinese|Mandarin)\s*(?:only|please)\b",
    re.IGNORECASE,
)
_FOLLOW_UPS = frozenset(
    {
        "继续",
        "继续吧",
        "然后呢",
        "为什么",
        "展开",
        "详细一点",
        "再详细一点",
        "这个呢",
        "那个呢",
        "可以",
        "好的",
        "好",
        "是的",
        "对",
        "再来一个",
        "continue",
        "go on",
        "and then",
        "why",
        "how so",
        "more",
        "tell me more",
        "this one",
        "what about this one",
        "yes",
        "ok",
        "okay",
        "please continue",
    }
)


def _text_language(text: str) -> AnswerLanguage | None:
    # 先去掉代码和含数字的标识，再按中英文正文比例判断。
    prose = re.sub(r"```[\s\S]*?```|`[^`]*`|[A-Za-z0-9_]*[_\d][A-Za-z0-9_]*", " ", text)
    han = len(re.findall(r"[\u3400-\u9fff]", prose))
    words = re.findall(r"\b[a-zA-Z]+\b", prose)
    if han:
        return "en" if len(words) > han * 2 else "zh"
    return "en" if words else None


def _explicit_language(question: str) -> AnswerLanguage | None:
    # 引用和代码中的要求只是待分析文本；否定要求不作为正向语言选择。
    prose = re.sub(r'```[\s\S]*?```|`[^`]*`|"[^"\n]*"|“[^”]*”', " ", question)
    prose = re.sub(
        r"(?:不要|不用|别|不使用|不需要用)\s*(?:使用|用)?\s*(?:中文|汉语|英文|英语)"
        r"|\b(?:do not|don't|never)\s+(?:answer|reply|respond|write|explain)\s+in\s+"
        r"(?:English|Chinese|Mandarin)\b",
        " ",
        prose,
        flags=re.IGNORECASE,
    )
    matches = list(_LANGUAGE_REQUEST.finditer(prose))
    if not matches:
        return None
    selected = next(value for value in matches[-1].groups() if value is not None).lower()
    return "en" if selected in {"英文", "英语", "english"} else "zh"


def _quoted_followup(question: str) -> str:
    """引用片段只是证据，语言由追问正文及近期回答决定。"""

    header = re.match(r"^引用此前回答(?:（Trace ID: [0-9a-f-]{36}）)?：\n", question, re.I)
    if header is None:
        return question
    split_at = question.rfind("\n\n我的追问：")
    if split_at < header.end():
        return question
    lines = question[header.end() : split_at].split("\n")
    if not lines or any(not line.startswith("> ") for line in lines):
        return question
    return question[split_at + len("\n\n我的追问：") :]


def resolve_answer_language(
    question: str,
    messages: Iterable[ConversationMessage] = (),
) -> AnswerLanguage:
    """明确要求优先；无语言信息的追问沿用近期回复，否则按本轮正文判断。"""

    question = _quoted_followup(question)
    explicit = _explicit_language(question)
    if explicit is not None:
        return explicit
    normalized = re.sub(r"[\W_]+", " ", question.lower()).strip()
    language = _text_language(question)
    if normalized in _FOLLOW_UPS or language is None:
        history = list(messages)
        for message in reversed(history):
            if message.role == "assistant" and (previous := _text_language(message.content)):
                return previous
        for message in reversed(history):
            previous = _explicit_language(message.content) or _text_language(message.content)
            if previous:
                return previous
    return language or "zh"
