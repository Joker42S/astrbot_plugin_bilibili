import json
import os
from typing import Dict, List, Any, Optional, Tuple
from astrbot.api import logger
from astrbot.api.star import StarTools
from .constant import DEFAULT_CFG, DATA_PATH
from .subscription import Subscription


class DataManager:
    """
    负责管理插件的订阅数据，包括加载、保存和修改。
    """

    def __init__(self):
        standard_data_path = os.path.join(
            StarTools.get_data_dir(plugin_name="astrbot_plugin_bilibili"),
            "astrbot_plugin_bilibili.json",
        )
        if os.path.exists(DATA_PATH) and not os.path.exists(standard_data_path):
            # 复制旧数据文件到标准路径
            os.makedirs(os.path.dirname(standard_data_path), exist_ok=True)
            with open(DATA_PATH, "r", encoding="utf-8-sig") as src:
                with open(standard_data_path, "w", encoding="utf-8") as dst:
                    dst.write(src.read())
            logger.info(f"已将旧数据文件迁移到标准路径: {standard_data_path}")
        self.path = standard_data_path
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

    def get_all_subscriptions(self) -> Dict[str, List[Subscription]]:
        """
        获取所有的订阅列表。
        """
        result: Dict[str, List[Subscription]] = {}
        for sub_user, entries in self.data.get("bili_sub_list", {}).items():
            result[sub_user] = [Subscription.from_dict(entry) for entry in entries]
        return result

    def get_subscriptions_by_user(
        self, sub_user: str
    ) -> Optional[List[Subscription]]:
        """
        根据 sub_user 获取其订阅的UP主列表。
        sub_user: 订阅用户的唯一标识, 形如 "aipcqhttp:GroupMessage:123456"
        """
        return self.get_all_subscriptions().get(sub_user)

    def _get_subscription_entry(
        self, sub_user: str, uid: int
    ) -> Tuple[Optional[Subscription], Optional[int]]:
        user_subs = self.data.get("bili_sub_list", {}).get(sub_user)
        if not user_subs:
            return None, None
        for idx, sub in enumerate(user_subs):
            if str(sub.get("uid")) == str(uid):
                return Subscription.from_dict(sub), idx
        return None, None

    def get_subscription(self, sub_user: str, uid: int) -> Optional[Subscription]:
        """
        获取特定用户对特定UP主的订阅信息。
        """
        subscription, _ = self._get_subscription_entry(sub_user, uid)
        return subscription

    def _replace_subscription(
        self, sub_user: str, index: int, subscription: Subscription
    ) -> None:
        self.data.setdefault("bili_sub_list", {}).setdefault(sub_user, [])
        self.data["bili_sub_list"][sub_user][index] = subscription.to_dict()

    async def add_subscription(self, sub_user: str, subscription: Subscription):
        """
        为用户添加一条新的订阅。
        """
        subscription.ensure_cache_limit()
        bili_sub_list = self.data.setdefault("bili_sub_list", {})
        bili_sub_list.setdefault(sub_user, [])
        bili_sub_list[sub_user].append(subscription.to_dict())
        await self.save()

    async def update_subscription(
        self, sub_user: str, uid: int, filter_types: List[str], filter_regex: List[str]
    ):
        """
        更新一个已存在的订阅的过滤条件。
        """
        subscription, index = self._get_subscription_entry(sub_user, uid)
        if subscription is not None and index is not None:
            subscription.filter_types = list(filter_types)
            subscription.filter_regex = list(filter_regex)
            self._replace_subscription(sub_user, index, subscription)
            await self.save()
            return True
        return False

    async def update_last_dynamic_id(self, sub_user: str, uid: int, dyn_id: str):
        """
        更新订阅的最新动态ID。
        """
        subscription, index = self._get_subscription_entry(sub_user, uid)
        if subscription is not None and index is not None:
            subscription.record_dynamic(dyn_id)
            self._replace_subscription(sub_user, index, subscription)
            await self.save()

    async def update_live_status(self, sub_user: str, uid: int, is_live: bool):
        """
        更新特定订阅的直播状态。
        """
        subscription, index = self._get_subscription_entry(sub_user, uid)
        if subscription is not None and index is not None:
            subscription.is_live = is_live
            self._replace_subscription(sub_user, index, subscription)
            await self.save()

    async def remove_subscription(self, sub_user: str, uid: int) -> bool:
        """
        移除一条订阅。
        """
        bili_sub_list = self.data.get("bili_sub_list", {})
        user_subs = bili_sub_list.get(sub_user)
        if not user_subs:
            return False

        idx_to_remove = None
        for idx, sub in enumerate(user_subs):
            if str(sub.get("uid")) == str(uid):
                idx_to_remove = idx
                break

        if idx_to_remove is not None:
            user_subs.pop(idx_to_remove)
            # 如果该用户已无任何订阅，可以选择移除该用户键
            if not user_subs:
                bili_sub_list.pop(sub_user, None)
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
