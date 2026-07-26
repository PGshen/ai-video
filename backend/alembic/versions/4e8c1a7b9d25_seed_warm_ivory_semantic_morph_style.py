"""seed_warm_ivory_semantic_morph_style

从参考 Manim 视频《能量与信息》提炼可跨选题复用的视觉与动画语法：
暖象牙学术讲义、衬线编辑排版、青绿/琥珀语义双色、细线科学图示，
以及固定镜头中的连续匹配变形。

录屏控件、通知、黑底玫瑰插片、字幕、左右黑柱和播放器尾屏不属于风格，
已在提示词中显式排除。

本风格只定义 color_scheme / animation_style / exemplar，不绑定
narrative_style；使用时可与任意叙事蓝图组合。

风格分析文档：
docs/superpowers/specs/2026-07-25-warm-ivory-semantic-morph-style-analysis.md

Revision ID: 4e8c1a7b9d25
Revises: d91aef317396
Create Date: 2026-07-25 16:00:00.000000

"""
from datetime import datetime, timezone
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "4e8c1a7b9d25"
down_revision: Union[str, Sequence[str], None] = "d91aef317396"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


STYLE_COMPONENT_IDS = {
    "color_scheme": uuid.UUID("b7a2f8c1-1008-4000-8000-000000000001"),
    "animation_style": uuid.UUID("b7a2f8c1-1008-4000-8000-000000000005"),
    "exemplar": uuid.UUID("b7a2f8c1-1008-4000-8000-000000000006"),
}

STYLE_TEMPLATE_ID = uuid.UUID("b7a2f8c1-1008-4000-8000-0000000000ff")


COLOR_SCHEME_PROMPT = """\
【视觉系统：暖白学术图解·双色语义】

〇、风格身份与适配原则
本风格的身份不是某个具体学科图标，而是：
暖象牙白学术讲义 + 衬线编辑排版 + 细线几何图解 + 青绿/琥珀语义双色 +
大面积留白。根据当前选题选择对应的几何隐喻，禁止机械复制原子、咖啡杯、
人物或"能量/信息"字样。

一、画布与留白（硬性要求）
- 横屏 16:9，背景全片固定为暖象牙白 #FDFAF6；直接铺满 Manim 画布
- 禁止黑边/左右黑柱、手机状态栏、播放器控件、通知横幅、底部描边字幕、
  黑底插片、片尾推荐卡；这些是参考素材的录屏杂质，不是视觉风格
- 稳定画面的负空间保持 62%-78%；一屏只解释一个主关系
- 主体 1 个，辅助对象最多 2 组；装饰不得比主体颜色更深、面积更大

二、语义色（含义锁定，不得随意换色）
- 主墨色 #1C1B19：正文、公式和主轮廓
- 青绿 #2F916A / 深青灰 #1F665B：信息、结构、有效传递、正确关系
- 琥珀金 #D2973B：能量、时间、关键节点、历史年份和核心强调
- 赭橙 #AF6535：消耗、热、冲突、否定和损失
- 蓝 #2D78A8：物理载体、中性系统、人物/方案 A
- 玫红 #C94F78：人物/方案 B，仅在关系或对照镜头使用
- 灰紫 #7D7391：未知、悖论、交叠关系
- 辅助灰 #9BA0A1、结构线 #D5D0D3：次级说明、坐标、通道和页面边界
- 淡薄荷 #D6ECE5、淡金 #F6EED7、淡紫 #E1CDE4：
  只作 8%-18% 透明填充、交集或短暂背景色场
稳定画面最多两个强调色家族同时占主导；第三强调色只能小面积、短暂出现。
颜色变化必须对应语义状态变化，不做随机彩虹配色。

三、字体与编辑排版
- 全片中文使用宋体/明朝体系衬线字；数学内容使用 LaTeX 字形
- 标题像书页章题，置于上方居中或中央，不超过 14 个汉字
- 一句话只给 1-2 个关键词着色，其余文字使用主墨色
- 历史节点可把四位年份拆成两组有呼吸感的大号数字（如"19  48"），
  但只有内容涉及历史节点时才使用，不得每个选题硬套年份
- 公式、年份、定律名可以独占一屏；靠字号、位置和留白建立层级，
  不依赖阴影、发光或厚重卡片
- 最终停留态文字必须完全可读且互不重叠；文字穿插只允许在不超过
  0.35 秒的变形过渡中出现

四、图形词汇表（按选题取用，不要求全用）
1. 关系图形：圆/交叠圆、Venn 交集、因果箭头、时间轴、通道、刻度条、
   左右对照、简洁进度条
2. 科学对象：原子、波、方形信息包、粒子、容器、活塞、仪表、坐标轴、
   简单网络；均用基础几何图元拼成，不用外部图片
3. 抽象人物：圆头 + 短圆角躯干 + 两点一线表情，无写实五官和肢体
4. 编辑元数据：章节编号圆章、右上角小场景标签、公式名、年份、
   极淡页面边界
5. 氛围图元：同心圆、扩散环、稀疏粒子、低透明大圆；
   仅作瞬时连接或主体背后的呼吸层，不能成为常驻装饰噪声

五、四种构图骨架
- 章题式：上方短标题 + 中央单一图示 + 极少量脚注
- 公式式：公式或年份居中放大，周围只保留必要解释
- 对照式：左右两个对象/命题，中间用交集、箭头、VS 或通道建立关系
- 传递式：源 → 路径/载体 → 目标，用少量粒子或色块展示过程
先选择一种骨架再布置元素；禁止把四种骨架混在同一稳定画面。

六、造型纪律
- 主描边细而清晰，统一线宽；填充低饱和、低透明
- 可以使用细框和小圆角容器，但不做大面积卡片墙、阴影 UI、3D 拟真物体、
  霓虹渐变或仪表盘
- 同一对象跨镜复用时，轮廓、颜色和尺寸关系保持一致
- 自检：若去掉标题后无法在 2 秒内看懂主体之间的关系，说明图示过密，
  必须删减而不是缩小全部元素
"""


