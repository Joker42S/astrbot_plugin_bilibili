import os

CURRENT_DIR = os.path.dirname(__file__)
LOGO_PATH = os.path.join(CURRENT_DIR, "Astrbot.png")
BV = r"(?:\?.*)?(?:https?:\/\/)?(?:www\.)?bilibili\.com\/video\/(BV[\w\d]+)\/?(?:\?.*)?|BV[\w\d]+"
VALID_FILTER_TYPES = {"forward", "lottery", "video"}
DATA_PATH = "data/astrbot_plugin_bilibili.json"
DEFAULT_CFG = {
    "bili_sub_list": {}  # sub_user -> [{"uid": "uid", "last": "last_dynamic_id", ...}]
}
TEMPLATE_PATH = os.path.join(CURRENT_DIR, "template.html")
IMG_PATH = "data/temp.jpg"
MAX_ATTEMPTS = 3
RETRY_DELAY = 2

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
