# 逐字稿載入系統 — 專案記憶（CLAUDE.md）

給未來 session／其他對話的你：這份專案照著 `逐字稿載入系統-規格書.md`（原始檔案在使用者的 Downloads 資料夾）第 10 節列出的 7 個開發步驟依序實作。這份文件記錄目前進度、關鍵技術決策，以及跟原規格書不同的地方（含原因），避免每次重新討論一遍。

## 開發進度（對應規格書第 10 節）

| # | 項目 | 狀態 |
|---|---|---|
| 1 | 音檔上傳 + faster-whisper 轉錄 | ✅ 完成 |
| 2 | pyannote.audio + 時間戳對齊邏輯，產出完整 VERBATIM | ✅ 完成 |
| 3 | VERBATIM 轉 docx 下載 | ✅ 完成 |
| 4 | 串接 LLM API 產生 ACTION_ITEMS、SUMMARY，轉 docx 下載 | ✅ 完成（**改用 Gemini API，非規格書原訂的 Claude API**，見下方原因） |
| 5 | 版本管理機制 | ✅ 完成 |
| 6 | 歷史紀錄頁面 | ✅ 完成 |
| 7 | Web 介面整體串接與測試 | ✅ 完成 |

## 專案結構

```
會議記錄系統/
├── CLAUDE.md                          # 本檔案
├── .gitignore
└── backend/
    ├── .env                           # 密鑰與設定（不進版控）
    ├── requirements.txt
    ├── app/
    │   ├── main.py                    # FastAPI app，掛載 router + 靜態頁
    │   ├── config.py                  # 讀 .env、ffmpeg DLL 路徑偵測
    │   ├── jobs.py                    # 記憶體中的 job 狀態（見下方限制）
    │   ├── storage.py                 # 音檔/逐字稿/outputs 的檔案讀寫
    │   ├── alignment.py               # STT segments × diarization turns 對齊
    │   ├── audio_preprocess.py        # ffmpeg 轉成統一 16kHz mono WAV
    │   ├── docx_export.py             # VERBATIM / ACTION_ITEMS / SUMMARY → docx
    │   ├── llm.py                     # Gemini API 呼叫 + prompts
    │   ├── stt/
    │   │   ├── base.py                # STTEngine 抽象介面、Segment dataclass
    │   │   └── faster_whisper_engine.py
    │   ├── diarization/
    │   │   ├── base.py                # DiarizationEngine 抽象介面、SpeakerTurn dataclass
    │   │   └── pyannote_engine.py
    │   └── api/
    │       └── transcribe.py          # 所有 API 路由
    ├── static/index.html              # 單頁前端（上傳/狀態輪詢/下載/版本列表）
    └── data/
        ├── audio/                     # 原始上傳音檔（uuid 命名）
        ├── transcripts/               # 逐字稿 JSON（uuid 命名）
        └── outputs/                   # ACTION_ITEMS/SUMMARY 產出，每版一個檔案
```

## 關鍵技術決策

### STT：faster-whisper
- 模型名稱、device、compute_type 都走 `.env`（`WHISPER_MODEL`/`WHISPER_DEVICE`/`WHISPER_COMPUTE_TYPE`），預設 `medium` / `cpu` / `int8`。
- **這台開發機沒有 GPU**，先用 `medium` 驗證流程正確性，不用一開始就上 `large-v3`（規格書建議值）；之後要衝準確度或換到有 GPU 的機器時，只需要改 `.env`，不用動程式碼。
- `STTEngine` 抽象介面在 `app/stt/base.py`，符合規格書 3.3 的「可替換架構」要求。