ANIMATION_STYLE_PROMPT = """\
【动画系统：暖白学术图解·连续语义变形】

总原则：相机固定，推理关系通过对象自身的建立、传递、相交、变形和耗散
完成。除前后确实没有语义继承的章节外，禁止"上一镜全清空、下一镜从零
重画"；连续变形是本风格最重要的身份。

一、动作占空比与时间
- 主要动作 0.55-1.10 秒；微动作 0.20-0.45 秒
- 同类元素错落间隔 0.06-0.16 秒
- 动作前留 0.2-0.4 秒观察起点，结论态留 0.8-1.6 秒读图
- 一个 beat 只承担一个主要语义变化，同时运动的独立对象不超过 3 组
- 不做持续漂浮、循环旋转、弹跳、镜头推拉或无意义粒子运动

二、六类语义动作
1. 建立
   - 顺序固定为：结构线生长 → 主体出现 → 标注跟随
   - 同类节点/粒子按阅读方向错落出现，不得所有元素同时淡入
2. 传递
   - 小方块/粒子沿已建立的通道移动，波形沿路径生长，箭头从因到果绘制
   - 路径和载体必须在场，让观众看见"什么经过了什么"
3. 转换
   - 同一对象改变形状、颜色、位置或排列来表达状态变化
   - 有语义继承时优先使用匹配形状/文字的变形或替换变形，
     禁止用 FadeOut + FadeIn 伪装成转换
4. 相交
   - 两段弧线先分别生长，再组成交叠圆；交集最后着淡紫，
     结论文字在交集稳定后出现
5. 否定/耗散
   - 一次划叉、收缩、碎成少量粒子或退色即可；动作短促，
     不叠加抖动、爆炸和镜头震动
6. 推导
   - 公式的项、年份数字、图示节点从上一状态移动到下一状态，
     让结论看起来是推导所得而非凭空展示

三、跨镜转场优先级
1. 匹配变形：上一镜核心对象改变形状、位置或标签，成为下一镜锚点
2. 扩散圆承接：已有圆形扩大为低透明色场，再收束为下一镜的光晕、
   结构圈或交集
3. 粒子承接：旧对象离散成少量粒子，沿明确路径汇聚为下一镜主体
4. 整组退场：只有前后不存在可解释的语义继承时，才在 0.5 秒内整体淡出
全片不使用黑场和硬切。转场结束后画面必须回到暖象牙背景。

四、Manim 实现映射
- 线、圆、轮廓：Create；文字和公式：Write
- 同类错落：LaggedStart 或 AnimationGroup，按空间阅读顺序组织
- 箭头和通道：GrowArrow / Create；粒子传递：MoveAlongPath
- 连续对象：TransformMatchingShapes、TransformMatchingTex、
  ReplacementTransform 或 Transform
- 颜色是状态变量：通过 animate.set_color / set_fill 改变，
  颜色变化与形状变化尽量在同一次 play 中完成
- 跨镜复用上一镜变量，不重复创建看起来相同的新对象

五、生命周期与防碰撞
每个核心对象走完：建立 → 承载状态/关系 → 得出结论 → 复用变形或完整退场。
过渡时允许对象短暂穿插，但不超过 0.35 秒；每次 play 结束都检查标题、
公式、主体和标注的包围盒，稳定画面不得有文字压图或元素互相遮挡。
不再使用的装饰环和粒子必须完整退场，禁止降透明后长期堆在角落。

六、禁止
- 所有镜头统一套用 FadeIn + shift
- 用 zoom / pan 代替对象关系变化
- 一次性完成整镜所有动画，随后长时间静止
- 每个 beat 都重新创建标题、背景和主体
- 为了填时间添加循环、晃动、呼吸缩放或无信息量的闪烁
- 把参考素材中的录屏 UI、通知、字幕、黑柱、黑底插片或尾屏当作转场
"""


