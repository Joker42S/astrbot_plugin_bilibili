import os
import time
import uuid
import asyncio
from .utils import *
from typing import Dict, Any
from astrbot.api import logger
from astrbot.api.all import Star
from .constant import TEMPLATE_PATH, LOGO_PATH, TEMP_DIR, MAX_ATTEMPTS, RETRY_DELAY

with open(TEMPLATE_PATH, "r", encoding="utf-8") as file:
    HTML_TEMPLATE = file.read()


class Renderer:
    """
    负责将动态数据渲染成图片。
    """

    def __init__(self, star_instance: Star, rai: bool):
        """
        初始化渲染器。
        """
        self.star = star_instance
        self.rai = rai

    async def render_dynamic(self, render_data: Dict[str, Any]):
        """
        将渲染数据字典渲染成最终图片。
        这是该类的主要入口方法。
        """
        os.makedirs(TEMP_DIR, exist_ok=True)
        options = {"full_page": True, "type": "png", "quality": None, "scale": "device"}
        for attempt in range(1, MAX_ATTEMPTS + 1):
            render_output = None
            try:
                render_output = await self.star.html_render(
                    tmpl=HTML_TEMPLATE,
                    data=render_data,
                    return_url=False,
                    options=options,
                )
                if (
                    render_output
                    and os.path.exists(render_output)
                    and os.path.getsize(render_output) > 0
                ):
                    filename = (
                        f"dynamic_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}.png"
                    )
                    output_path = os.path.join(TEMP_DIR, filename)
                    await get_and_crop_image(render_output, output_path)
                    return output_path  # 成功，返回图片路径
            except Exception as e:
                logger.error(f"渲染图片失败 (尝试次数: {attempt}): {e}")

            if attempt < MAX_ATTEMPTS:
                await asyncio.sleep(RETRY_DELAY)

        return None  # 所有尝试都失败

    async def build_render_data(
        self, item: Dict, is_forward: bool = False
    ) -> Dict[str, Any]:
        """
        根据从B站API获取的单个动态项目，构建用于渲染的字典。
        is_forward: 标记是否正在处理转发动态
        """
        render_data = await create_render_data()

        # 用户名称、头像、挂件
        author_module = item.get("modules", {}).get("module_author", {})
        render_data["name"] = author_module.get("name")
        render_data["avatar"] = author_module.get("face")
        render_data["pendant"] = author_module.get("pendant", {}).get("image")
        render_data["type"] = item.get("type")

        # 根据不同动态类型填充数据
        if item.get("type") == "DYNAMIC_TYPE_AV":
            # 视频动态
            archive = item["modules"]["module_dynamic"]["major"]["archive"]
            title = archive["title"]
            bv = archive["bvid"]
            cover_url = archive["cover"]

            try:
                content_text = item["modules"]["module_dynamic"]["desc"]["text"]
            except (TypeError, KeyError):
                content_text = None  # 或默认值

            if content_text:
                rich_text = await parse_rich_text(
                    item["modules"]["module_dynamic"]["desc"],
                    item["modules"]["module_dynamic"]["topic"],
                )
                render_data["text"] = f"投稿了新视频<br>{rich_text}"
            else:
                render_data["text"] = f"投稿了新视频<br>"
            render_data["title"] = title
            render_data["image_urls"] = [cover_url]
            if not is_forward:
                url = f"https://www.bilibili.com/video/{bv}"
                render_data["qrcode"] = await create_qrcode(url)
                render_data["url"] = url
            # logger.info(f"返回视频动态 {dyn_id}。")
            return render_data
        elif item.get("type") in (
            "DYNAMIC_TYPE_DRAW",
            "DYNAMIC_TYPE_WORD",
            "DYNAMIC_TYPE_ARTICLE",
        ):
            # 图文动态
            opus = item["modules"]["module_dynamic"]["major"]["opus"]
            summary = opus["summary"]
            jump_url = opus["jump_url"]
            topic = item["modules"]["module_dynamic"]["topic"]

            render_data["summary"] = summary["text"]
            render_data["text"] = await parse_rich_text(summary, topic)
            render_data["title"] = opus["title"]
            render_data["image_urls"] = [pic["url"] for pic in opus["pics"][:9]]
            if not render_data["image_urls"] and self.rai:
                render_data["image_urls"] = [await image_to_base64(LOGO_PATH)]
            if not is_forward:
                url = f"https:{jump_url}"
                render_data["qrcode"] = await create_qrcode(url)
                render_data["url"] = url
            # logger.info(f"返回图文动态 {dyn_id}。")
            return render_data
        elif item.get("type") == "DYNAMIC_TYPE_FORWARD":
            # 转发动态
            try:
                content_text = item["modules"]["module_dynamic"]["desc"]["text"]
            except (TypeError, KeyError):
                content_text = None
            if content_text:
                rich_text = await parse_rich_text(
                    item["modules"]["module_dynamic"]["desc"],
                    item["modules"]["module_dynamic"]["topic"],
                )
                render_data["text"] = f"{rich_text}"
            return render_data

        return render_data