### Diarization：pyannote.audio 4.0，非規格書原訂的 3.1
- 規格書寫的 `pyannote/speaker-diarization-3.1` 已過時。目前 pyannote.audio 4.0 的開源本地版模型是 **`pyannote/speaker-diarization-community-1`**（CC-BY-4.0，免費、可本地跑，符合規格書「開源免費」精神）。
- 需要 Hugging Face token（`.env` 的 `HF_TOKEN`），且該 token 對應帳號要先到 https://huggingface.co/pyannote/speaker-diarization-community-1 網頁上接受使用條款，否則下載模型會 401。
- 對齊邏輯（`app/alignment.py`）採規格書 3.2 建議的「片段時間戳中點落入哪個說話者區段」規則，找不到重疊區段時退而求其次找最近的區段。
- 說話者標籤正規化成 `Speaker 1`、`Speaker 2`...（依首次出現順序），不是 pyannote 原始的 `SPEAKER_00` 格式。

### 音檔前處理：統一轉成 WAV
- `app/audio_preprocess.py` 在跑 STT/diarization 前，一律先用 ffmpeg 把上傳的音檔（mp3/wav/m4a）轉成 16kHz mono WAV。
- 原因：手機錄的 m4a 常有 AAC encoder padding，導致容器回報的時長跟實際解碼出來的取樣數對不上，會讓 pyannote 的 chunked reader 讀取失敗。統一轉檔可以避開這個問題，對兩個引擎都更穩定。
- 這台機器上的 ffmpeg 是用 `winget install --id Gyan.FFmpeg.Shared` 裝的（需要「shared」版本才有 DLL，torchcodec 需要這些 DLL 才能載入）。`config.py` 會自動偵測 winget 安裝路徑並註冊 DLL 目錄（`os.add_dll_directory`），不依賴系統 PATH。

### LLM：改用 Google Gemini API，非規格書原訂的 Claude API
- **原因**：使用者評估 Claude API 需要信用卡加值，改選 Gemini API（免費額度不需綁信用卡，有速率限制但對這個系統的用量足夠）。
- SDK：`google-genai`（`pip install google-genai`），用法 `from google import genai` → `client.interactions.create(model=..., input=...)`。
- `.env` 對應變數：`GEMINI_API_KEY`、`GEMINI_MODEL`（預設 `gemini-3.6-flash`）。
- `app/llm.py` 的函式名稱刻意保持通用（`generate_action_items`、`generate_summary`），如果之後要換回 Claude 或其他 LLM，只需要改這個檔案內部實作，不用動 `api/transcribe.py`。
- Prompt 設計完全照規格書 4.2/4.3/4.4：ACTION_ITEMS 用「[負責人：X] 事項 (截止日期：Y)」格式 + Next Steps 條列；SUMMARY 依主題分段、每段小標題、3 分鐘可讀完；兩者一律輸出繁體中文，不受原始音檔語言影響。

### docx 輸出：python-docx
- VERBATIM：`[HH:MM:SS] Speaker N：文字`，逐段輸出，不經 LLM 加工（規格書 4.1）。
- ACTION_ITEMS / SUMMARY：直接把 LLM 回傳的文字逐行寫成段落。

### 資料儲存：檔案系統 JSON，沒有資料庫
- 規格書建議 SQLite，但目前量小，先用檔案系統存 JSON（`data/audio/`、`data/transcripts/`、`data/outputs/`），比較簡單，之後真的需要查詢/索引效能時再考慮換資料庫。
- **逐字稿 JSON schema**（對應規格書 3.4）：
  ```json
  {
    "transcript_id": "uuid",
    "audio_filename": "原始檔名",
    "created_at": "ISO 8601",
    "segments": [
      {"start": 12.5, "end": 16.2, "speaker": "Speaker 1", "text": "..."}
    ]
  }
  ```
- **Output（ACTION_ITEMS/SUMMARY）JSON schema**（對應規格書第 5 節版本管理）：
  ```json
  {
    "output_id": "uuid",
    "transcript_id": "uuid",
    "mode": "ACTION_ITEMS | SUMMARY",
    "version": 1,
    "created_at": "ISO 8601",
    "content": "LLM 產出的純文字"
  }
  ```
  每次觸發重新產生都會建立新的 output 檔案（新 uuid），版本號是同一個 (transcript_id, mode) 底下現有檔案數 +1，**不會覆蓋舊版本**。`storage.list_outputs(transcript_id)` 回傳該逐字稿底下所有版本，依 (mode, version) 排序。