EXEMPLAR_PROMPT = """\
{
  "scenes": [
    {
      "scene_index": 0,
      "narration": "看到新证据以后，我们为什么要改变原来的判断？",
      "description": "暖象牙白画布中央建立一组证据更新关系：左侧蓝色圆代表原判断，中间青绿色小方块代表新证据，右侧琥珀色问号代表尚未完成的更新。上方只有一行衬线标题，四周保留大片空白。",
      "estimated_duration_seconds": 8.0,
      "beats": [
        {
          "beat_index": 0,
          "cue_text": "看到新证据以后，",
          "visual_action": "先绘出左侧蓝色原判断圆和通向中央的极细灰线，随后青绿色证据方块从圆内分离，沿灰线移动到画面中央并停住。",
          "emphasis": "新证据",
          "transition": "transform",
          "fallback_weight": 1.0
        },
        {
          "beat_index": 1,
          "cue_text": "我们为什么要改变原来的判断？",
          "visual_action": "中央证据方块右侧生长出一段琥珀色弧线，弧线闭合为问号；标题中的“改变”同步转为琥珀色，其余元素保持安静。",
          "emphasis": "改变判断",
          "transition": "reveal",
          "fallback_weight": 1.0
        }
      ]
    },
    {
      "scene_index": 1,
      "narration": "证据不是替换旧结论，而是沿着关系链，重新分配两种可能性的权重。",
      "description": "继承上一镜的蓝色圆、青绿证据方块和细线，把它们连续变形成左右两条概率刻度。证据沿共同通道推进后，蓝色短条缩短，青绿色长条增长，最终形成清楚的权重对照。",
      "estimated_duration_seconds": 10.0,
      "beats": [
        {
          "beat_index": 0,
          "cue_text": "证据不是替换旧结论，",
          "visual_action": "蓝色原判断圆不消失，轮廓展开为上方概率刻度；青绿证据方块仍停在刻度中央，旁边短暂出现一个赭橙色否定叉，明确表示不是直接删除。",
          "emphasis": "不是替换",
          "transition": "transform",
          "fallback_weight": 1.0
        },
        {
          "beat_index": 1,
          "cue_text": "而是沿着关系链，",
          "visual_action": "证据方块沿两条分叉细线移动，分叉末端分别长出蓝色和青绿色权重条；细线画完后才出现两侧的可能性标签。",
          "emphasis": "关系链",
          "transition": "continue",
          "fallback_weight": 1.0
        },
        {
          "beat_index": 2,
          "cue_text": "重新分配两种可能性的权重。",
          "visual_action": "蓝色权重条从一半平滑缩短到约三成，青绿色权重条同步增长到约七成；最终数值和“更新后”短标题淡入并停留，画面不再添加装饰。",
          "emphasis": "重新分配权重",
          "transition": "continue",
          "fallback_weight": 1.0
        }
      ]
    }
  ],
  "fact_checks": [
    {
      "claim_text": "新证据会通过条件概率更新不同假设的相对权重，而不是简单删除先验判断。",
      "scene_index": 1,
      "source_url": null,
      "source_description": "核查贝叶斯更新或条件概率的权威教材来源。",
      "confidence": "high",
      "is_hypothesis": false,
      "assumptions": "示意图只表达相对权重变化，不代表未经题目数据计算的精确概率。",
      "controversy": null,
      "reviewer_verdict": null,
      "reviewer_note": null
    }
  ]
}"""


