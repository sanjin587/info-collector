"""
多维表格的表结构定义
每个表定义包含表名和字段列表
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


# ============================================================
# 字段类型常量
# ============================================================
class FieldType:
    """飞书多维表格字段类型"""
    TEXT = 1           # 文本
    NUMBER = 2         # 数字
    DATETIME = 5       # 日期
    URL = 15           # 链接（新版用 15）
    SINGLE_SELECT = 3  # 单选
    MULTI_SELECT = 4   # 多选


@dataclass
class FieldDef:
    """字段定义"""
    name: str
    type: int
    property: Optional[Dict] = None  # 字段属性（如单选选项）

    def to_api_dict(self) -> Dict:
        """转换为飞书 API 格式"""
        result = {
            "field_name": self.name,
            "type": self.type,
        }
        if self.property:
            result["property"] = self.property
        return result


@dataclass
class TableDef:
    """表定义"""
    name: str
    fields: List[FieldDef] = field(default_factory=list)


# ============================================================
# 表1: 文章采集（Articles）
# ============================================================
ARTICLES_TABLE = TableDef(
    name="文章采集",
    fields=[
        FieldDef(name="标题", type=FieldType.TEXT),
        FieldDef(name="平台", type=FieldType.TEXT),
        FieldDef(name="作者", type=FieldType.TEXT),
        FieldDef(name="笔记链接", type=FieldType.URL),
        FieldDef(name="发布时间", type=FieldType.DATETIME),
        FieldDef(name="内容摘要", type=FieldType.TEXT),
        FieldDef(name="关键词", type=FieldType.MULTI_SELECT),
        FieldDef(name="点赞数", type=FieldType.NUMBER),
        FieldDef(name="收藏数", type=FieldType.NUMBER),
        FieldDef(name="评论数", type=FieldType.NUMBER),
        FieldDef(name="互动总量", type=FieldType.NUMBER),
        FieldDef(name="爆款指数", type=FieldType.NUMBER),
        FieldDef(name="采集时间", type=FieldType.DATETIME),
        FieldDef(
            name="状态",
            type=FieldType.SINGLE_SELECT,
            property={
                "options": [
                    {"name": "待分析", "color": 0},
                    {"name": "已分析", "color": 1},
                    {"name": "已归档", "color": 2},
                ]
            },
        ),
    ],
)

# 关键词选项（在写入时动态创建，这里仅做参考）
KEYWORD_OPTIONS = [
    "AI工具", "大模型", "ChatGPT", "AIGC", "AI绘画",
    "AI写作", "AI编程", "AI视频", "AI音乐", "深度学习",
    "机器学习", "提示词", "LangChain", "RAG", "Agent",
    "多模态", "Sora", "Claude", "Copilot", "Midjourney",
]


# ============================================================
# 表2: 热点主题（Hot Topics）
# ============================================================
HOT_TOPICS_TABLE = TableDef(
    name="热点主题",
    fields=[
        FieldDef(name="主题名称", type=FieldType.TEXT),
        FieldDef(name="相关文章", type=FieldType.TEXT),
        FieldDef(name="热度指数", type=FieldType.NUMBER),
        FieldDef(
            name="趋势方向",
            type=FieldType.SINGLE_SELECT,
            property={
                "options": [
                    {"name": "上升", "color": 0},
                    {"name": "稳定", "color": 1},
                    {"name": "下降", "color": 2},
                ]
            },
        ),
        FieldDef(name="首次发现时间", type=FieldType.DATETIME),
        FieldDef(name="最近更新时间", type=FieldType.DATETIME),
    ],
)


# ============================================================
# 表3: 内容框架分析（Content Framework）
# ============================================================
CONTENT_FRAMEWORK_TABLE = TableDef(
    name="内容框架分析",
    fields=[
        FieldDef(name="笔记标题", type=FieldType.TEXT),
        FieldDef(
            name="Hook 类型",
            type=FieldType.SINGLE_SELECT,
            property={
                "options": [
                    {"name": "痛点提问", "color": 0},
                    {"name": "惊人数据", "color": 1},
                    {"name": "对比冲突", "color": 2},
                    {"name": "故事开场", "color": 3},
                    {"name": "利益前置", "color": 4},
                ]
            },
        ),
        FieldDef(name="Hook 原文", type=FieldType.TEXT),
        FieldDef(
            name="主体结构",
            type=FieldType.SINGLE_SELECT,
            property={
                "options": [
                    {"name": "清单列表", "color": 0},
                    {"name": "对比分析", "color": 1},
                    {"name": "步骤教程", "color": 2},
                    {"name": "故事叙述", "color": 3},
                    {"name": "观点论证", "color": 4},
                ]
            },
        ),
        FieldDef(name="内容框架", type=FieldType.TEXT),
        FieldDef(name="Key Takeaway", type=FieldType.TEXT),
        FieldDef(name="互动引导", type=FieldType.TEXT),
        FieldDef(name="爆款要素", type=FieldType.TEXT),
        FieldDef(
            name="情绪基调",
            type=FieldType.SINGLE_SELECT,
            property={
                "options": [
                    {"name": "焦虑", "color": 0},
                    {"name": "希望", "color": 1},
                    {"name": "好奇", "color": 2},
                    {"name": "实用", "color": 3},
                    {"name": "共鸣", "color": 4},
                ]
            },
        ),
    ],
)


# ============================================================
# 所有表定义
# ============================================================
ALL_TABLES = [ARTICLES_TABLE, HOT_TOPICS_TABLE, CONTENT_FRAMEWORK_TABLE]


def get_table_by_name(name: str) -> Optional[TableDef]:
    """根据表名查找表定义"""
    for table in ALL_TABLES:
        if table.name == name:
            return table
    return None
