# VENDOR — ที่มาและรายการแพตช์ (line-ext-reader)

| ส่วน | ต้นทาง | เวอร์ชัน/hash |
|---|---|---|
| `src/line_desktop_mcp/` | github.com/onlygummy/line-desktop-mcp (MIT) | commit `a1af60b6f2376a8c39bb93538ab9fc134f305f47` "release 2.0.0" (2026-09-15) |
| `src/line_ext_msg/` + `tests/` | PyPI sdist `line_ext_msg-2.0.0.tar.gz` (MIT, ITC6910120) | sha256 `d1c523d4b18ef30b3f678c0f1db844fd249bf14068e502f6e3df28dcf7a04346` = hash in upstream uv.lock (ตรวจด้วย `shasum -a 256`) |
| `uv.lock` | เริ่มจาก uv.lock ของ line-desktop-mcp; transitive deps ทุกตัวที่ใช้ร่วมกันเวอร์ชันเท่าเดิม (fastmcp 4.0.3, playwright 1.62.0) · เพิ่มเฉพาะ pytest/pluggy/iniconfig/colorama · ตัด mypy/ruff | `uv sync --frozen` |

License เดิมเก็บที่ `vendor-licenses/`.

## แพตช์ที่ทำ (เทียบกับต้นทาง)
- `browser/process.py`: path Chrome mac · ปิดโปรเซสด้วย `os.killpg` SIGTERM→SIGKILL (เช็ค command line ของ PID ก่อนฆ่า กัน PID ซ้ำ) · fallback `pgrep -f` (regex-escape) · ตัด taskkill/PowerShell
- `browser/chrome.py`: `start_new_session=True` แทน creationflags · ข้อความ error/port_hint เป็น mac (`lsof`)
- `config/settings.py`: โปรไฟล์ default `~/Library/Application Support/line-ext-reader`
- `config/paths.py` + `service/qr.py`: โฟลเดอร์ session (pid, qr.png) ย้ายจาก CWD ไป `~/Library/Application Support/line-ext-reader/session`
- `service/qr_view.py`: ฟอนต์ Helvetica Neue · ตัด ctypes.windll · `browser/mode.py`: แก้คอมเมนต์
- ลบ `line_ext_msg/cli.py` (เขียนข้อความลงดิสก์ได้) และเทสต์ของมัน
- MCP: ลบ `tools/session.py` (probe_session, clear_session) และ tool `unread_full` · cli เหลือ stdio อย่างเดียว (ตัดโหมด http ไม่มี auth)

## ที่ยังเหลือในไลบรารี (ไม่มี tool เรียกถึง — ต้องรู้)
`LineClient.clear_session` / `probe_session` · `Messages.save()` / `download_media()` (เขียนไฟล์ถ้ามีโค้ดเรียก) ·
เปิดหน้า Chrome Web Store ในหน้าต่าง Chrome เพื่อให้ผู้ใช้กดติดตั้งส่วนขยาย (`browser/session.py: open_store_page`)
