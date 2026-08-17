from functools import lru_cache

from google import genai

from app import config

ACTION_ITEMS_PROMPT = """以下是一份會議逐字稿。請從中抽取 Action Items 與 Next Steps，並以繁體中文輸出，格式如下：

Action Items
1. [負責人：某某] 事項描述 (截止日期：某日期)
2. [負責人：未指定] 事項描述

Next Steps
- 條列式項目
- ...

規則：
- 若逐字稿中有明確指派負責人，填入該負責人姓名；若沒有明確指派，標記為「未指定」
- 若有明確提及截止日期，填入；若無則省略「(截止日期：...)」這部分
- 不論逐字稿原始語言為何，一律輸出繁體中文
- 只輸出上述格式的內容，不要有其他說明文字

逐字稿：
{transcript_text}"""

SUMMARY_PROMPT = """以下是一份會議逐字稿。請產出一份一般人 3 分鐘內可讀完的會議摘要，依會議中討論到的主題/議程分段落呈現，每段落有小標題。

規則：
- 純繁體中文輸出，不論逐字稿原始語言為何
- 不需要逐字稿內容，只需要摘要
- 依主題分段，每段給一個簡短小標題
- 只輸出摘要內容，不要有其他說明文字

逐字稿：
{transcript_text}"""


def build_transcript_text(transcript: dict) -> str:
    lines = []
    for seg in transcript["segments"]:
        speaker = f"{seg['speaker']}：" if seg.get("speaker") else ""
        lines.append(f"{speaker}{seg['text']}")
    return "\n".join(lines)


@lru_cache
def _get_client() -> genai.Client:
    return genai.Client(api_key=config.GEMINI_API_KEY)


def _generate(prompt_template: str, transcript_text: str) -> str:
    interaction = _get_client().interactions.create(
        model=config.GEMINI_MODEL,
        input=prompt_template.format(transcript_text=transcript_text),
    )
    return interaction.output_text.strip()


def generate_action_items(transcript_text: str) -> str:
    return _generate(ACTION_ITEMS_PROMPT, transcript_text)


def generate_summary(transcript_text: str) -> str:
    return _generate(SUMMARY_PROMPT, transcript_text)
