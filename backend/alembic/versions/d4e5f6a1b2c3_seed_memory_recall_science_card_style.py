"""seed_memory_recall_science_card_style

记忆唤醒·理科卡片：面向职场人复习初高中数理化的短视频风格家族。
竖屏 9:16，Manim 引擎，记忆钩子三段式叙事。

Revision ID: d4e5f6a1b2c3
Revises: a4d6b7e9c102
Create Date: 2026-07-08 12:00:00.000000

"""
from datetime import datetime, timezone
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "d4e5f6a1b2c3"
down_revision: Union[str, Sequence[str], None] = "a4d6b7e9c102"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


STYLE_COMPONENT_IDS = {
    "color_scheme":     uuid.UUID("b7a2f8c1-1004-4000-8000-000000000001"),
    "narrative_style":  uuid.UUID("b7a2f8c1-1004-4000-8000-000000000002"),
    "pacing":           uuid.UUID("b7a2f8c1-1004-4000-8000-000000000003"),
    "scene_structure":  uuid.UUID("b7a2f8c1-1004-4000-8000-000000000004"),
    "animation_style":  uuid.UUID("b7a2f8c1-1004-4000-8000-000000000005"),
}

STYLE_TEMPLATE_ID = uuid.UUID("b7a2f8c1-1004-4000-8000-0000000000ff")