### Job 狀態：記憶體字典，重啟會消失，但不影響資料存取
- `app/jobs.py` 的 pending/processing/done/failed 狀態只存在記憶體裡，伺服器重啟就會不見。
- 但逐字稿 JSON 跟 outputs JSON 都在磁碟上，**重啟後不會消失**。所有需要「逐字稿已完成」的端點（`GET /transcripts/{id}`、VERBATIM 下載、產生 ACTION_ITEMS/SUMMARY）都改成**優先看磁碟上有沒有逐字稿檔案**，只有磁碟上也沒有時才去查記憶體中的 job 狀態（用來回報 pending/processing/failed 這種還沒寫檔的中間狀態）。共用邏輯在 `api/transcribe.py` 的 `_load_ready_transcript()`。
- 歷史紀錄頁（`GET /api/transcripts`，`storage.list_transcripts()`）直接掃 `data/transcripts/*.json` 檔名列出所有逐字稿，不依賴 job 狀態，所以伺服器重啟、甚至換一台機器接手 `data/` 目錄，歷史紀錄都還在。

### 歷史紀錄頁面
- 前端首頁下方固定顯示「歷史紀錄」清單（`GET /api/transcripts`），依上傳時間新到舊排序，顯示檔名、上傳時間、逐字稿段數、已產生的 ACTION_ITEMS/SUMMARY 版本數。
- 點清單項目會呼叫 `GET /api/transcripts/{id}`（同一支既有 API，包含 `transcript` + `outputs`），在同一頁的 `#result` 區塊渲染完整逐字稿跟所有版本輸出，不用另開頁面或路由。
- 上傳新音檔完成、或產生新版本 ACTION_ITEMS/SUMMARY 之後，會自動重新呼叫 `loadHistory()` 刷新清單。

## 環境需求（`.env`）

```
HF_TOKEN=...              # Hugging Face token，需已在 pyannote/speaker-diarization-community-1 頁面接受條款
WHISPER_MODEL=medium      # 沒 GPU 先用 medium，有 GPU 環境可改 large-v3
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
GEMINI_API_KEY=...        # aistudio.google.com/api-keys 申請，免費額度不用信用卡
GEMINI_MODEL=gemini-3.6-flash
```

系統層級還需要：
- FFmpeg（shared/DLL 版本）：`winget install --id Gyan.FFmpeg.Shared -e`
- Python 套件：見 `backend/requirements.txt`（含安裝順序註解，torch 要先裝 CPU 版才不會抓到幾 GB 的 CUDA 版）

## 啟動指令

```bash
cd backend
.venv/Scripts/python.exe -m uvicorn app.main:app --reload
```

## 規格書第 10 節已全部完成（第 1-7 項）

### 第 7 項做了什麼
- 前端新增真正的客戶端驗證（`static/index.html`）：上傳前先檢查副檔名（.mp3/.wav/.m4a），再用 `<audio>` 元素讀取 metadata 檢查時長 ≤ 2 小時，不符合直接擋下不送出，符合規格書 6 節「需做前端基本檔案格式與時長校驗」的要求。
- 狀態文字改成中文（等待處理中／轉錄與說話者辨識中／完成／失敗），取代原本直接顯示英文 status 字串。
- 用 in-app Browser 實際跑過一輪完整流程並截圖驗證：首頁載入 → 點歷史紀錄項目載入舊逐字稿（含 fallback 邏輯）→ 點「產生 Action Items」實際呼叫 Gemini 並顯示結果 → 下載連結存在且格式正確 → 歷史清單即時刷新。因為這個瀏覽環境沒辦法操作原生檔案選取對話框，上傳流程改用「在頁面 JS context 裡組出合法的 WAV Blob 當作 File 物件，直接呼叫 `handleFile()`」的方式測試，等同真實拖曳/選檔會觸發的同一段程式碼路徑，親眼確認 pending → processing → done 整個輪詢與畫面更新都正常。
- 沒有發現需要修的 bug。

