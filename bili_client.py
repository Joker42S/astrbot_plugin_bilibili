import asyncio
from typing import Any, Awaitable, Callable, Dict, Optional, Tuple

import aiohttp
from astrbot.api import logger
from bilibili_api import Credential, user, video
from bilibili_api.utils.network import Api


class BiliClient:
    """
    负责所有与 Bilibili API 的交互。
    """

    def __init__(
        self,
        sessdata: Optional[str] = None,
        credential_dict: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        初始化 Bilibili API 客户端。
        """
        self.credential = None
        if credential_dict:
            self.credential = Credential(**credential_dict)
        elif sessdata:
            self.credential = Credential(sessdata=sessdata)
        else:
            logger.warning("未提供 SESSDATA 或 凭据，部分需要登录的API可能无法使用。")

    def set_credential(self, credential_dict: Dict[str, Any]) -> None:
        """
        设置凭据。
        """
        self.credential = Credential(**credential_dict)

    def get_credential_dict(self) -> Optional[Dict[str, Any]]:
        """
        获取当前凭据的字典形式。
        """
        if not self.credential:
            return None
        return {
            "sessdata": self.credential.sessdata,
            "bili_jct": self.credential.bili_jct,
            "buvid3": self.credential.buvid3,
            "buvid4": self.credential.buvid4,
            "dedeuserid": self.credential.dedeuserid,
            "ac_time_value": self.credential.ac_time_value,
        }

    async def check_credential(self) -> bool:
        """
        检查凭据是否有效。
        """
        if not self.credential:
            return False
        return await self.credential.check_valid()

    async def refresh_credential(self) -> bool:
        """
        刷新凭据。
        """
        if not self.credential:
            return False
        try:
            if await self.credential.check_refresh():
                await self.credential.refresh()
                return True
        except Exception as e:
            logger.error(f"刷新凭据失败: {e}")
        return False

    async def start_refresh(
        self,
        on_refreshed: Optional[
            Callable[[Dict[str, Any] | None], Awaitable[None]]
        ] = None,
    ):
        """
        定时刷新凭据的循环。
        :param on_refreshed: 刷新成功后的异步回调函数，接收新的凭据字典。
        """
        if (
            not self.credential
            or not self.credential.sessdata
            or not self.credential.bili_jct
        ):
            return

        while True:
            try:
                if self.credential:
                    if await self.credential.check_refresh():
                        await self.credential.refresh()
                        logger.info("Bilibili 凭据已自动刷新。")
                        if on_refreshed:
                            await on_refreshed(self.get_credential_dict())
            except Exception as e:
                logger.error(f"自动刷新 Bilibili 凭据失败: {e}")

            # 每 1 小时检查一次
            await asyncio.sleep(3600)

    async def get_user(self, uid: int) -> user.User:
        """
        根据UID获取一个 User 对象。
        """
        return user.User(uid=uid, credential=self.credential)

    async def get_video_info(self, bvid: str) -> Optional[Dict[str, Any]]:
        """
        获取视频的详细信息和在线观看人数。
        """
        try:
            v = video.Video(bvid=bvid)
            info = await v.get_info()
            online = await v.get_online()
            return {"info": info, "online": online}
        except Exception as e:
            logger.error(f"获取视频信息失败 (BVID: {bvid}): {e}")
            return None

    async def get_latest_dynamics(self, uid: int) -> Optional[Dict[str, Any]]:
        """
        获取用户的最新动态。
        """
        try:
            u: user.User = await self.get_user(uid)
            return await u.get_dynamics_new()
        except Exception as e:
            logger.error(f"获取用户动态失败 (UID: {uid}): {e}")
            return None

    async def get_live_info(self, uid: int) -> Optional[Dict[str, Any]]:
        """
        获取用户的直播间信息。
        DEPRECATED: 该方法已弃用，据反馈易引起412错误
        """
        try:
            u: user.User = await self.get_user(uid)
            # 上游接口同u.get_user_info，即"https://api.bilibili.com/x/space/wbi/acc/info"，412的诱因
            return await u.get_live_info()
        except Exception as e:
            logger.error(f"获取直播间信息失败 (UID: {uid}): {e}")
            return None

    async def get_live_info_by_uids(self, uids: list[int]) -> Optional[Dict[str, Any]]:
        API_CONFIG = {
            "url": "https://api.live.bilibili.com/room/v1/Room/get_status_info_by_uids",
            "method": "GET",
            "verify": False,
            "params": {"uids[]": "list<int>: 主播uid列表"},
            "comment": "通过主播uid列表获取直播间状态信息（是否在直播、房间号等）",
        }
        params: Dict[str, list[int]] = {"uids[]": uids}
        resp = await Api(**API_CONFIG, no_csrf=True).update_params(**params).result
        if not isinstance(resp, dict) or not resp:
            return None
        live_room = next(iter(resp.values()))
        return live_room

    async def get_user_info(self, uid: int) -> Tuple[Dict[str, Any] | None, str]:
        """
        获取用户的基本信息。
        """
        try:
            u: user.User = await self.get_user(uid)
            info = await u.get_user_info()
            return info, ""
        except Exception as e:
            if "code" in e.args[0] and e.args[0]["code"] == -404:
                logger.warning(f"无法找到用户 (UID: {uid})")
                return None, "啥都木有 (´;ω;`)"
            else:
                logger.error(f"获取用户信息失败 (UID: {uid}): {e}")
                return None, f"获取 UP 主信息失败: {str(e)}"

    async def b23_to_bv(self, url: str) -> Optional[str]:
        """
        b23短链转换为原始链接
        """
        headers: Dict[str, str] = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(
                    url=url, headers=headers, allow_redirects=False, timeout=10
                ) as response:
                    if 300 <= response.status < 400:
                        location_url: str | None = response.headers.get("Location")
                        if location_url:
                            base_url: str = location_url.split("?", 1)[0]
                            return base_url
            except Exception as e:
                logger.error(f"解析b23链接失败 (URL: {url}): {e}")
                return url