def upgrade() -> None:
    """Seed the five components and bundle template of the memory-recall science card style."""
    now = datetime.now(timezone.utc)

    prompt_components_table = sa.table(
        "prompt_components",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("category", sa.String),
        sa.column("name", sa.String),
        sa.column("description", sa.Text),
        sa.column("prompt_text", sa.Text),
        sa.column("is_builtin", sa.Boolean),
        sa.column("created_by", sa.String),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )

    seeds = [
        {
            "id": STYLE_COMPONENT_IDS["color_scheme"],
            "category": "color_scheme",
            "name": "记忆唤醒·白底明亮知识卡片",
            "description": "纯白底、学科主色条带、明黄结论胶囊、竖屏三层卡片骨架与幽灵态残缺开场",
            "prompt_text": """【视觉系统：记忆唤醒·白底明亮知识卡片】

〇、画面规格（硬性要求）
竖屏 9:16，Manim 配置：config.pixel_height=1920, config.pixel_width=1080, config.frame_height=16。
全片统一此规格，禁止使用横屏或正方形比例。
安全区：顶部和底部各留 5%（约 0.8 frame 单位），避开手机状态栏与手势条。

一、背景与分区
- 主背景：纯白 #FFFFFF
- 卡片内分区底色：浅灰 #F4F6F9，用于需要区分的信息块背景
- 全片统一背景，不切换深色模式

二、学科主色（同一视频内固定，跨镜头不变）
- 数学：钴蓝 #2563EB
- 物理：橙红 #EA580C
- 化学：翠绿 #16A34A
视频开始时由选题学科决定本片主色，全片不混用其他学科色。

三、结论高亮色（语义固定，不得挪用）
- 底色：明黄 #FEF08A
- 文字：深灰 #1E293B
专用于每个镜头底部"结论胶囊"区域，是观众最重要的记忆锚点。

四、图解线条与标注
- 主线条/坐标轴：深灰 #1E293B，线宽 3-4px 等效
- 标注箭头：学科主色，粗细与主线条一致
- 辅助虚线：暖灰 #94A3B8

五、幽灵态（开场专用）
- 开场第一镜头中，待揭示的图解元素设为 fill_opacity=0.15
- 仅用于"残缺图解"开场，下一镜头用 FadeIn 补全
- 其他镜头不使用幽灵态（与暖白极简风格区分）

六、三层卡片骨架（每镜头必须具备）
- 顶层（画面顶部 6-10%）：学科主色色条带 + 本镜头主题短语（≤8 字）
- 主体区（画面中部 50-60%）：Manim 图解动画，逐步构建
- 底层（画面下方 15%）：明黄底结论胶囊，1 句核心结论（≤20 字）
三层缺一即为不合格镜头；开场"提问镜头"的底层可换为问号或"?"占位。

七、字体尺寸（竖屏手机可读）
- 顶部标题：font_size 等效 ≥52pt
- 图解标注：font_size 等效 ≥36pt
- 结论胶囊文字：font_size 等效 ≥40pt
- 手机小屏（<6寸）下所有文字须清晰可读，禁止出现需要放大才能看清的标注

八、用色纪律
- 同一视频学科主色固定，跨镜头不变
- 单镜头主色不超过 3 种（背景白 + 学科主色 + 结论黄）
- 色彩承载语义信息，禁止纯装饰性用色
- 同一概念跨镜头保持同色""",
            "is_builtin": True,
            "created_by": None,
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": STYLE_COMPONENT_IDS["narrative_style"],
            "category": "narrative_style",
            "name": "记忆唤醒·记忆钩子三段式",
            "description": "唤醒-重建-升华三段式，第二人称记忆钩子开场，残缺图解提问，语气像一起回忆而非重新教",
            "prompt_text": """【叙事风格：记忆唤醒·记忆钩子三段式】

一、核心气质
不是在教陌生知识，而是在帮观众找回遗忘的记忆。
语气像同龄人聊天："你肯定学过这个，只是忘了——来，咱们一起想想。"
亲切不说教，有趣不油腻，理科严谨但不学术腔。

二、三段式结构（叙事骨架）

第一段——唤醒（开场 1-2 镜头）
目标：让观众在 3 秒内产生"我学过这个！"的模糊记忆感。
- 用第二人称 + 具体课堂场景切入："还记得初中物理课吗？" / "这道题你当年做过。"
- 开场第一镜头必须显示残缺图解（核心元素用幽灵态隐去），配问题文字
  （"这里是什么，还记得吗？"），让观众先尝试主动回忆
- 不直接给答案，带着悬念进入第二段
- 禁止开场就把完整知识点全盘托出

第二段——重建（中间 3-5 镜头）
目标：一步步重新推导，让观众"哦对！就是这样！"
- 语气用"对，就是这一步" / "你想到了吗？" / "没错——"
- 每步推导在图解上逐步构建，旁白同步说明当步的含义
- 概念/公式名称在图解完成后才亮出（不提前给答案）
- 不假设观众记得任何细节，但不把观众当小白——他学过，只是忘了
- 每个知识点拆成最小步骤，每步对应一个镜头

第三段——升华（最后 1 镜头）
目标：让职场观众感到"这个知识其实还在用"。
- 给出超出课本的一句话现实延伸
  （"这个原理，就是你手机散热的底层逻辑" / "下次遇到这类问题，这个思路直接用"）
- 一句话，克制，不展开，不喊口号
- 结论胶囊放最核心的那句话

三、旁白语气规则
- 多用第二人称和反问："你还记得吗？" / "这步对吗？" / "想到了吗？"
  全片至少 4 处，让观众始终处于参与状态
- 短句为主，每句 10-18 字，主语+动作+结果
- 每句推进一个新信息，禁止复述已讲内容
- 旁白讲逻辑，画面承载关键词和图解，两者不重复
- 允许轻微亲切感叹："对！" / "就是这样。" / "还记得吗？"
  全片不超过 4 处，多则显油腻

四、钩子工程（保证完播率）
- 开场残缺图解是最强钩子，观众会因为"我想起来了吗"而继续看
- 第二镜必须"揭晓"第一镜的问题（哪怕只是部分揭晓），给观众即时满足感
- 每 2-3 镜安排一次小"对了！"时刻——旁白与图解同步说出观众正在回忆的答案

五、禁止
说教开场（"今天我们来学"）、空洞形容（"超简单" / "一看就懂"）、
喊口号（"知识改变命运"）、提前给答案、通篇第三人称冷讲解、
把观众当成从未学过的外行。""",
            "is_builtin": True,
            "created_by": None,
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": STYLE_COMPONENT_IDS["pacing"],
            "category": "pacing",
            "name": "记忆唤醒·短视频竖屏节奏",
            "description": "60-90秒总时长、8-12镜、每镜5-8秒卡片节奏，开场3秒必现课本感元素",
            "prompt_text": """【叙事节奏：记忆唤醒·短视频竖屏节奏】

〇、时长估算基准
estimated_duration_seconds = 旁白字数 ÷ 5 + 画面复杂度补偿 0-2 秒
单镜不低于 5 秒、不高于 10 秒。

一、总量（硬性要求）
- 成片目标：60-90 秒
- scenes 数组长度：8-12 个
- 全片旁白总字数：300-450 字（短视频节奏，不是长内容）
- 每镜旁白：25-45 字；超过 45 字必须拆镜或删词

二、节奏曲线：钩子-重建-升华
- 唤醒段（前 1-2 镜）：合计不超过 15 秒，前 3 秒必须出现课本感视觉元素
  （学科色条带 + 熟悉的图形或公式轮廓）
- 重建段（中间 3-5 镜）：每镜 5-8 秒，图解逐步构建，旁白节奏稳定
- 升华镜（最后 1 镜）：4-6 秒，结论胶囊停留，旁白放慢一句话收束

三、一镜一步拆分规则
每个镜头只承载一个推导步骤或一个信息点：
- "提问 / 展示残缺图解"是一个镜头
- "揭晓答案 / 补全图解"是一个镜头
- 一个公式的每个推导步骤各占一个镜头
- 结论单独占一个镜头
写完后自检：若镜头 description 里出现两次以上"然后/接着/再"，说明塞了多件事，必须拆开。

四、镜头时长按信息密度分级
- 提问/唤醒镜头（1-2 个元素）：5-6 秒
- 图解构建镜头（1 个推导步骤）：6-8 秒
- 复杂图解镜头（多步骤叠加）：8-10 秒，全片不超过 3 个
- 升华/收尾镜头：4-6 秒

五、旁白措辞纪律
- 短句直给，每句 10-18 字
- 前一句说过的内容不得复述
- 禁止口头过渡（"接下来我们看"），镜头切换靠画面衔接
- 画面已呈现的图解内容旁白不复述，只讲画面看不出的含义
- 短视频开头 5 秒的旁白必须包含"还记得" / "你学过" 等记忆召唤词

六、自检
全片 estimated_duration_seconds 之和须落在 60-90 秒：
- 不足 60 秒：在重建段补一个推导步骤镜头
- 超过 90 秒：逐镜删旁白冗词，保持镜头数不变""",
            "is_builtin": True,
            "created_by": None,
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": STYLE_COMPONENT_IDS["scene_structure"],
            "category": "scene_structure",
            "name": "记忆唤醒·知识卡片三层结构",
            "description": "残缺图解开场、逐步补全推导、升华收束的三段镜头序列，每镜固定三层卡片骨架",
            "prompt_text": """【镜头结构：记忆唤醒·知识卡片三层结构】

一、镜头序列模板（全片 8-12 镜）

第一镜——记忆钩子（必须）
- 显示残缺图解：核心元素用 fill_opacity=0.15 的幽灵态隐去
- 顶部标题：学科 + "还记得这个吗？"（≤8字）
- 底层区域：显示问号"？"或"这里是什么"
- 旁白用第二人称 + 具体课堂场景召唤记忆
- 本镜不揭晓答案，制造悬念

第二镜——揭晓与定义（必须）
- 用 FadeIn 补全第一镜的幽灵态元素，完成图解
- 顶部标题更新为知识点名称
- 旁白："对——就是这里。[知识点名称]。"
- 底层结论胶囊：该知识点的一句话定义

第三至 N-1 镜——逐步推导
每个镜头处理一个推导步骤，镜头内部结构：
  顶部：步骤序号 + 本步标题（如"第二步：代入公式"）
  主体：在上一镜图解基础上新增本步内容（Create/Write 逐步构建）
  底层：本步的核心结论或中间结果
旁白："你想到了吗？下一步是——"
相邻镜头至少保留一个视觉锚点（坐标轴、核心符号或关键数字）。

第 N 镜——升华收束（必须）
- 清场，只保留最核心的图形或公式
- 顶部标题："其实你一直用着它"或同义句
- 底层结论胶囊：一句话现实延伸（≤20 字）
- 大面积留白，节奏放慢

二、镜头内部三层骨架（每镜固定）
每个镜头必须具备以下三层，缺一不合格：

┌─────────────────────────┐  ← 顶层：学科色条带 + 标题（画面上方 8-12%）
│  [学科色条带]  本镜标题   │
├─────────────────────────┤
│                         │
│      Manim 图解区        │  ← 主体：Manim 逐步构建（画面中部 50-60%）
│   （逐步 Create/Write）  │
│                         │
├─────────────────────────┤
│  💡 [结论胶囊文字]        │  ← 底层：明黄底结论胶囊（画面下方 15%）
└─────────────────────────┘

三、连续性规则
- 相邻镜头复用同一批 Manim 对象，保持空间位置一致
- 推导过程中坐标轴、分界线、核心符号一旦建立即跨镜保留
- 清场仅发生在升华收束镜头前，用整体 FadeOut 完成
- 图形元素的颜色跨镜头固定（同一变量/概念始终同色）

四、特殊镜头规则
- 公式推导：公式用 TransformMatchingTex 按推理顺序逐项构建，
  变量从已有图形中生长而来，不是静态贴图
- 受力图/坐标系：先 Create 轴和参考线，再 GrowArrow 添加力向量
- 函数图像：Draw 坐标轴，再用 Create(graph) 描绘曲线，最后标注关键点

五、禁止
整页文字标题卡（无图解）、把旁白逐句排成大段文字、
把多个推导步骤压缩进一个镜头、升华镜还在推导新知识。""",
            "is_builtin": True,
            "created_by": None,
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": STYLE_COMPONENT_IDS["animation_style"],
            "category": "animation_style",
            "name": "记忆唤醒·Manim图解动效",
            "description": "逐笔描线图解构建、FadeIn幽灵态补全、GrowFromCenter结论弹出、卡片FadeIn入场",
            "prompt_text": """【动画系统：记忆唤醒·Manim 图解动效】

总原则：动画服务于理解，不做装饰。每个动画对应一次信息的呈现或状态的变化；
宁可静止也不做无意义的运动。Manim 的图形构建能力是本风格的核心差异化优势。

一、图解构建动画（核心）
充分利用 Manim 逐步构建能力：
- 几何图形/曲线：Create() 逐笔描线，单个元素 0.3-0.6 秒
- 文字/公式：Write() 逐字出现，0.4-0.8 秒
- 公式变换/推导：TransformMatchingTex() 按推理顺序逐项变换，
  旧项在旁白说到时淡出，新项生长出现
- 函数图像：Create(graph) 从原点出发描绘，配合旁白节奏
- 坐标轴：Create(axes) 先出，再在其上构建其他元素
- 受力图箭头：GrowArrow() 从作用点出发向外生长，0.3-0.5 秒

二、开场幽灵态补全（开场专用）
- 第一镜的隐藏元素（fill_opacity=0.15）在第二镜中用 FadeIn() 补全
- FadeIn 时机：旁白说到"对——就是这里"时触发
- 单个元素补全约 0.4 秒，不用 Create（避免重描线）
- 补全顺序：从画面中心向外展开

三、卡片入场
- 每个镜头整体入场：FadeIn(shift=UP*0.3)，0.4 秒
- 不用从屏幕外飞入，禁止 slide-in 动效
- 顶部色条带先出（0.2 秒），主体图解区域再入场

四、结论胶囊出场
- GrowFromCenter()，0.4 秒弹出
- 弹出后 0.5 秒停顿
- 再执行一次 Flash()（学科主色），持续 0.3 秒
- 之后静止保持到镜头结束

五、镜头切换
- 统一：FadeOut 旧镜头（0.3 秒）→ FadeIn 新镜头（0.3 秒）
- 不使用任何花式转场（推移、旋转、缩放等）
- 连续推导镜头之间：保留上一镜图形对象，新增本镜元素，
  不清场，用 Create/Write 增量构建
- 幕间清场（升华镜前）：FadeOut(VGroup(*all_objects))，0.5 秒整体淡出

六、beat 内时间分配
- 一个 beat 对应一次图解动画
- 动画完成后静置 0.3-0.5 秒再推进下一拍
- 旁白说到某步骤时对应动画触发，两者精确对齐
- 关键公式或结论前安排 0.2-0.3 秒短暂停顿制造重点感

七、跨镜头连续性
- 同一幕内相邻镜头复用 Manim 对象变量，空间坐标保持一致
- 坐标轴、分界线、核心符号全片同一坐标不移动
- 数字/变量值更新时用 Transform 或 ReplacementTransform，不重新 Create

八、禁忌
屏幕外滑入、持续旋转、频繁闪白、装饰性粒子、
每镜清场重绘（连续推导镜头内）、所有元素同帧出现、
无意义弹跳、超过 1 秒的等待空白（若旁白有间隔，保持最终画面静止即可）。""",
            "is_builtin": True,
            "created_by": None,
            "created_at": now,
            "updated_at": now,
        },
    ]

    op.bulk_insert(prompt_components_table, seeds)

    style_templates_table = sa.table(
        "style_templates",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("name", sa.String),
        sa.column("description", sa.Text),
        sa.column("style_config", postgresql.JSONB),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )

    op.bulk_insert(
        style_templates_table,
        [
            {
                "id": STYLE_TEMPLATE_ID,
                "name": "记忆唤醒·理科卡片",
                "description": (
                    "面向职场人复习初高中数理化的短视频风格族："
                    "白底明亮知识卡片视觉 + 记忆钩子三段式叙事 + 短视频竖屏节奏 + "
                    "知识卡片三层结构 + Manim 图解动效。"
                    "竖屏 9:16，Manim 引擎，适合数学/物理/化学初高中知识复习类选题。"
                ),
                "style_config": {
                    category: str(component_id)
                    for category, component_id in STYLE_COMPONENT_IDS.items()
                },
                "created_at": now,
                "updated_at": now,
            }
        ],
    )


def downgrade() -> None:
    """Remove the seeded memory-recall science card style template and components."""
    style_templates = sa.table(
        "style_templates",
        sa.column("id", postgresql.UUID(as_uuid=True)),
    )
    op.execute(
        style_templates.delete().where(style_templates.c.id == STYLE_TEMPLATE_ID)
    )

    prompt_components = sa.table(
        "prompt_components",
        sa.column("id", postgresql.UUID(as_uuid=True)),
    )
    op.execute(
        prompt_components.delete().where(
            prompt_components.c.id.in_(list(STYLE_COMPONENT_IDS.values()))
        )
    )