至此規格書第 10 節列出的 7 個開發步驟全部完成，系統核心功能（上傳、STT、diarization、VERBATIM/ACTION_ITEMS/SUMMARY 三種輸出、版本管理、歷史紀錄）都已可用。之後若要繼續，可以考慮的方向：把前端排版/UX 再優化、把 job 狀態也做持久化（見上面「已知限制」段落）、或補上規格書沒明講但實務上會需要的東西（例如刪除逐字稿的功能、分頁）。

## 效能優化

同一份 22 秒測試音檔的處理時間從 ~50-55 秒降到 **~38 秒**，三項都不犧牲輸出品質：

1. **VAD filter**（`app/stt/faster_whisper_engine.py`）：`model.transcribe(audio_path, vad_filter=True)`，先跳過靜音再送進模型，會議錄音常有停頓，省下不少時間。
2. **明確設定 CPU 執行緒數**：這台機器 12 核，`.env` 新增 `WHISPER_CPU_THREADS`（預設 8）、`DIARIZATION_CPU_THREADS`（預設 4）——因為 STT 跟 diarization 現在平行跑（見下一點），兩者分配核心數避免互搶，換到別的機器要照核心數調整。faster-whisper 走 ctranslate2 自己的執行緒池（`WhisperModel(cpu_threads=...)`），pyannote 走 torch 的（`torch.set_num_threads(...)`），兩者互不影響。
3. **STT 跟 diarization 平行跑**（`api/transcribe.py` 的 `_run_transcription`）：兩者互不依賴（都只需要那份轉檔後的 WAV），改用 `ThreadPoolExecutor` 同時送出去跑，總時間接近「兩者中較慢的那個」而不是「兩者相加」。兩個引擎都會在計算時釋放 GIL（ctranslate2 是原生 C++、torch 也是），所以純 thread（不用 multiprocessing）就能拿到真正的平行效果。

還沒做、如果之後真的需要更快可以考慮：`WHISPER_MODEL` 降級（medium→small，準確度會下降，尤其中英夾雜）、GPU（本地或雲端，效果最大但要硬體/預算）、換成付費雲端 STT API（`STTEngine` 抽象層本來就是為了這個）。

## 部署（Cloudflare Tunnel + GitHub）

**現況**：公開網址透過 Cloudflare Quick Tunnel 對外，跑在使用者自己這台 Windows 機器上（沒有租用任何雲端主機——免費雲端方案的 RAM 通常撐不住 torch + faster-whisper + pyannote 這套疊層，所以選擇用自己已經驗證跑得動的機器）。

- **權限模型維持規格書原案**：無登入、公開、不分使用者（預期使用者 <5 人，內部快速上線優先於做帳號系統）。
- **Cloudflare Tunnel**：`winget install --id Cloudflare.cloudflared`，用 Quick Tunnel（`cloudflared tunnel --url http://localhost:8000`），不需要 Cloudflare 帳號、不需要網域。
  - ⚠️ **網址不固定**：Quick Tunnel 每次重啟都會換一個新的 `*.trycloudflare.com` 隨機網址，重開機或 tunnel process 重啟後網址會變。要固定網址需要使用者自己買網域、綁到 Cloudflare、改用「named tunnel」（需要 `cloudflared tunnel login` 走一次帳號綁定），目前沒做。
  - 目前網址查詢方式：跑 `backend/get_tunnel_url.ps1`，會從 `backend/logs/tunnel.log` 抓最新的網址。
