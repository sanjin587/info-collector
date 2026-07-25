"""
飞书多维表格操作
- 自动建表（检测表是否存在，不存在则创建）
- 批量写入记录
- 去重写入
- 更新记录
"""
from typing import Any, Dict, List, Optional

from utils.logger import logger
from .client import FeishuClient
from .schema import (
    ALL_TABLES,
    ARTICLES_TABLE,
    CONTENT_FRAMEWORK_TABLE,
    HOT_TOPICS_TABLE,
    FieldDef,
    FieldType,
    get_table_by_name,
)


class BitableManager:
    """多维表格管理器"""

    def __init__(self, client: FeishuClient, base_token: str):
        self.client = client
        self.base_token = base_token
        # 缓存 table_id: {表名: table_id}
        self._table_ids: Dict[str, str] = {}

    # ── 表管理 ──────────────────────────────────────────────

    def _api_path(self, *parts: str) -> str:
        """构建 API 路径"""
        return f"/bitable/v1/apps/{self.base_token}/" + "/".join(parts)

    def ensure_tables(self):
        """确保所有需要的表都存在，不存在则自动创建"""
        existing_tables = self._list_tables()
        existing_names = {t["name"]: t["table_id"] for t in existing_tables}
        self._table_ids = existing_names

        for table_def in ALL_TABLES:
            if table_def.name in existing_names:
                logger.info(f"表已存在: {table_def.name} (id={existing_names[table_def.name]})")
                # 检查字段是否匹配，尝试补全新字段
                self._ensure_fields(table_def, existing_names[table_def.name])
            else:
                logger.info(f"正在创建表: {table_def.name}")
                table_id = self._create_table(table_def)
                if table_id:
                    self._table_ids[table_def.name] = table_id

    def _list_tables(self) -> List[Dict]:
        """获取 base 下的所有表"""
        try:
            result = self.client.get(self._api_path("tables"))
            return result.get("data", {}).get("items", [])
        except Exception as e:
            logger.error(f"获取表列表失败: {e}")
            return []

    def _create_table(self, table_def) -> Optional[str]:
        """创建新表"""
        try:
            payload = {
                "table": {
                    "name": table_def.name,
                    "fields": [f.to_api_dict() for f in table_def.fields],
                }
            }
            result = self.client.post(self._api_path("tables"), json_data=payload)
            table_id = result.get("data", {}).get("table_id")
            if table_id:
                logger.info(f"表 '{table_def.name}' 创建成功 (id={table_id})")
                return table_id
            else:
                logger.error(f"创建表 '{table_def.name}' 返回无 table_id")
                return None
        except Exception as e:
            logger.error(f"创建表 '{table_def.name}' 失败: {e}")
            return None

    def _ensure_fields(self, table_def, table_id: str):
        """检查并补全缺失的字段（首次运行时可能字段不全）"""
        try:
            result = self.client.get(self._api_path("tables", table_id, "fields"))
            existing_fields = {f["field_name"]: f for f in result.get("data", {}).get("items", [])}

            for field_def in table_def.fields:
                if field_def.name not in existing_fields:
                    logger.info(f"  补充缺失字段: {field_def.name}")
                    self._create_field(table_id, field_def)
        except Exception as e:
            logger.warning(f"检查字段时出错: {e}")

    def _create_field(self, table_id: str, field_def: FieldDef):
        """在表中创建新字段"""
        try:
            self.client.post(
                self._api_path("tables", table_id, "fields"),
                json_data=field_def.to_api_dict(),
            )
        except Exception as e:
            logger.warning(f"创建字段 '{field_def.name}' 失败: {e}")

    def get_table_id(self, table_name: str) -> Optional[str]:
        """获取表 ID"""
        return self._table_ids.get(table_name)

    # ── 记录操作 ────────────────────────────────────────────

    def list_records(self, table_name: str, page_size: int = 500) -> List[Dict]:
        """列出表中的所有记录"""
        table_id = self.get_table_id(table_name)
        if not table_id:
            logger.error(f"表 '{table_name}' 不存在")
            return []

        try:
            records = []
            page_token = None

            while True:
                params = {"page_size": page_size}
                if page_token:
                    params["page_token"] = page_token

                result = self.client.get(
                    self._api_path("tables", table_id, "records"),
                    params=params,
                )
                data = result.get("data", {})
                items = data.get("items", [])
                records.extend(items)

                if not data.get("has_more"):
                    break
                page_token = data.get("page_token")

            return records

        except Exception as e:
            logger.error(f"查询记录失败 [{table_name}]: {e}")
            return []

    def create_record(self, table_name: str, fields: Dict[str, Any]) -> Optional[str]:
        """创建一条记录，返回 record_id"""
        table_id = self.get_table_id(table_name)
        if not table_id:
            logger.error(f"表 '{table_name}' 不存在")
            return None

        try:
            payload = {"fields": fields}
            result = self.client.post(
                self._api_path("tables", table_id, "records"),
                json_data=payload,
            )
            record_id = result.get("data", {}).get("record_id")
            return record_id
        except Exception as e:
            logger.error(f"创建记录失败 [{table_name}]: {e}")
            return None

    def batch_create_records(self, table_name: str, records_fields: List[Dict[str, Any]]) -> int:
        """批量创建记录，返回成功数

        飞书 API 单次最多 10 条，自动分批。
        """
        if not records_fields:
            return 0

        table_id = self.get_table_id(table_name)
        if not table_id:
            logger.error(f"表 '{table_name}' 不存在")
            return 0

        # 每批 10 条
        success_count = 0
        batch_size = 10

        for i in range(0, len(records_fields), batch_size):
            batch = records_fields[i:i + batch_size]
            try:
                payload = {"records": [{"fields": fields} for fields in batch]}
                result = self.client.post(
                    self._api_path("tables", table_id, "records", "batch_create"),
                    json_data=payload,
                )
                data = result.get("data", {})
                records = data.get("records", [])
                success_count += len(records)

                if len(records) < len(batch):
                    logger.warning(f"批处理 {i//batch_size + 1}: 成功 {len(records)}/{len(batch)} 条")

            except Exception as e:
                logger.error(f"批量创建记录失败 (批次 {i//batch_size + 1}): {e}")

        logger.info(f"批量写入 '{table_name}': 成功 {success_count}/{len(records_fields)} 条")
        return success_count

    def update_record(self, table_name: str, record_id: str, fields: Dict[str, Any]) -> bool:
        """更新一条记录"""
        table_id = self.get_table_id(table_name)
        if not table_id:
            return False

        try:
            payload = {"fields": fields}
            self.client.put(
                self._api_path("tables", table_id, "records", record_id),
                json_data=payload,
            )
            return True
        except Exception as e:
            logger.error(f"更新记录失败 [{table_name}/{record_id}]: {e}")
            return False

    # ── 高级操作 ────────────────────────────────────────────

    def get_existing_urls(self, table_name: str) -> set:
        """获取表中已有的笔记链接集合（用于去重）"""
        records = self.list_records(table_name)
        urls = set()
        for record in records:
            fields = record.get("fields", {})
            url_field = fields.get("笔记链接", "")
            if isinstance(url_field, dict):
                url = url_field.get("link", "")
            else:
                url = str(url_field) if url_field else ""
            if url:
                urls.add(url)
        logger.info(f"表 '{table_name}' 已有 {len(urls)} 条记录")
        return urls

    def dedup_and_insert(self, table_name: str, records: List[Dict[str, Any]]) -> int:
        """去重后插入记录，返回新增数"""
        existing_urls = self.get_existing_urls(table_name) if "链接" in table_name else set()
        # 对于"文章采集"表，用"笔记链接"去重

        new_records = []
        for rec in records:
            url_field = rec.get("笔记链接", "")
            url = url_field.get("link", "") if isinstance(url_field, dict) else str(url_field) if url_field else ""
            if not url or url not in existing_urls:
                new_records.append(rec)
                if url:
                    existing_urls.add(url)

        if not new_records:
            logger.info(f"表 '{table_name}': 无新记录需要写入")
            return 0

        logger.info(f"表 '{table_name}': {len(new_records)} 条新记录待写入（已去重）")
        return self.batch_create_records(table_name, new_records)

    def write_article(self, article: Dict[str, Any]) -> Optional[str]:
        """写入单篇文章记录"""
        fields = self._article_to_fields(article)
        return self.create_record("文章采集", fields)

    def batch_write_articles(self, articles: List[Dict[str, Any]]) -> int:
        """批量写入文章（自动去重）"""
        records = []
        for article in articles:
            records.append(self._article_to_fields(article))
        return self.dedup_and_insert("文章采集", records)

    def write_hot_topic(self, topic: Dict[str, Any]) -> Optional[str]:
        """写入热点主题"""
        from datetime import datetime

        def date_to_ts(date_str: str) -> int:
            """将 YYYY-MM-DD 转为毫秒时间戳"""
            if not date_str:
                return 0
            try:
                dt = datetime.strptime(date_str, "%Y-%m-%d")
                return int(dt.timestamp() * 1000)
            except (ValueError, TypeError):
                return 0

        fields = {
            "主题名称": topic.get("topic_name", ""),
            "相关文章": "\n".join(topic.get("related_articles", [])),
            "热度指数": topic.get("heat_score", 0),
            "趋势方向": topic.get("trend", "稳定"),
            "首次发现时间": date_to_ts(topic.get("first_seen", "")),
            "最近更新时间": date_to_ts(topic.get("last_updated", "")),
        }
        return self.create_record("热点主题", fields)

    def write_content_framework(self, analysis: Dict[str, Any]) -> Optional[str]:
        """写入内容框架分析"""
        fields = self._framework_to_fields(analysis)
        return self.create_record("内容框架分析", fields)

    def batch_write_frameworks(self, analyses: List[Dict[str, Any]]) -> int:
        """批量写入内容框架分析"""
        records = []
        for analysis in analyses:
            records.append(self._framework_to_fields(analysis))
        return self.batch_create_records("内容框架分析", records)

    # ── 字段转换 ────────────────────────────────────────────

    @staticmethod
    def _article_to_fields(article: Dict[str, Any]) -> Dict[str, Any]:
        """将文章字典转换为飞书字段格式"""
        # URL 字段：飞书要求传入对象格式
        url = article.get("url", "")
        url_field = {"link": url, "text": article.get("title", "")} if url else ""

        # 日期字段：飞书要求传入毫秒时间戳
        publish_ts = article.get("publish_timestamp", 0)
        if not publish_ts:
            # 尝试从 publish_date 字符串解析
            publish_ts = 0

        crawl_ts = 0
        crawl_time = article.get("crawl_time", "")
        if crawl_time:
            try:
                from datetime import datetime
                dt = datetime.strptime(crawl_time, "%Y-%m-%d %H:%M")
                crawl_ts = int(dt.timestamp() * 1000)
            except (ValueError, TypeError):
                crawl_ts = int(datetime.now().timestamp() * 1000)

        # 计算互动总量和爆款指数
        likes = int(article.get("likes", 0))
        favorites = int(article.get("favorites", 0))
        comments = int(article.get("comments", 0))
        total_interactions = likes + favorites + comments
        # 收藏权重最高(3x) → 收藏是小红书最强爆款信号
        # 评论次之(2x) → 讨论度高说明话题性强
        # 点赞基础(1x)
        viral_score = likes + favorites * 3 + comments * 2

        fields = {
            "标题": article.get("title", ""),
            "平台": article.get("platform", ""),
            "作者": article.get("author", ""),
            "笔记链接": url_field,
            "发布时间": publish_ts if publish_ts else "",
            "内容摘要": article.get("summary", ""),
            "关键词": article.get("keywords", []),
            "点赞数": likes,
            "收藏数": favorites,
            "评论数": comments,
            "互动总量": total_interactions,
            "爆款指数": viral_score,
            "采集时间": crawl_ts if crawl_ts else "",
            "状态": "待分析",
        }
        # 清理空值
        return {k: v for k, v in fields.items() if v != "" and v != [] and v != 0}

    @staticmethod
    def _framework_to_fields(analysis: Dict[str, Any]) -> Dict[str, Any]:
        """将框架分析字典转换为飞书字段格式"""
        fields = {
            "笔记标题": analysis.get("title", ""),
            "Hook 类型": analysis.get("hook_type", ""),
            "Hook 原文": analysis.get("hook_text", ""),
            "主体结构": analysis.get("structure_type", ""),
            "内容框架": analysis.get("framework", ""),
            "Key Takeaway": analysis.get("takeaway", ""),
            "互动引导": analysis.get("engagement_prompt", ""),
            "爆款要素": analysis.get("viral_factors", ""),
            "情绪基调": analysis.get("emotion_tone", ""),
        }
        return {k: v for k, v in fields.items() if v != "" and v is not None}
