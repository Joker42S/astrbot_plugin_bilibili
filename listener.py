import re
import time
import asyncio
import traceback
from collections import OrderedDict
from typing import Dict, Any, Optional, List
from astrbot.api import logger
from astrbot.api.message_components import Image, Plain, Node, File
from astrbot.api.event import MessageEventResult, MessageChain
from astrbot.api.all import *
from .data_manager import DataManager
from .bili_client import BiliClient
from .renderer import Renderer
from .utils import create_render_data, image_to_base64, create_qrcode, is_height_valid
from .constant import LOGO_PATH, BANNER_PATH


class DynamicListener:
    """
    负责后台轮询检查B站动态和直播，并推送更新。
    """

    def __init__(
        self,
        context: Context,
        data_manager: DataManager,
        bili_client: BiliClient,
        renderer: Renderer,
        cfg: dict,
    ):
        self.context = context
        self.data_manager = data_manager
        self.bili_client = bili_client
        self.renderer = renderer
        self.interval_mins = float(cfg.get("interval_mins", 20))
        self.rai = cfg.get("rai", True)
        self.node = cfg.get("node", False)
        self.dynamic_limit = cfg.get("dynamic_limit", 5)
        self.render_cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self.render_cache_limit = int(cfg.get("render_cache_limit", 32))

    async def start(self):
        """启动后台监听循环。"""
        while True:
            if self.bili_client.credential is None:
                logger.warning(
                    "Bilibili 凭据未设置，无法获取动态。请使用 /bili_login 登录或在配置中设置 sessdata。"
                )
                await asyncio.sleep(60 * self.interval_mins)
                continue

            all_subs = self.data_manager.get_all_subscriptions()
            for sub_user, sub_list in all_subs.items():
                for sub_data in sub_list:
                    try:
                        await self._check_single_up(sub_user, sub_data)
                    except Exception as e:
                        logger.error(
                            f"处理订阅者 {sub_user} 的 UP主 {sub_data.get('uid', '未知UID')} 时发生未知错误: {e}\n{traceback.format_exc()}"
                        )
            await asyncio.sleep(60 * self.interval_mins)

    async def _check_single_up(self, sub_user: str, sub_data: Dict[str, Any]):
        """检查单个订阅的UP主是否有更新。"""
        uid = sub_data.get("uid")
        if not uid:
            return

        # 检查动态更新
        dyn = await self.bili_client.get_latest_dynamics(uid)
        if dyn:
            result_list = await self._parse_and_filter_dynamics(dyn, sub_data)
            sent = 0
            for render_data, dyn_id in reversed(result_list):
                if render_data:
                    if sent < self.dynamic_limit:
                        sent += 1
                        await self._handle_new_dynamic(sub_user, render_data, dyn_id)
                    await self.data_manager.update_last_dynamic_id(
                        sub_user, uid, dyn_id
                    )

                elif dyn_id:  # 动态被过滤，只更新ID
                    await self.data_manager.update_last_dynamic_id(
                        sub_user, uid, dyn_id
                    )

        # 检查直播状态
        if "live" in sub_data.get("filter_types", []):
            return
        # lives = await self.bili_client.get_live_info(uid)
        lives = await self.bili_client.get_live_info_by_uids([uid])
        if lives:
            await self._handle_live_status(sub_user, sub_data, lives)

    def _compose_plain_dynamic(
        self, render_data: Dict[str, Any], render_fail: bool = False
    ):
        """转换为纯文本消息链。"""
        name = render_data.get("name")
        summary = render_data.get("summary", "")
        prefix_fail = [Plain("渲染图片失败了 (´;ω;`)\n")] if render_fail else []
        ls = [
            *prefix_fail,
            Plain(f"📣 UP 主 「{name}」 发布了新图文动态:\n"),
            Plain(summary),
        ]
        for pic in render_data.get("image_urls", []):
            ls.append(Image.fromURL(pic))
        return ls

    async def _send_dynamic(
        self, sub_user: str, chain_parts: list, send_node: bool = False
    ):
        if self.node or send_node:
            qqNode = Node(
                uin=0,
                name="AstrBot",
                content=chain_parts,
            )
            await self.context.send_message(
                sub_user, MessageEventResult(chain=[qqNode])
            )
        else:
            await self.context.send_message(
                sub_user, MessageEventResult(chain=chain_parts).use_t2i(False)
            )

    def _cache_render(self, dyn_id: Optional[str], chain_parts: list, send_node: bool):
        """缓存渲染结果，避免同一动态在不同会话重复渲染。"""
        if not dyn_id:
            return
        self.render_cache[dyn_id] = {"chain": chain_parts, "send_node": send_node}
        while len(self.render_cache) > self.render_cache_limit:
            self.render_cache.popitem(last=False)

    async def _handle_new_dynamic(
        self, sub_user: str, render_data: Dict[str, Any], dyn_id: Optional[str] = None
    ):
        """处理并发送新的动态通知。"""
        cached = self.render_cache.get(dyn_id) if dyn_id else None
        if cached:
            await self._send_dynamic(sub_user, cached["chain"], cached["send_node"])
            return

        send_node_flag = self.node
        # 非图文混合模式
        if not self.rai and render_data.get("type") in (
            "DYNAMIC_TYPE_DRAW",
            "DYNAMIC_TYPE_WORD",
        ):
            ls = self._compose_plain_dynamic(render_data)
            await self._send_dynamic(sub_user, ls, send_node_flag)
            self._cache_render(dyn_id, ls, send_node_flag)
            return

        img_path = await self.renderer.render_dynamic(render_data)
        if img_path:
            url = render_data.get("url", "")
            if await is_height_valid(img_path):
                ls = [Image.fromFileSystem(img_path)]
            else:
                timestamp = int(time.time())
                filename = f"bilibili_dynamic_{timestamp}.jpg"
                ls = [File(file=img_path, name=filename)]
            ls.append(Plain(f"\n{url}"))
            await self._send_dynamic(sub_user, ls, send_node_flag)
            self._cache_render(dyn_id, ls, send_node_flag)
            return

        logger.error("渲染图片失败，尝试发送纯文本消息")
        ls = self._compose_plain_dynamic(render_data, render_fail=True)
        await self._send_dynamic(sub_user, ls, send_node=True)

    async def _handle_live_status(self, sub_user: str, sub_data: Dict, live_room: Dict):
        """处理并发送直播状态变更通知。"""
        is_live = sub_data.get("is_live", False)

        live_name = live_room.get("title", "Unknown")
        user_name = live_room.get("uname", "Unknown")
        cover_url = live_room.get("cover_from_user", "")
        room_id = live_room.get("room_id", 0)
        link = f"https://live.bilibili.com/{room_id}"

        render_data = await create_render_data()
        render_data["banner"] = await image_to_base64(BANNER_PATH)
        render_data["name"] = "AstrBot"
        render_data["avatar"] = await image_to_base64(LOGO_PATH)
        render_data["title"] = live_name
        render_data["url"] = link
        render_data["image_urls"] = [cover_url]
        # live_status: 0：未开播    1：正在直播     2：轮播中
        if live_room.get("live_status", "") == 1 and not is_live:
            render_data["text"] = f"📣 你订阅的UP 「{user_name}」 开播了！"
            await self.data_manager.update_live_status(sub_user, sub_data["uid"], True)
        if live_room.get("live_status", "") != 1 and is_live:
            render_data["text"] = f"📣 你订阅的UP 「{user_name}」 下播了！"
            await self.data_manager.update_live_status(sub_user, sub_data["uid"], False)
        if render_data["text"]:
            render_data["qrcode"] = await create_qrcode(link)
            img_path = await self.renderer.render_dynamic(render_data)
            if img_path:
                await self.context.send_message(
                    sub_user,
                    MessageChain().file_image(img_path).message(render_data["url"]),
                )
            else:
                text = "\n".join(filter(None, render_data.get("text", "").split("\n")))
                await self.context.send_message(
                    sub_user,
                    MessageChain()
                    .message("渲染图片失败了 (´;ω;`)")
                    .message(text)
                    .url_image(cover_url),
                )

    async def _get_dynamic_items(self, dyn: Dict, data: Dict):
        """获取动态条目列表。"""
        last = data["last"]
        items = dyn["items"]
        recent_ids = data.get("recent_ids", []) or []
        known_ids = {x for x in ([last] + recent_ids) if x}
        new_items = []

        for item in items:
            if "modules" not in item:
                continue
            # 过滤置顶
            if (
                item["modules"].get("module_tag")
                and item["modules"]["module_tag"].get("text") == "置顶"
            ):
                continue

            if item["id_str"] in known_ids:
                break
            new_items.append(item)

        return new_items

    def _match_filter_regex(
        self, text: Optional[str], filter_regex: List[str], log_template: str
    ) -> bool:
        """检测文本是否命中过滤正则"""
        if not text or not filter_regex:
            return False

        for regex_pattern in filter_regex:
            try:
                if re.search(regex_pattern, text):
                    logger.info(log_template.format(regex_pattern=regex_pattern))
                    return True
            except re.error:
                logger.warning(f"无效的正则表达式: {regex_pattern}")
                continue

        return False

    async def _parse_and_filter_dynamics(self, dyn: Dict, data: Dict):
        """
        解析并过滤动态。
        """
        filter_types = data.get("filter_types", [])
        filter_regex = data.get("filter_regex", [])
        uid = data.get("uid", "")
        items = await self._get_dynamic_items(dyn, data)  # 不含last及置顶的动态列表
        result_list = []
        # 无新动态
        if not items:
            result_list.append((None, None))

        for item in items:
            dyn_id = item["id_str"]
            # 转发类型
            if item.get("type") == "DYNAMIC_TYPE_FORWARD":
                if "forward" in filter_types:
                    logger.info(f"转发类型在过滤列表 {filter_types} 中。")
                    # return None, dyn_id  # 返回 None 表示不推送，但更新 dyn_id
                    result_list.append((None, dyn_id))
                    continue
                try:
                    content_text = item["modules"]["module_dynamic"]["desc"]["text"]
                except (TypeError, KeyError):
                    content_text = None
                if self._match_filter_regex(
                    content_text, filter_regex, "转发内容匹配正则 {regex_pattern}。"
                ):
                    result_list.append((None, dyn_id))
                    continue
                render_data = await self.renderer.build_render_data(item)
                render_data["uid"] = uid
                render_data["url"] = f"https://t.bilibili.com/{dyn_id}"
                render_data["qrcode"] = await create_qrcode(render_data["url"])

                render_forward = await self.renderer.build_render_data(
                    item["orig"], is_forward=True
                )
                if render_forward["image_urls"]:  # 检查列表是否非空
                    render_forward["image_urls"] = [
                        render_forward["image_urls"][0]
                    ]  # 保留第一项
                render_data["forward"] = render_forward
                result_list.append((render_data, dyn_id))
            elif item.get("type") in ("DYNAMIC_TYPE_DRAW", "DYNAMIC_TYPE_WORD"):
                # 图文类型过滤
                if "draw" in filter_types:
                    logger.info(f"图文类型在过滤列表 {filter_types} 中。")
                    result_list.append((None, dyn_id))
                    continue

                major = (
                    item.get("modules", {}).get("module_dynamic", {}).get("major", {})
                )
                if major.get("type") == "MAJOR_TYPE_BLOCKED":
                    logger.info(f"图文动态 {dyn_id} 为充电专属。")
                    result_list.append((None, dyn_id))
                    continue
                opus = major["opus"]
                summary_text = opus["summary"]["text"]

                if (
                    opus["summary"]["rich_text_nodes"][0].get("text") == "互动抽奖"
                    and "lottery" in filter_types
                ):
                    logger.info(f"互动抽奖在过滤列表 {filter_types} 中。")
                    result_list.append((None, dyn_id))
                    continue
                if self._match_filter_regex(
                    summary_text,
                    filter_regex,
                    f"图文动态 {dyn_id} 的 summary 匹配正则 '{{regex_pattern}}'。",
                ):
                    result_list.append((None, dyn_id))
                    continue
                render_data = await self.renderer.build_render_data(item)
                render_data["uid"] = uid
                result_list.append((render_data, dyn_id))
            elif item.get("type") == "DYNAMIC_TYPE_AV":
                # 视频类型过滤
                if "video" in filter_types:
                    logger.info(f"视频类型在过滤列表 {filter_types} 中。")
                    result_list.append((None, dyn_id))
                    continue
                render_data = await self.renderer.build_render_data(item)
                render_data["uid"] = uid
                result_list.append((render_data, dyn_id))
            elif item.get("type") == "DYNAMIC_TYPE_ARTICLE":
                # 文章类型过滤
                if "article" in filter_types:
                    logger.info(f"文章类型在过滤列表 {filter_types} 中。")
                    result_list.append((None, dyn_id))
                    continue
                major = (
                    item.get("modules", {}).get("module_dynamic", {}).get("major", {})
                )
                if major.get("type") == "MAJOR_TYPE_BLOCKED":
                    logger.info(f"文章 {dyn_id} 为充电专属。")
                    result_list.append((None, dyn_id))
                    continue
                render_data = await self.renderer.build_render_data(item)
                render_data["uid"] = uid
                result_list.append((render_data, dyn_id))
            else:
                result_list.append((None, None))

        return result_list
