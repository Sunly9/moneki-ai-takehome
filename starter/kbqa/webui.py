"""前端经营看板的静态文件接线。

只用原生 HTML/CSS/JS（图表是手写 SVG），所以这里不需要任何构建步骤，
FastAPI 直接把这个目录当静态目录挂出去就行。

目录位置由 `Path(__file__)` 推出来（`kbqa/` 的同级 `web/`），
不写死任何一台机器的绝对路径：仓库 clone 到哪都能跑。
"""

from __future__ import annotations

from pathlib import Path

from fastapi.responses import FileResponse

#: `kbqa/webui.py` -> `kbqa/` -> `starter/web/`
WEB_DIR = Path(__file__).resolve().parent.parent / "web"

INDEX_FILE = WEB_DIR / "index.html"


def index_response() -> FileResponse:
    """把看板首页发回去。

    `FileResponse` 按扩展名推断 `content-type`，`.html` 就是 `text/html`，
    正好满足「GET / 返回 HTML 页面」这条。
    """
    return FileResponse(INDEX_FILE, media_type="text/html; charset=utf-8")
