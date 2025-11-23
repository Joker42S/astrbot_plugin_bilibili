import os
from typing import Dict

CURRENT_DIR = os.path.dirname(__file__)
ASSETS_DIR = os.path.join(CURRENT_DIR, "assets")


def _asset_path(*parts: str) -> str:
    return os.path.join(ASSETS_DIR, *parts)


LOGO_PATH = _asset_path("Astrbot.png")
BANNER_PATH = _asset_path("banner.png")
BV = r"(?:\?.*)?(?:https?:\/\/)?(?:www\.)?(?:bilibili\.com\/video\/(BV[a-zA-Z0-9]+)|b23\.tv\/([a-zA-Z0-9]+))\/?(?:\?.*)?|BV[a-zA-Z0-9]+"
VALID_FILTER_TYPES = {"forward", "lottery", "video", "article", "draw", "live"}
DATA_PATH = "data/astrbot_plugin_bilibili.json"
DEFAULT_CFG = {
    "bili_sub_list": {}  # sub_user -> [{"uid": "uid", "last": "last_dynamic_id", ...}]
}


def _discover_templates() -> Dict[str, str]:
    templates: Dict[str, str] = {}
    if os.path.isdir(ASSETS_DIR):
        for filename in os.listdir(ASSETS_DIR):
            if filename.lower().endswith(".html"):
                name, _ = os.path.splitext(filename)
                templates[name] = os.path.join(ASSETS_DIR, filename)
    return templates


TEMPLATES = _discover_templates()

MAX_ATTEMPTS = 3
RETRY_DELAY = 2
RECENT_DYNAMIC_CACHE = 4

category_mapping = {
    "全部": "ALL",
    "原创": "ORIGINAL",
    "漫画改": "COMIC",
    "小说改": "NOVEL",
    "游戏改": "GAME",
    "特摄": "TOKUSATSU",
    "布袋戏": "BUDAIXI",
    "热血": "WARM",
    "穿越": "TIMEBACK",
    "奇幻": "IMAGING",
    "战斗": "WAR",
    "搞笑": "FUNNY",
    "日常": "DAILY",
    "科幻": "SCIENCE_FICTION",
    "萌系": "MOE",
    "治愈": "HEAL",
    "校园": "SCHOOL",
    "儿童": "CHILDREN",
    "泡面": "NOODLES",
    "恋爱": "LOVE",
    "少女": "GIRLISH",
    "魔法": "MAGIC",
    "冒险": "ADVENTURE",
    "历史": "HISTORY",
    "架空": "ALTERNATE",
    "机战": "MACHINE_BATTLE",
    "神魔": "GODS_DEM",
    "声控": "VOICE",
    "运动": "SPORT",
    "励志": "INSPIRATION",
    "音乐": "MUSIC",
    "推理": "ILLATION",
    "社团": "SOCIEITES",
    "智斗": "OUTWIT",
    "催泪": "TEAR",
    "美食": "FOOD",
    "偶像": "IDOL",
    "乙女": "OTOME",
    "职场": "WORK",
}
