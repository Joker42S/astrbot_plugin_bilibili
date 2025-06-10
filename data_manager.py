import json
import os
from typing import Dict, List, Any, Optional
from astrbot.api import logger
from .constant import DATA_PATH, DEFAULT_CFG


class DataManager:
    """
    负责管理插件的订阅数据，包括加载、保存和修改。
    """

    def __init__(self, path: str = DATA_PATH):
        self.path = path
        self.data = self._load_data()

    def _load_data(self) -> Dict[str, Any]:
        """
        从 JSON 文件加载数据。如果文件不存在，则创建并使用默认配置。
        """
        if not os.path.exists(self.path):
            logger.info(f"数据文件不存在，将创建于: {self.path}")
            # 确保目录存在
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(self.path, "w", encoding="utf-8-sig") as f:
                json.dump(DEFAULT_CFG, f, ensure_ascii=False, indent=4)
            return DEFAULT_CFG

        with open(self.path, "r", encoding="utf-8-sig") as f:
            return json.load(f)

    async def save(self):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def get_all_subscriptions(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        获取所有的订阅列表。
        """
        return self.data.get("bili_sub_list", {})

    def get_subscriptions_by_user(
        self, sub_user: str
    ) -> Optional[List[Dict[str, Any]]]:
        """
        根据 sub_user 获取其订阅的UP主列表。
        sub_user: 订阅用户的唯一标识, 形如 "aipcqhttp:GroupMessage:123456"
        """
        return self.get_all_subscriptions().get(sub_user)

    def get_subscription(self, sub_user: str, uid: int) -> Optional[Dict[str, Any]]:
        """
        获取特定用户对特定UP主的订阅信息。
        """
        user_subs = self.get_subscriptions_by_user(sub_user)
        if user_subs:
            for sub in user_subs:
                if sub.get("uid") == uid:
                    return sub
        return None

    async def add_subscription(self, sub_user: str, sub_data: Dict[str, Any]):
        """
        为用户添加一条新的订阅。
        """
        all_subs = self.get_all_subscriptions()
        if sub_user not in all_subs:
            all_subs[sub_user] = []

        all_subs[sub_user].append(sub_data)
        await self.save()

    async def update_subscription(
        self, sub_user: str, uid: int, filter_types: List[str], filter_regex: List[str]
    ):
        """
        更新一个已存在的订阅的过滤条件。
        """
        sub = self.get_subscription(sub_user, uid)
        if sub:
            sub["filter_types"] = filter_types
            sub["filter_regex"] = filter_regex
            await self.save()
            return True
        return False

    async def update_last_dynamic_id(self, sub_user: str, uid: int, dyn_id: str):
        """
        更新订阅的最新动态ID。
        """
        sub = self.get_subscription(sub_user, uid)
        if sub:
            sub["last"] = dyn_id
            await self.save()

    async def update_live_status(self, sub_user: str, uid: int, is_live: bool):
        """
        更新特定订阅的直播状态。
        """
        sub = self.get_subscription(sub_user, uid)
        if sub:
            sub["is_live"] = is_live
            await self.save()

    async def remove_subscription(self, sub_user: str, uid: int) -> bool:
        """
        移除一条订阅。
        """
        user_subs = self.get_subscriptions_by_user(sub_user)
        if not user_subs:
            return False

        sub_to_remove = None
        for sub in user_subs:
            if sub.get("uid") == uid:
                sub_to_remove = sub
                break

        if sub_to_remove:
            user_subs.remove(sub_to_remove)
            # 如果该用户已无任何订阅，可以选择移除该用户键
            if not user_subs:
                del self.data["bili_sub_list"][sub_user]
            await self.save()
            return True

        return False

    async def remove_all_for_user(self, sid: str):
        """
        移除一个用户的所有订阅（用于管理员指令）。
        """
        candidate = []
        for sub_user in self.get_all_subscriptions():
            third = sub_user.split(":")[2]
            if third == str(sid) or sid == sub_user:
                candidate.append(sub_user)

        if not candidate:
            msg = "未找到订阅"
            return msg

        if len(candidate) == 1:
            self.data["bili_sub_list"].pop(candidate[0])
            await self.save()
            msg = f"删除 {sid} 订阅成功"
            return msg

        msg = "找到多个订阅者: " + ", ".join(candidate)
        return msg
