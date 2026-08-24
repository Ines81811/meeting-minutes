from functools import lru_cache

from google import genai

from app import config

ACTION_ITEMS_PROMPT = """以下是一份會議逐字稿。請從中抽取 Action Items 與 Next Steps，並以繁體中文輸出，格式必須使用以下 Markdown 語法（與會議摘要功能相同的一套語法）：

- `# 標題文字` 表示大區塊（Action Items / Next Steps）
- `- 內容` 表示條列（第一層，一個事項的標題）
- 用兩個半形空格縮排再接 `- 內容`（即 `  - 內容`）表示該事項底下的欄位明細（第二層）
- `**文字**` 表示需要強調的粗體文字

輸出格式：

# Action Items
- **事項**：<簡短描述具體要做的事>
  - **負責人**：<有明確指派就填人名，沒有則填「未指定」>
  - **截止日期**：<有明確提及就填，沒有則省略這一行>
  - **背景**：<濃縮成 1-2 句話，說明這件事在會議中是怎麼被提出來的、為什麼需要做，不要只重述事項本身>

# Next Steps
- <條列式項目，較籠統的後續方向，不一定有明確負責人/期限>

規則：
- 每個 Action Item 都要有 **背景** 欄位，交代會議中的討論脈絡，不要只寫「誰要做什麼」這種單行結論
- 若逐字稿中有明確指派負責人，填入該負責人姓名；若沒有明確指派，標記為「未指定」
- 若沒有明確提及截止日期，整行省略，不要寫「未提及」之類的字樣
- 不論逐字稿原始語言為何，一律輸出繁體中文
- 只輸出上述 Markdown 格式的內容，不要有其他說明文字，不要用 ``` 包住整段輸出

逐字稿：
{transcript_text}"""

SUMMARY_PROMPT_TEMPLATE = """以下是一份會議逐字稿。請產出一份結構化的會議摘要，格式必須使用以下 Markdown 語法：

- `# 標題文字` 表示大主題（第一層標題）
- `## 標題文字` 表示大主題底下的子主題（第二層標題）
- `- 內容` 表示條列重點（第一層條列）
- 用兩個半形空格縮排再接 `- 內容`（即 `  - 內容`）表示條列底下的補充細節（第二層條列）
- `**文字**` 表示需要強調的粗體文字

結構規則：
{style_instructions}
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

# Per-style "結構規則" opener injected into SUMMARY_PROMPT_TEMPLATE. Shared
# rules (Markdown syntax, bold rules, output language, ...) live once in the
# template above; only the organizational logic differs by style, so tuning
# one style never risks drifting the shared contract the docx/web renderers
# depend on.
SUMMARY_STYLES: dict[str, dict[str, str]] = {
    "auto": {
        "label": "自動判斷",
        "instructions": "- 大主題（#）與子主題（##）依這份逐字稿實際討論到的內容自行歸納分類，不要套用固定的分類清單；財務/業務型會議可能會分「業務數據」「團隊編制」之類的主題，訪談則依受訪者談到的每個面向分主題，決策討論則依議題分——一切以逐字稿實際性質判斷",
    },
    "data": {
        "label": "數據報告型",
        "instructions": "- 依業務/數據面向分主題（例如成本、成交率、人事、財務等），每個重點條列聚焦在具體數字與事實，避免空泛描述",
    },
    "decision": {
        "label": "決策討論型",
        "instructions": "- 依討論到的議題分主題，每個議題下列出各方立場、**最終結論**與**待辦事項**；結論與待辦務必用粗體標示，讓讀者一眼看到「決定了什麼」",
    },
    "interview": {
        "label": "訪談型",
        "instructions": "- 依受訪者談到的主題面向分主題；若原話本身是重點（觀點、感受、關鍵表態），用「**問**：...」「**答**：『原話引述』」的格式保留受訪者的實際措辭，不要全部改寫成第三人稱陳述句",
    },
    "comparison": {
        "label": "方案比較型",
        "instructions": "- 若逐字稿在比較多個方案/選項，用 `## 方案 A：xxx`、`## 方案 B：xxx` 這樣的子標題並列呈現，各自列出內容與優缺點/疑慮，方便讀者對照；若逐字稿沒有明顯的方案比較，則依主題分段即可",
    },
}


def build_transcript_text(transcript: dict) -> str:
    lines = []
    for seg in transcript["segments"]:
        speaker = f"{seg['speaker']}：" if seg.get("speaker") else ""
        lines.append(f"{speaker}{seg['text']}")
    return "\n".join(lines)


@lru_cache
def _get_client() -> genai.Client:
    return genai.Client(api_key=config.GEMINI_API_KEY)


def _generate(prompt: str) -> str:
    interaction = _get_client().interactions.create(
        model=config.GEMINI_MODEL,
        input=prompt,
    )
    return interaction.output_text.strip()


def generate_action_items(transcript_text: str) -> str:
    return _generate(ACTION_ITEMS_PROMPT.format(transcript_text=transcript_text))


def generate_summary(transcript_text: str, style: str = "auto") -> str:
    style_config = SUMMARY_STYLES.get(style, SUMMARY_STYLES["auto"])
    prompt = SUMMARY_PROMPT_TEMPLATE.format(
        style_instructions=style_config["instructions"],
        transcript_text=transcript_text,
    )
    return _generate(prompt)
