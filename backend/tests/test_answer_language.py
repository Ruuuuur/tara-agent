import pytest

from tara_agent.agent.conversation import build_conversation_context
from tara_agent.agent.language import resolve_answer_language
from tara_agent.agent.models import ConversationMessage


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("查询前两个 Tara 样本的编号与海区。", "zh"),
        ("List the first two Tara samples and their ocean regions.", "en"),
        ("比较 V4 / V9 的 Shannon diversity 与 Opisthokonta 丰度。", "zh"),
        ("Find samples TARA_A100000038 and TARA_A100000039.", "en"),
        ("Use English: 查询两个样本。", "en"),
        ("Use Chinese: list two samples.", "zh"),
        ("请用英文回答：查询前两个样本。", "en"),
        ("英文回答：查询前两个样本。", "en"),
        ("用英文名查询 Opisthokonta 的丰度。", "zh"),
        ("请用中文解释这个英文回答的含义。", "zh"),
        ("请用英文来解释 Shannon 指数。", "en"),
        ("查询前两个样本，使用英语解释。", "en"),
        ("List two samples. 请用中文回答。", "zh"),
        ("List two samples; reply in Chinese.", "zh"),
        ("查询前两个样本。Answer in English please.", "en"),
        ("中文回答。不，改用英文。", "en"),
        ("不要用中文，请用英文回答。", "en"),
        ("Don't answer in Chinese; respond in English.", "en"),
        ("请解释代码 `reply in English` 的含义。", "zh"),
        ("解释这句提示：“answer in English”。", "zh"),
        ("Compare diversity between two 海区 using the V4 marker and explain the results.", "en"),
        ("继续", "zh"),
        ("Continue", "en"),
        ("123", "zh"),
    ],
)
def test_language_follows_question_and_explicit_request(question, expected):
    assert resolve_answer_language(question) == expected


@pytest.mark.parametrize("question", ["继续", "再详细一点", "Continue!", "Why?", "TARA_A100000038"])
@pytest.mark.parametrize(
    ("previous", "expected"),
    [
        ("Here are the two samples and their ocean regions.", "en"),
        ("以下是两个样本及其海区。", "zh"),
    ],
)
def test_short_follow_up_inherits_previous_answer(question, previous, expected):
    context = build_conversation_context(
        [ConversationMessage(role="assistant", content=previous)], question=question
    )
    assert context.answer_language == expected


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("What is Shannon diversity?", "en"),
        ("请解释 Shannon 多样性。", "zh"),
        ("继续，请用英文回答。", "en"),
        ("Continue, reply in Chinese.", "zh"),
    ],
)
def test_current_question_overrides_history(question, expected):
    history = [ConversationMessage(role="assistant", content="历史中文回答。")]
    assert resolve_answer_language(question, history) == expected


def test_follow_up_uses_latest_answer_and_does_not_modify_scientific_text():
    history = [
        ConversationMessage(role="assistant", content="中文历史。"),
        ConversationMessage(role="user", content="改用英文回答。"),
        ConversationMessage(role="assistant", content="Sample TARA_A100000038 has Shannon 2.5."),
    ]
    context = build_conversation_context(history, question="继续")
    assert context.answer_language == "en"
    assert context.messages == history


def test_chinese_question_next_to_sample_id_does_not_inherit_english():
    history = [
        ConversationMessage(role="assistant", content="The sample is in the Atlantic Ocean.")
    ]
    assert resolve_answer_language("查询TARA_A100000038", history) == "zh"
