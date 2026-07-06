"""seed_ensemble_theater_style

从《秘书问题：37%法则》类高完播率概率知识短片拆解抽象出的可复用风格族：
群像剧场（快节奏知识叙事）。

Revision ID: b3f1d6a8c2e5
Revises: f4a7c29d1b63
Create Date: 2026-07-06 17:00:00.000000

"""
from datetime import datetime, timezone
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "b3f1d6a8c2e5"
down_revision: Union[str, Sequence[str], None] = "f4a7c29d1b63"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


STYLE_COMPONENT_IDS = {
    "color_scheme": uuid.UUID("b7a2f8c1-1003-4000-8000-000000000001"),
    "narrative_style": uuid.UUID("b7a2f8c1-1003-4000-8000-000000000002"),
    "pacing": uuid.UUID("b7a2f8c1-1003-4000-8000-000000000003"),
    "scene_structure": uuid.UUID("b7a2f8c1-1003-4000-8000-000000000004"),
    "animation_style": uuid.UUID("b7a2f8c1-1003-4000-8000-000000000005"),
}

STYLE_TEMPLATE_ID = uuid.UUID("b7a2f8c1-1003-4000-8000-0000000000ff")


def upgrade() -> None:
    """Seed the five components and bundle template of the ensemble-theater style family."""
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
            "name": "群像剧场·暖白小人群像",
            "description": "暖米白底、彩色圆头小人队列为核心母题、观众化身固定角色、大号语义数字与唯一黑场例外",
            "prompt_text": """【视觉系统：群像剧场·暖白小人群像】

一、背景基调
全片统一暖米白 #F8F4EB 背景，纸面质感，不用纯白与深色。
全片允许且仅允许一个"情感转场"镜头使用纯黑背景——黑场是稀缺资源，
第二次使用即失效，除该镜头外任何镜头不得改变背景。

二、群像母题（本风格的身份标识）
- 抽象概念一律翻译成"一排人"的处境来演示：候选、排队、被选中、
  被淘汰、被错过；全片以"彩色圆头小人横排队列"作为核心视觉载体
- 小人造型统一：圆头 + 方肩短身，无五官，靠颜色、体型、姿态、
  透明度表达一切状态
- 队列 10-25 个，横排等距，整排占画面宽度 70%-85%；
  数量本身是信息时，配计数数字标注而不是堆更多小人
- 主体色循环：宝蓝 #5B8DD9 / 青绿 #3DAA8C / 珊瑚橙 #E8714A /
  蓝紫 #8B7BB5，同排循环取色，制造"人群感"而非制服感

三、观众化身（固定角色）
- 全片设一个"你"角色：蓝紫色小人，位置固定在画面左上区域，
  配「你」或身份标签（面试官 / 玩家 / 决策者）
- "你"不进入队列，始终以旁观-决策视角存在；队列会动，"你"不动
- 涉及"你的动作"（观察、拒绝、选择）时，用从"你"出发的箭头表达

四、语义色（含义锁定，不得挪用）
- 砖红 #C0392B：失败、代价、警示数字、否决划线
- 青绿 #3DAA8C：成功、结论、正确选择、正向数字
- 金黄 #F0B429：当前焦点、被圈选对象的光圈
- 暖灰 #8A7A6A：辅助标注与结构线

五、文字与数字
- 关键数字是本风格的第一主角：衬线体特大号（占画面高度 15%-25%），
  正向结论用青绿、残酷事实用砖红；一屏最多一个大数字
- 公式以"分数 = 数字"组合呈现，衬线体，配一行灰色小注
- 标题：顶部居中，不超过 10 字；残酷/警示主题用红棕、
  方法/结论用青绿、中性用深灰 #3C3C3C
- 手写体文字 + 手绘圆圈专用于情感化旁注，全片 1-2 处，多则油腻

六、分区语言
- 阶段/阵营用竖直虚线切分队列，虚线两侧顶部配「XX阶段 N%」标签，
  左侧橙红系、右侧青绿系
- 基准/标尺用水平虚线加右侧小标签
- 分区与标尺一旦建立即跨镜头保留，不得每镜重建

七、构图
三层骨架：顶部标题层 / 中部队列主体层 / 紧贴主体的标注层。
负空间 55%-70%；收尾镜头只留 1-3 个元素加大片留白。
自检：若一屏出现两个互相争夺注意力的大数字，或队列缩到画面
宽度一半以下，即为不合格构图。""",
            "is_builtin": True,
            "created_by": None,
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": STYLE_COMPONENT_IDS["narrative_style"],
            "category": "narrative_style",
            "name": "群像剧场·设局打脸温情收束",
            "description": "十秒打脸开场、概念速亮原理悬置、对照处刑论证、自我拆台三连与知识到情感的迁移收尾",
            "prompt_text": """【叙事风格：群像剧场·设局打脸温情收束】

一、开场三句打脸（决定完播率的核心规则）
- 第 1 句旁白替观众说出他心里的常识判断（"只要……就总能……"句式），
  语气笃定，像是要顺着常识讲下去
- 紧接一个反问加干脆否定（"是吗？当然不对了"节奏），
  开场 10 秒内必须完成第一次反转
- 封面/首镜允许直接亮出核心数字当钩子，但绝不解释——
  数字前置制造好奇，原理后置作为全片悬念

二、概念速亮、原理悬置
- 与"延迟命名"流派相反：打脸之后立即给出概念的正式名号与别名
  （"被称为X，也叫Y"），像介绍一位传奇人物出场，配学科出身
- 命名只给身份不给原理；"为什么是这个答案"悬置到中后段，
  用对照实验偿还

三、第二人称局中人
- 观众不是听众，是局中人：规则用"你只能 / 你必须 / 你再也不能"宣告，
  损失用"你亲手……"归因到观众身上
- 全片至少 6 处第二人称；关键转折处直接质问观众

四、对照处刑式论证
- 最优解登场前，先让 1-2 个直觉方案上台并当众处刑：
  每个方案给出可量化的惨败数字，失败过程具体到画面上谁被错过、
  错在哪一步，不许一句话带过
- 直觉方案的失败数字与最优解数字必须形成数量级反差，
  反差本身就是高潮的燃料

五、自我拆台三连（本风格的诚实标签）
- 揭晓最优解后禁止就地庆祝，立刻连续抛出它的阴暗面，
  用递进句式串联："残酷的是 → 更扎心的是 → 更残忍的是"
- 每一击都落在观众的切身痛处：仍会大概率失败 / 必须亲手放弃
  好的选项 / 最好的可能早已被你错过
- 拆台用数字和画面支撑，不用感叹词渲染

六、知识到情感的迁移
- 尾段把模型平移到情感、人生场景：同一套图形语言不换，
  只换标签与旁白语境，让观众突然认出"这说的是我"
- 迁移处安排一次具象隐喻转场（黑场 + 单一意象），全片唯一抒情镜头
- 刺痛要具体（"你亲手拒绝了他，不是因为不够好"），不许抽象感慨

七、金句收尾
- 收尾一组对仗句回扣核心数字，冷酷与温情同框：
  "不肯给你100%的X，只肯给你N%的Y"句式
- 数字在结尾完成语义升华：从概率变成勇气、选择或代价

八、禁止
说教开场（"今天我们来讲"）、揭晓后自夸（"是不是很神奇"）、
无数字支撑的形容词、结尾喊口号、通篇第三人称冷讲解。""",
            "is_builtin": True,
            "created_by": None,
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": STYLE_COMPONENT_IDS["pacing"],
            "category": "pacing",
            "name": "群像剧场·1.2倍速快节奏",
            "description": "按 1.2 倍速 TTS 校准的时长估算、快-稳-爆-缓节奏曲线与一拍一动作的高密度推进",
            "prompt_text": """【叙事节奏：群像剧场·1.2倍速快节奏】

〇、前提（时长估算基准）
本风格成片的 TTS 音频按 1.2 倍速播放，有效语速约 6 字/秒。
estimated_duration_seconds = 旁白字数 ÷ 6 + 画面复杂度补偿 0-1.5 秒，
单镜不低于 4 秒、不高于 11 秒。

一、总量（硬性要求）
- 成片目标 2.5-3 分钟（150-180 秒），全片旁白总字数 850-1050 字，
  超出 1050 字即为不合格输出
- scenes 数组长度 16-20 个，平均每镜 8-9 秒
- 每镜旁白 25-45 字；超过 45 字必须拆镜或删词
- 超过 11 秒的镜头必须拆分为两镜

二、节奏曲线：快-稳-爆-缓
- 快：前 3 镜（打脸 + 概念亮相）合计不超过 25 秒，
  开场 10 秒内完成第一次反转
- 稳：设定、规则、对照实验区间匀速推进，一镜一个信息点，
  不加速也不拖长
- 爆：关键数字揭晓独占一镜，旁白只有一句（不超过 25 字），
  该镜前可安排一个 4-5 秒短镜蓄势
- 缓：情感迁移与收尾镜头允许降密度——句子变短、旁白字数降到
  20-30 字，画面留白变大，用节奏落差制造余味

三、beat 密度
- 每镜 1-4 拍：开场与收尾镜头 1-2 拍，展示镜头 2-3 拍，
  推演镜头 3-4 拍
- 一拍一动作：每拍 cue_text 对应且仅对应一次画面状态变化
- 单拍时长 2-5 秒；一拍内塞两个动作的，拆拍

四、旁白措辞纪律
- 短句直给，每句 8-16 字，主语+动作+结果
- 每句必须携带新信息，前一句说过的内容不得复述
- 禁止口头过渡（"接下来我们看看"），转场一律靠画面完成
- 递进换挡词（"更扎心的是 / 更残忍的是"）是快节奏中的合法减速带，
  全片不超过 3 次
- 画面已呈现的信息旁白不重复，只讲画面看不出的逻辑与含义

五、自检
全片 estimated_duration_seconds 之和须落在 150-180 秒：
不足 150 秒回到对照实验幕补推演步骤；超过 180 秒逐镜删旁白冗词，
保持镜头数不变。""",
            "is_builtin": True,
            "created_by": None,
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": STYLE_COMPONENT_IDS["scene_structure"],
            "category": "scene_structure",
            "name": "群像剧场·先亮后证七幕",
            "description": "打脸开场、概念亮相、设定规则、两难对峙、法则速览、对照实验、反面升华的先亮答案再证明结构",
            "prompt_text": """【镜头结构：群像剧场·先亮后证七幕】

总原则：与"延迟揭晓"流派相反，本结构在中段就把最优解亮出来，
后半场先用对照实验证明它，再亲手给它泼冷水。
全片合计 16-20 镜，各幕镜头数为硬性下限。

第一幕·打脸开场（1-2 镜）
1. 常识陈述：用图形隐喻呈现观众的常识策略（不断更换、越多越好），
   旁白替观众把常识说出口
2. 当场否定：画面骤停或集体变灰，旁白反问加否定，留下悬念

第二幕·概念亮相（1 镜）
概念名与别名正式登场，标题卡待遇（大字居中书写），
配学科出身（"在X理论中"）；只命名，不解释

第三幕·设定与规则（2-3 镜）
1. 世界观：群像队列入场，交代对象数量与随机顺序
2. 苛刻规则：规则逐条以卡片立起（少于 3 条一镜并列，
   3 条以上拆镜），每条都用"你只能 / 你必须"句式
3. 规则叠加后点一句"为什么这很难"

第四幕·两难与对峙（2 镜）
1. 两难演示：同一队列连续跑两种失败路径（等太久错过 / 定太早后悔）
2. 对峙：直觉与理论两个图形对峙同屏，宣告"理论的答案冷酷得多"，
   蓄势进入解法

第五幕·法则速览（2 镜）
1. 法则演示：分区 + 阈值机制直接在队列上完整走一遍
   （先给结论性演示，此时不证明）
2. 数字与公式：核心数字加来源公式独占一镜，配一行小注

第六幕·对照实验（4-6 镜，信息密度最高的一幕）
1. 实验设定：放大样本（如 100 人）重新入场，一镜
2. 直觉方案A（观众第一反应的方案）：提出并处刑，惨败数字定格，1-2 镜
3. 直觉方案B：提出并处刑，同样惨败，1 镜
4. 最优方案执行：阶段一、阶段二各占一镜，机制逐步落地
5. 揭晓：直觉数字与最优数字的对比独占一镜，全片视觉高潮

第七幕·反面与升华（4-5 镜）
1. 自我拆台三连：失败概率图 / 必须亲手放弃的代价 / 最好的早已错过，
   每击一镜，标题用递进句式（"残酷的话 / 更扎心的 / 更残忍的真相"）
2. 情感迁移转场：黑场 + 单一具象意象，模型平移到人生场景，1 镜
3. 现实描摹：用最简群像重演观众自己的日常行为，1 镜
4. 金句收尾：清场只留核心数字或两个元素，对仗句定格，1 镜

连续性规则：
- 同一套小人队列贯穿全片复用；幕间允许人数与配色变化，造型不变
- 分区虚线、标尺线一旦建立即跨镜保留
- 幕内镜头之间保留至少一个视觉锚点；清场只发生在幕间
- 全片唯一硬切留给第七幕的情感迁移转场

自检：输出前核对每幕镜头数达到下限；总数不足 16 镜时，
优先在第六幕补完整的"提出→处刑"链条。""",
            "is_builtin": True,
            "created_by": None,
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": STYLE_COMPONENT_IDS["animation_style"],
            "category": "animation_style",
            "name": "群像剧场·状态流转词汇表",
            "description": "队列波浪入场、六态状态词汇表（已阅/被拒/否决/离场/焦点/锁定）、数字弹性定格与做减法收尾",
            "prompt_text": """【动画系统：群像剧场·状态流转】

总原则：动画只做一件事——把"人"的状态变化演出来。
每个动作对应一次决策语义（入场 / 被看过 / 被拒 / 被选中 / 被错过），
禁止装饰性运动；宁可静止也不做无意义的循环与飘动。

一、入场
- 队列：按空间顺序波浪式 grow-in（原地从零放大 + 轻微过冲），
  单个约 0.3 秒，间隔 0.08-0.15 秒；禁止屏幕外滑入
- "你"角色：独立入场约 0.5 秒，之后全片位置锁定不移动
- 标题淡入 0.4 秒；标注在锚定元素出现后延迟 0.2 秒跟随

二、状态流转词汇表（核心，含义锁定）
- 已看过 / 已流逝：fill_opacity 降到 0.25-0.35，保留原位不删除
- 被拒绝：变灰 + 整体下沉的垂头姿态
- 被否决（强调版）：砖红斜线从左上划过该元素，0.3 秒
- 被错过 / 已离场：只剩空心轮廓（描边保留、填充清空），
  这是比变灰更重的终局状态
- 当前焦点：放大 1.2-1.4 倍加同色描边；转移焦点时旧焦点缩回、
  新焦点放大，同时进行形成接力
- 最终选中锁定：金黄光圈 + 对勾，全片每个实验至多出现一次

三、你的动作
"你"的观察与出手一律用灰色细长箭头表达：从"你"出发向队列目标
生长，约 0.4 秒；扫视多个对象时箭头依次指向，被扫过者转入
"已看过"态，形成波浪扫过效果。

四、结构与数字
- 分区虚线：自上而下生长 0.5 秒，画完后两侧标签淡入；
  建立后跨镜保留，不重绘
- 标尺线：从最高个体脚下水平生长并保留至幕结束
- 关键数字：原地弹性放大定格（过冲一次），与旁白读出该数字的
  时刻对齐
- 对比揭晓：旧数字先立、箭头生长、新数字放大压场，
  三步各 0.3-0.5 秒
- 饼图 / 比例图：数值从零生长到目标值约 1 秒

五、beat 内时间分配
- 一拍一动作，动作完成后静置 0.3-0.5 秒再进下一拍
- 首拍完成结构层与主体首批元素，后续拍只做增量
- 镜头末尾保持定格，禁止循环动画补时

六、镜头衔接
- 同幕镜头间禁止清场：队列、虚线、标尺原位继承，只做增量变化
- 幕间切换用整体淡出淡入
- 全片唯一硬切：情感迁移黑场镜头（切入切出各一次）
- 收尾做减法：元素逐层淡出，最后只留 1-3 个元素加大片留白定格

七、禁忌
无意义弹跳、持续旋转、频繁闪白、装饰粒子、每句清场重绘、
所有元素同帧出现、屏幕外滑入、黑场滥用。""",
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
                "name": "群像剧场（快节奏知识叙事）",
                "description": (
                    "从高完播率概率知识短片抽象出的风格族："
                    "暖白小人群像视觉 + 设局打脸温情收束叙事 + 1.2倍速快节奏 + "
                    "先亮后证七幕结构 + 状态流转动画词汇表。"
                    "适合反直觉知识、决策与概率类选题。"
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
    """Remove the seeded ensemble-theater style template and components."""
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
