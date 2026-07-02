"""add prompt snapshots

Revision ID: 36b73e58f8a1
Revises: 7978c738915a
Create Date: 2026-07-02
"""

from typing import Sequence, Union
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "36b73e58f8a1"
down_revision: Union[str, Sequence[str], None] = "7978c738915a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "narrative_versions",
        sa.Column("prompt_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "script_versions",
        sa.Column("prompt_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )

    prompt_components = sa.table(
        "prompt_components",
        sa.column("id", sa.String),
        sa.column("category", sa.String),
        sa.column("name", sa.String),
        sa.column("description", sa.Text),
        sa.column("prompt_text", sa.Text),
        sa.column("is_builtin", sa.Boolean),
        sa.column("created_by", sa.String),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    now = datetime.now(timezone.utc)
    op.bulk_insert(
        prompt_components,
        [
            {
                "id": "b2c3d4e5-0001-4000-8000-000000000001",
                "category": "narrative_style",
                "name": "情境驱动知识叙事",
                "description": "先让观众进入具体问题，再通过证据和机制完成认知反转",
                "prompt_text": """【叙事风格：情境驱动知识叙事】

以一个观众能立即代入的具体处境、选择或冲突开场，不要先介绍术语、背景或定义。开头先让观众形成直觉判断，随后用事实、实验或反例制造认知反转，再解释背后的机制。

叙事推进遵循“发生了什么 → 直觉为什么会判断错 → 证据说明什么 → 机制如何运作 → 现实中怎么做”。抽象概念必须先通过人物、行为、空间关系或可观察结果呈现，再给出概念名称。

旁白使用自然、清晰、有画面感的现代口语。每句话只承担一个主要信息，不重复画面已经明确表达的内容，不使用空洞的过渡句、连续反问或夸张煽动。关键结论允许短句和停顿，形成认知落点。

保持可信和克制：不把相关性说成因果，不为戏剧效果歪曲实验结论；有争议或依赖条件的观点要明确边界。

结尾不要泛泛升华，应回到开头的具体处境，给出一个观众能够记住并执行的判断原则或行动方法。""",
                "is_builtin": True,
                "created_by": None,
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": "b2c3d4e5-0001-4000-8000-000000000002",
                "category": "pacing",
                "name": "高留存标准节奏（2.5分钟）",
                "description": "约150秒，每2～4秒产生一次有效信息或视觉变化",
                "prompt_text": """【叙事节奏：高留存标准节奏】

目标成片时长为 140～170 秒，旁白总字数控制在 550～700 个中文字符，预计语速约为每秒 4.0～4.8 个中文字符。不要仅通过增加镜头数量控制时长。

全片建议 12～16 个镜头。普通镜头承担一个明确论点或过程，旁白通常为 25～45 个中文字符；复杂机制可以更长，但应拆成连续的语义阶段。纯标题镜头应极短，不得用长旁白停留在标题页。

前 6 秒必须出现具体问题、异常结果或需要观众判断的选择；前 20 秒内完成第一次信息反转或证据揭示。每 20～35 秒形成一次段落推进：新证据、新机制、新反例或新应用。

保持信息密度变化：冲突与证据段落更快，机制解释段落适度放缓，关键数字和结论前后允许短暂停顿。删除不增加信息的铺垫、同义重复、预告式句子和泛泛总结。

每个镜头内部应持续推进，约每 2～4 秒出现一次有意义的新信息、关系变化或视觉结果；变化必须服务理解，不能依赖无意义装饰维持热闹。""",
                "is_builtin": True,
                "created_by": None,
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": "b2c3d4e5-0001-4000-8000-000000000003",
                "category": "scene_structure",
                "name": "情境—证据—机制—行动",
                "description": "从具体冲突切入，以证据反转，解释机制后回到行动",
                "prompt_text": """【内容结构：情境—证据—机制—行动】

第一段“情境与下注”（约全片 0%～12%）：直接呈现一个具体人物、处境或选择，让观众在两个结果之间形成直觉判断。不要先展示视频标题、术语定义或作者介绍。

第二段“结果与证据”（约全片 12%～30%）：尽快揭示反直觉结果，并用一个最有说服力的实验、数据、案例或对照支撑。证据必须说明比较对象、关键数字和结论边界。

第三段“机制拆解”（约全片 30%～68%）：将核心机制拆成不超过三个相互衔接的步骤。每一步先展示可观察变化，再命名概念。优先表现因果链、状态变化、角色关系和数量变化，不连续堆叠定义。

第四段“现实迁移”（约全片 68%～88%）：回到一个与观众有关的现实场景，对比常见错误做法和更有效做法。尽量复用开头场景，让知识发生可见的行为变化。

第五段“行动与回扣”（约全片 88%～100%）：给出不超过三条、动作明确、可以立即执行的方法。最后一句回扣开头的问题，形成闭环，不另起空泛升华。

段落边界应通过证据揭晓、关系反转、视觉锚点变形或场景复用自然过渡，不使用孤立章节页反复打断叙事。""",
                "is_builtin": True,
                "created_by": None,
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": "b2c3d4e5-0001-4000-8000-000000000004",
                "category": "color_scheme",
                "name": "高对比亮底认知紫",
                "description": "延续紫色品牌感，提高主体对比与移动端可读性",
                "prompt_text": """【视觉系统：高对比亮底认知紫】

基础背景：暖白 #FBFAFF；允许使用极浅紫 #F3EEFF 构建局部区域，但不得让整片长期处于同一低对比淡紫色。

主要文字：深墨紫 #211936；辅助文字：灰紫 #756A91。核心文字与背景必须保持清晰对比，避免大面积使用浅紫小字。

品牌主色：认知紫 #6C4FD4；高亮紫 #8B6FE8。主色用于当前叙事焦点、关键路径和核心概念，不把所有节点同时染成主色。

语义颜色：风险/错误 #E85353；警示/待行动 #F39A3D；理性/解释 #258E9B；正确/完成 #25A85A；人物/情境辅助 #D96C9D。

结构颜色：浅分隔线 #D9D0EE；深结构线 #51456F。

每个画面确定一个主导色和最多两个辅助语义色。红色只表达风险、错误或阻断，绿色只表达正确、完成或有效行动，不作纯装饰。

关键主体应具有足够面积和明度对比；核心数字、结论和当前动作必须在手机尺寸下优先可读。背景装饰降低透明度和复杂度，不与主体争夺注意力。""",
                "is_builtin": True,
                "created_by": None,
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": "b2c3d4e5-0001-4000-8000-000000000005",
                "category": "animation_style",
                "name": "语义驱动动态图解",
                "description": "动画解释关系和过程，持续推进并避免模板化进场",
                "prompt_text": """【动画系统：语义驱动动态图解】

动画的首要职责是解释知识变化，而不是装饰页面。每次主要运动都必须对应旁白中的一个新事实、关系、数量、状态或行动结果。

镜头内部采用“建立对象 → 发生变化 → 显示结果”的推进方式。不要在镜头开始时一次性展示全部元素，也不要只播放进场动画后长时间静止。前一阶段的视觉结果应尽量成为后一阶段的输入，通过移动、连接、分裂、聚合、替换、对比或强调持续演化。

根据内容选择视觉语法：人物与行为使用情境构图、视线、距离和行动路径；原因与结果使用方向明确的因果链；数量变化使用增长、分配、聚合和比例变化；正误判断使用同一场景的前后对照；实验与证据使用大数字、清晰对照和必要来源标识；抽象机制使用状态变化，不用一组同质圆点代替所有概念。

构图避免长期居中和过度留白。核心主体通常占画面主要视觉区域；根据叙事在全屏情境、左右对比、局部特写、流程关系和数据证据等版式之间切换。版式变化服务段落层级，不随机切换。

转场优先复用视觉锚点：让上一画面的核心人物、数字、图形或路径变形成下一画面的解释对象。只有在主题真正切换时才整体淡出重建。

强调动作应短而明确，关键结果出现后留出可阅读时间。持续运动必须有语义，禁止用无意义循环、漂浮、呼吸或重复脉冲填满旁白时长。

装饰保持克制。光晕、阴影、弹性和粒子只用于突出当前重点，不作为所有镜头的统一模板。全片保持字体、圆角、线宽和图标语言一致。""",
                "is_builtin": True,
                "created_by": None,
                "created_at": now,
                "updated_at": now,
            },
        ],
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM prompt_components "
            "WHERE id IN ("
            "'b2c3d4e5-0001-4000-8000-000000000001',"
            "'b2c3d4e5-0001-4000-8000-000000000002',"
            "'b2c3d4e5-0001-4000-8000-000000000003',"
            "'b2c3d4e5-0001-4000-8000-000000000004',"
            "'b2c3d4e5-0001-4000-8000-000000000005'"
            ")"
        )
    )
    op.drop_column("script_versions", "prompt_snapshot")
    op.drop_column("narrative_versions", "prompt_snapshot")
