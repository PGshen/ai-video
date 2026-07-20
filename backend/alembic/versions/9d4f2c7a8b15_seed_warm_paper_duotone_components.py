"""seed_warm_paper_duotone_components

暖纸双色·橙蓝语义图解：从高完播率数理科普短片（对数时间感知）逆向提取的
视觉系统与动画系统两个组件。横屏 16:9，Manim 引擎。
暖米粉纸底 + 陶土橙/深靛蓝双色语义 + 细线图解 + 中英双语标题；
动画以"一张不断擦写的讲义纸"为总心智模型：跨镜头连续变换、数值扫描、
手绘感强调。仅提供 color_scheme 与 animation_style 两个组件，
不捆绑叙事组件与 style_template，可与任意叙事蓝图自由组合。

Revision ID: 9d4f2c7a8b15
Revises: d7f2b4c6e831
Create Date: 2026-07-18 13:30:00.000000

"""
from datetime import datetime, timezone
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "9d4f2c7a8b15"
down_revision: Union[str, Sequence[str], None] = "d7f2b4c6e831"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


STYLE_COMPONENT_IDS = {
    "color_scheme":    uuid.UUID("b7a2f8c1-1006-4000-8000-000000000001"),
    "animation_style": uuid.UUID("b7a2f8c1-1006-4000-8000-000000000005"),
}


