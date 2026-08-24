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

SUMMARY_PROMPT = """以下是一份會議逐字稿。請產出一份結構化的會議摘要，格式必須使用以下 Markdown 語法：

- `# 標題文字` 表示大主題（第一層標題）
- `## 標題文字` 表示大主題底下的子主題（第二層標題）
- `- 內容` 表示條列重點（第一層條列）
- 用兩個半形空格縮排再接 `- 內容`（即 `  - 內容`）表示條列底下的補充細節（第二層條列）
- `**文字**` 表示需要強調的粗體文字

結構規則：
- 大主題（#）與子主題（##）要依這份逐字稿實際討論到的內容自行歸納分類，不要套用固定的分類清單；財務/業務型會議可能會分「業務數據」「團隊編制」之類的主題，訪談則可能依受訪者談到的每個面向分主題，一切以逐字稿實際內容為準
- 最多使用兩層標題（# 與 ##）、兩層條列（- 與縮排 -），不要再往下細分
- 條列項目若開頭是一個簡短標籤（例如「每月廣告費」「受訪者背景」這類主題詞），請把該標籤用 **粗體** 標示、接著冒號再寫內容說明，例如：`- **每月廣告費**：SOV 品牌...約為 23 萬至 25 萬元`
- 除了開頭標籤外，內文中的關鍵數字、金額、比例、人名、決策結論等重要資訊也要用 **粗體** 標示
- 一般人可在 3 分鐘內讀完，只保留有意義的重點，省略逐字稿中的口語贅字

規則：
- 純繁體中文輸出，不論逐字稿原始語言為何
- 不需要逐字稿內容，只需要摘要
- 只輸出上述 Markdown 格式的摘要內容，不要有其他說明文字，不要用 ``` 包住整段輸出

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