- **開機自動啟動**：這個 sandbox 環境對 Task Scheduler（`schtasks`/`Register-ScheduledTask`）沒有權限（Access Denied），改用**傳統 Windows 啟動資料夾**：
  - `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\start_server.vbs`
  - `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\start_tunnel.vbs`
  - 這兩個 `.vbs` 用 `WScript.Shell.Run` 隱藏視窗啟動對應的 `backend/start_server.ps1` / `backend/start_tunnel.ps1`。
  - **編碼是這裡的坑**：路徑含中文（`桌面`、`會議記錄系統`），經典 VBScript（`cscript`/`wscript`）預設用系統 ANSI codepage 讀檔，UTF-8 BOM 也不行（會被當亂碼，編譯期直接報「無效的字元」）——**要用 UTF-16LE + BOM**（PowerShell `Set-Content -Encoding Unicode`）VBScript 才讀得對中文路徑。如果之後要改這兩個 `.vbs`，記得維持這個編碼，不要用一般文字編輯器存成 UTF-8 覆蓋掉。
  - `start_server.ps1` 沒加 `--reload`（正式執行不需要熱重載），`start_tunnel.ps1` 有內建 8 秒延遲，確保先等 server 起來再連。
  - 這個機制只有在**真的登入 Windows** 時才會觸發，沒辦法在這個 sandbox 裡直接驗證「登入時真的會跑」，但用 `cscript` 手動跑過一次確認整個路徑解析跟啟動鏈是通的（會正確印出 port 8000 已被佔用的錯誤，證明程式碼跟路徑都對，只是因為手動啟動的伺服器已經佔住那個 port）。
- **GitHub**：程式碼在 https://github.com/Ines81811/meeting-minutes（`main` branch，public）。`.gitignore` 排除 `.env`、`data/audio|transcripts|outputs/*`、`.venv/`、`logs/`——只有程式碼上去，音檔/逐字稿/API 金鑰都留在本機。目前只是單純的程式碼備份，還沒接 CI/CD 自動部署（因為部署方式是「本機常駐服務」，不是典型的 push-to-deploy 平台）。

### 已知的營運狀況（實際發生過，不是理論上的風險）

- **Quick Tunnel 真的斷過一次**：cloudflared process 還活著、沒當掉，但邊緣連線斷了，網址變成連不上（`curl` 回 `HTTP 000`）。這印證了 Cloudflare 官方文件寫的「quick tunnel 沒有 uptime 保證」不是講假的。處理方式：把舊 process `taskkill /F` 掉，重新跑一次 `cloudflared tunnel --url http://localhost:8000`，會拿到一組新網址（新舊網址完全無關，不是同一個 tunnel 復活）。
- **這個 Claude Code sandbox／對話 session 重啟，會把背景跑的 server + tunnel process 一起帶走**：不是「斷線」，是**process 直接消失**（`tasklist` 查不到）。開機資料夾（`Startup\*.vbs`）那組**不會**因為這種重啟而觸發——它只在**真的登入 Windows** 時才會執行，sandbox/session 重啟不算登入。所以每次接續一個新的 Claude session 時，第一件事應該是先檢查 `http://127.0.0.1:8000/` 跟 tunnel 網址是否還活著，兩個都可能需要手動重開：
  ```bash
  # server（背景執行，冷啟動約 15-25 秒——torch/pyannote import 需要時間，第一次 curl 可能還是 000，等一下再試）
  cd backend && ./.venv/Scripts/python.exe -m uvicorn app.main:app --port 8000

  # tunnel（背景執行，從輸出 log 抓新網址）
  "/c/Program Files (x86)/cloudflared/cloudflared.exe" tunnel --url http://localhost:8000
  ```
- **目前的公開網址不要寫死在這份文件裡**——因為上面兩點，網址會一直換，寫了也會馬上過期。要拿目前的網址，用上面的指令重新啟動一次最準。
- 這些狀況（服務會斷、網址會變、需要人手動重啟）正是「先上免費方案、以後再看要不要花錢」這個決策帶來的直接後果，已經在跟老闆的匯報裡講清楚了。真的要解決，還是要嘛買網域＋named tunnel（網址不再變），要嘛換成真正的常駐主機（不依賴這台開發機、不依賴這個 Claude session）。