STYLE_TEMPLATE_DESCRIPTION = (
    "暖象牙学术讲义、衬线编辑排版、青绿/琥珀语义双色与细线几何图解；"
    "以匹配变形、路径传递、交叠圆和粒子承接实现几乎无硬切的连续推理动画。"
    "仅绑定视觉、动画与金样本，可搭配任意叙事蓝图。"
)


def upgrade() -> None:
    """Seed visual, animation and exemplar components plus their style template."""
    now = datetime.now(timezone.utc)

    prompt_components = sa.table(
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

    op.bulk_insert(
        prompt_components,
        [
            {
                "id": STYLE_COMPONENT_IDS["color_scheme"],
                "category": "color_scheme",
                "name": "暖白学术图解·双色语义",
                "description": (
                    "暖象牙白讲义画布、衬线编辑排版、青绿/琥珀语义双色、"
                    "细线科学图示与 62%-78% 大留白"
                ),
                "prompt_text": COLOR_SCHEME_PROMPT,
                "is_builtin": True,
                "created_by": None,
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": STYLE_COMPONENT_IDS["animation_style"],
                "category": "animation_style",
                "name": "暖白学术图解·连续语义变形",
                "description": (
                    "固定镜头中的建立、传递、相交、变形、耗散与推导；"
                    "匹配变形优先，扩散圆/粒子承接，几乎无硬切"
                ),
                "prompt_text": ANIMATION_STYLE_PROMPT,
                "is_builtin": True,
                "created_by": None,
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": STYLE_COMPONENT_IDS["exemplar"],
                "category": "exemplar",
                "name": "暖白学术图解·证据更新金样本",
                "description": (
                    "用非原片选题示范双色语义、继承对象、路径传递和权重变形，"
                    "防止模型照抄能量/信息题材"
                ),
                "prompt_text": EXEMPLAR_PROMPT,
                "is_builtin": True,
                "created_by": None,
                "created_at": now,
                "updated_at": now,
            },
        ],
    )

    style_templates = sa.table(
        "style_templates",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("name", sa.String),
        sa.column("description", sa.Text),
        sa.column("style_config", postgresql.JSONB),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )

    op.bulk_insert(
        style_templates,
        [
            {
                "id": STYLE_TEMPLATE_ID,
                "name": "暖白学术图解·语义流变",
                "description": STYLE_TEMPLATE_DESCRIPTION,
                "style_config": {
                    "color_scheme": str(STYLE_COMPONENT_IDS["color_scheme"]),
                    "animation_style": str(
                        STYLE_COMPONENT_IDS["animation_style"]
                    ),
                    "exemplar": str(STYLE_COMPONENT_IDS["exemplar"]),
                },
                "created_at": now,
                "updated_at": now,
            }
        ],
    )


def downgrade() -> None:
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