def upgrade() -> None:
    """Seed the visual and animation components of the warm-paper duotone style."""
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
            "name": "暖纸双色·橙蓝语义图解",
            "description": "暖米粉纸底、陶土橙/深靛蓝双色语义对立、细线图解与胶囊标注、中英双语标题",
            "prompt_text": """【视觉系统：暖纸双色·橙蓝语义图解】

〇、画面规格（硬性要求）
横屏 16:9，Manim 默认配置（1920x1080）。全片统一此规格。
底部约 12% 留空（后期将在此叠加字幕），核心图解不得进入该区域；
顶部约 12% 为标题区。核心图解集中在画面中部 70% 区域。

一、背景
主背景：暖米粉纸色 #F2E9E6（似有微弱纸纹的暖调米粉色）。
全片唯一背景，不切换深色模式，不做黑场——章节转换靠内容更替完成。

二、双色语义主色（本风格的身份标识）
全片建立一组固定的颜色语义对立，一旦分配，跨镜头不变：
- 陶土橙 #C25E3F：主观的、感受的、当下强调的一方
  （如：主观时间 / 童年 / 变化量 / 结论断言）
- 深靛蓝 #26274E：客观的、基准的、对照的一方
  （如：日历时间 / 成年 / 基数 / 既定事实）
任何"A vs B"的对比图解都必须落在这组橙蓝对立上；
左右双栏对比时通常橙在左、蓝在右。
同一概念全片同色；正文与中性图形线条用近黑深灰 #1B1212。

三、辅助色（受限使用）
- 灰绿 #4E7A68：专用于"转折/新增/希望"语义的章节
  （如"新信息让时间变长"），是打破橙蓝对立的第三色，
  全片最多一个章节使用，不与橙蓝语义混淆
- 暖灰 #9E948F：英文副标题、次要标注、单位等辅助信息
- 结尾升华镜头允许橙/蓝/绿多色小元素并存（如彩色时间轴标记点），
  表达"丰富多样"语义，仅此一处例外

四、半透明面积填充
需要表达"面积/数量/区间"时，用语义色 15%-35% 不透明度的填充
（曲线下面积、柱状条、方块阵列），边线用同色实线（stroke_width 2-3）。
两种语义面积叠放时，橙蓝半透明填充可以相邻或相接，边界清晰。

五、标题系统（每个章节页固定）
- 中文主标题：顶部居中，按本章语义取橙/蓝/绿色，font_size 等效 44-52pt
- 英文副标题：紧贴主标题下方，暖灰小写短语，font_size 等效 18-22pt
  （如 "a simplified logarithmic model"），起学术注脚气质
- 标题在镜头推进中原位替换，位置与字号不变

六、图形语言
- 线条：细线为主，stroke_width 2-3，颜色取语义色或深灰
- 卡片：圆角矩形，细边框，无填充或纸色微填充，不加阴影
- 胶囊标注：圆角胶囊细边框 + 同色文字（如「不是错觉」「翻倍」），
  可配一条同色曲线箭头（CurvedArrow）指向目标；是本风格的标准旁注形式
- 刻度尺 motif：时间/生命一律画成带均匀刻度的横尺（圆角边框 + 密集竖刻度），
  是本风格反复出现的核心意象
- 线稿图标：具象物一律用单线勾勒的极简图标（房子、提包、时钟），
  不用面填充图标、不用 emoji、不用照片
- 图标只作点缀：单个图标高度不超过画面高度的 10%，置于标注文字或
  卡片旁辅助示意，禁止作为镜头主体；镜头主体永远是结构化图表
  （刻度尺 / 坐标系 / 卡片 / 方块阵列 / 时间轴）
- 禁止火柴人、简笔涂鸦、儿童画式具象绘画；需要表现"人"或复杂具象物时，
  用抽象几何代替（圆点、胶囊、带标签的卡片）
- 同类元素同尺寸、同圆角、同 stroke_width，几何必须规整
  （网格对齐、间距均匀），不追求"手绘的抖动感"
- 数量对比：用小方块阵列（5 个方块 vs 10x10 网格），填充色表新增量

七、数学排版
- 公式一律 LaTeX 衬线体（Manim MathTex 默认），与中文黑体形成中西混排对比
- 公式中承载语义的数字/变量按语义着色（变化量橙、基数蓝），
  其余部分深灰
- 公式服务于图形：与图解共存时置于图解旁侧或下方，不压盖图形主体

八、布局骨架与排版纪律（硬性要求）
- 每镜先定骨架再放元素：顶部标题区 + 中部主体区两段式；
  主体区内容必须组织为 1 个（单主体，画面居中）或 2 个（左右双栏）VGroup，
  VGroup 整体在主体区内居中
- 所有元素必须归属某个 VGroup，用 arrange / next_to / align_to 建立对齐关系，
  禁止逐个指定绝对坐标导致元素散落四角、互不对齐
- 标注紧贴其指向的目标（胶囊 + 箭头与目标间距小于目标自身尺寸）；
  留白只允许出现在主体四周，禁止夹在互相关联的元素之间
- 左右双栏必须严格对称：两栏等宽，栏内"标题 / 图形 / 结论"三段上下对齐
- 大量留白，单屏只有一个核心图解
- 单屏语义色不超过 3 种（背景不计）
- 色彩承载语义，禁止纯装饰性用色""",
            "is_builtin": True,
            "created_by": None,
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": STYLE_COMPONENT_IDS["animation_style"],
            "category": "animation_style",
            "name": "暖纸双色·讲义纸连续变换",
            "description": "全片如一张不断擦写的讲义纸：骨架锚点原位保留、标题原位变换、ValueTracker数值扫描、手绘圈与打叉强调、转场自检防残留",
            "prompt_text": """【动画系统：暖纸双色·讲义纸连续变换】

总心智模型：全片是一张不断擦写的讲义纸。镜头之间没有"翻页"，
只有元素的擦除、退层与生长。动画服务于推理的展开，
每个动画对应一次信息呈现或状态变化，宁可静止也不做无意义运动。

一、跨镜头连续演进（本风格的身份标识）
镜头切换禁止硬切，按内容关系三选一：
- 锚点保留：仅当新旧镜头共享同一图表骨架（坐标轴 / 刻度尺 / 卡片框）时，
  骨架原位保留——位置、大小、颜色、透明度都不变，
  其余旧元素 FadeOut（0.3 秒）后在骨架上构建新元素
- 复用变换：上一镜的图形对象 Transform 成它在新镜正式版式中的对应物
  （如单图并入双栏、图形收拢进卡片），变换终点必须是新镜布局的
  正式成员，观众看着旧图变成新图
- 整体淡出（默认）：不满足以上两条时，FadeOut 全部旧对象（0.4 秒）
  后构建新镜头
顶部标题始终原位替换：TransformMatchingStrings/TransformMatchingTex，
位置字号不变，只换文字内容。
禁止把上一镜内容缩小、减淡后挪到角落"存档"——旧内容要么原位保留、
要么变换为新镜正式成员、要么彻底退场，不存在中间态。
每次转场结束必须自检：画面上只允许存在当前镜头清单内的对象，
上一镜的其余对象必须已被显式 FadeOut，防止残留漏删。

二、构建动画（与旁白逐个对齐）
- 线条/坐标轴/刻度尺/曲线：Create() 逐笔描线，0.4-0.8 秒
- 文字/公式：Write() 逐字出现，0.4-0.8 秒
- 卡片/图标/已成形元素：FadeIn(shift=UP*0.2)，0.3-0.5 秒
- 箭头：GrowArrow() 从起点生长，0.3 秒
- 同类元素群（方块阵列、时间轴标记点）：LaggedStart 依次出现，
  lag_ratio 0.1-0.2，总时长不超过 1.5 秒
元素出现顺序严格跟随旁白语序：旁白说到什么，什么才出现。

三、数值扫描（本风格的特色手法）
展示函数关系/趋势时，用 ValueTracker + always_redraw：
一条指示线或指示点沿曲线/横轴匀速移动，旁边数字标签实时更新
（如年龄从 9 → 13 → 18 → 25 扫过，每处停留 0.5 秒读出对应值）。
比静态标注多个点更能传达"连续变化"的感觉，优先采用。

四、公式推导
- 公式演进用 TransformMatchingTex 原位变形，按推理顺序逐项变换
- 被否定的公式/结论：用橙色斜叉（两笔 Create，0.4 秒）划掉，
  划掉后保留在画面作为对照，不立即移除
- 新结论从图形中生长而来（面积→积分式、图形数量→分数），不凭空出现

五、强调手法（每镜头至多一种）
- SurroundingRectangle：橙色细框 Create 包围关键式子，0.4 秒
- 手绘圈：橙色不规则圆圈 Create 圈出图中重点区域，0.5 秒
- 断言大字：结论性短语（如「当然不对」）以大号橙字 FadeIn，
  停留至镜头结束，配合从其指向证据的小箭头
- 关键数字变色：数字由深灰变为语义色（0.3 秒）

六、对比动画
- 左右双栏：同一动画在两栏先后播放（左栏先、右栏后，间隔约 0.5 秒），
  用相同的动画类型强化"同样操作、不同结果"
- 多对一合并：多条线/多个元素 Transform 收拢进一个卡片，
  配合 Brace 括拢，表达"被合并/被压缩"语义

七、节奏
- 单个动画 0.3-0.8 秒；动画完成后静置 0.3-0.5 秒再推进
- 动画触发点与旁白句子精确对齐；旁白间隙保持画面静止
- 数值扫描等长动画（1.5-3 秒）全片不超过 3 处，且必须有旁白覆盖

八、禁忌
屏幕外飞入滑出、旋转/缩放/推移转场、闪白、粒子与光效、
镜头间硬切、上一镜内容缩小减淡退居角落、转场后残留旧对象、
所有元素同帧出现、无旁白覆盖的长动画、装饰性循环运动。""",
            "is_builtin": True,
            "created_by": None,
            "created_at": now,
            "updated_at": now,
        },
    ]

    op.bulk_insert(prompt_components_table, seeds)


def downgrade() -> None:
    """Remove the warm-paper duotone visual and animation components."""
    prompt_components = sa.table(
        "prompt_components",
        sa.column("id", postgresql.UUID(as_uuid=True)),
    )
    op.execute(
        prompt_components.delete().where(
            prompt_components.c.id.in_(list(STYLE_COMPONENT_IDS.values()))
        )
    )
