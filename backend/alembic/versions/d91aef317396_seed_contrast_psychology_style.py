"""seed_contrast_psychology_style

反差心理学·直觉翻案：把早期单薄的"反差心理学"叙事蓝图（仅 4 行文字，
配套 pacing/scene_structure 已在 b6d8f0a2c435 重构时被删除）升级为与
概念传记/暖纸双色同规格的完整叙事蓝图 + 视觉系统 + 动画系统 + 金样本。

核心识别度：反差不是全片一次性的高潮，而是重复出现的结构性节奏——
至少两轮完整的"直觉先立起→当场被推翻"，双栏对照面板（暖橙=直觉 vs
冷青=真相）是唯一论证图式；每轮反差后立即解释机制，不欠账；结尾给
可操作的认知纠偏方法，而非情绪口号。适配个体决策类/社会认知类/
反常识现象类的心理学、行为经济学知识选题。

narrative_style 组件原地更新（UUID 不变，downgrade 精确还原 4 行原文）；
color_scheme / animation_style / exemplar 为新增，归入新族前缀 1007；
同时新增打包三者+narrative_style 的 style_template。

风格设计文档：docs/superpowers/specs/2026-07-22-contrast-psychology-style-redesign.md

Revision ID: d91aef317396
Revises: 7a3d9e5b2c41
Create Date: 2026-07-22 21:00:00.000000

"""
from datetime import datetime, timezone
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "d91aef317396"
down_revision: Union[str, Sequence[str], None] = "7a3d9e5b2c41"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


NARRATIVE_STYLE_ID = uuid.UUID("a1b2c3d4-0001-4000-8000-000000000001")

NEW_COMPONENT_IDS = {
    "color_scheme": uuid.UUID("b7a2f8c1-1007-4000-8000-000000000001"),
    "animation_style": uuid.UUID("b7a2f8c1-1007-4000-8000-000000000005"),
    "exemplar": uuid.UUID("b7a2f8c1-1007-4000-8000-000000000006"),
}

STYLE_TEMPLATE_ID = uuid.UUID("b7a2f8c1-1007-4000-8000-0000000000ff")


NARRATIVE_STYLE_NAME_V2 = "反差心理学·直觉翻案"
NARRATIVE_STYLE_DESCRIPTION_V2 = (
    "至少两轮「直觉立起→当场推翻→机制解释」的反差循环 + 双栏对照定式图式 + "
    "工具化纠偏收尾，适合心理学/行为经济学类反直觉现象选题"
)

NARRATIVE_STYLE_PROMPT_V2 = """\
【叙事蓝图：反差心理学·直觉翻案】

〇、现象归类（动笔前判定，决定证据菜单与场域选取）
- 个体决策类（赌徒谬误、锚定效应、损失厌恶、合取谬误）
  → 证据菜单用当场测试型或数据模拟型
- 社会认知类（基本归因错误、光环效应、群体极化）→ 证据菜单用场景重演型
- 反常识现象类（纯统计/感知反差，不强求归因到具体偏差名词）
  → 证据菜单用数据模拟型
判定一次，全片沿用同一类；若串联多个现象，要求它们同属一个判定结果。

一、不变内核（风格身份，任何选题不得省略）
1. 开庭即立靶：开场 10 秒内，观众必须自己在心里给出一个具体判断
   （数字、选择、排序皆可），这个判断随后会被打脸——不是旁白替观众
   预判，是让观众真的先下注。
2. 至少两轮完整"预期→打破"：每一轮都要走完"直觉方案站住（配证据/
   画面支持它看起来合理）→ 当场被推翻"的完整闭环，禁止只闪一下就
   一笔带过。两轮之间必须换角度或换场景，不能是同一个例子重复讲。
3. 翻案即时解释，不欠账：每一轮反差落地后，机制解释必须紧跟其后
   （同一章或下一章），禁止把两轮的疑问都拖到全片结尾才一次性解释。
4. 双栏是全片唯一论证图式：每一轮反差的落点都是一次"直觉 vs 真相"
   并置面板，格式全片统一、只换内容；禁止另造新图式分散识别度。
5. 纠偏方法必须可操作：结尾不是"所以我们要警惕 XX"式的情绪结论，
   而是一句观众能在 10 秒内学会、下次能实际使用的判断技巧或自检问句，
   且必须回扣开场的那个"下注"，让观众看到自己前后判断的落差。
6. 语气：平静、克制、带一点"拆穿把戏"的分寸感——不喊口号、不贩卖
   焦虑、不居高临下嘲笑观众，而是"这不怪你，是大脑的固定套路"。

二、开庭钩子菜单（四选一，不叠用）
- 押注式：直接抛一个二选一或填空，逼观众在心里先选定
  ("连续 10 次抛硬币都是正面，第 11 次你猜正面还是反面？")。
  适用：个体决策类、有明确对错的判断题
- 排序/估算式：让观众估一个数字或排一个序。适用：反常识现象类、
  统计直觉题
- 代入式：把观众放进一个具体情境，让观众替自己做一次决定。
  适用：社会认知类
- 打脸式：替观众说出一个人人都会脱口而出的常识判断，反问后直接否定。
  适用：观众对某类判断有高度一致的错误共识时

三、证据菜单（每一轮反差用，可跨轮混用）
- 数据模拟型：用统计/概率模拟让反差自己显形（蒙特卡洛式序列、
  真实分布 vs 直觉估计对比）
- 当场测试型：观众就是被试，当场给出材料看观众是否会掉进陷阱
- 场景重演型：简笔小人剧重演一个观众大概率经历过的具体场景，
  末尾揭示自己没意识到的偏差
共同纪律：每种证据在被推翻前必须先让直觉方案看起来"确实合理"——
给出至少一个支撑直觉的理由或数据，再推翻，否则打脸没有分量。

四、机制段（二选一，跟在每一轮反差之后，可以简短）
- 认知捷径直击型：直接画因果链（大脑 → 依赖的启发式 → 为什么这次
  失灵），默认选项，不需要人名
- 研究溯源型：提及具体研究者/实验一句带过，仅当机制确有明确来源且
  不喧宾夺主时使用，不展开人物卡与编年

五、纠偏方法收尾菜单（三选一）
- 自检问句式：给观众一句可以随身带走的自问句
- 决策脚本式：给一个"遇到 XX 情况 → 做 YY"的条件动作对
- 重新定义式：把这个偏差重新框成一个可以被利用而非单纯规避的工具
  （适用于该偏差并非全然有害的情形）

六、镜头结构：双轮翻案·三段循环骨架
全片以"轮"为单位，每轮固定走完"立-破-释"三章（证据充分时可拆为
4 章）：
1. 开庭立靶（1-2 章）：按钩子菜单实现，让观众下注
2. 第一轮反差（4-5 章）：立（直觉方案站住并给出支撑）→ 破（证据当场
   推翻，双栏面板首次出现）→ 释（机制解释）
3. 第二轮反差（3-5 章）：换角度/换场景重复立-破-释，双栏面板复用
   同一视觉格式；若素材只支撑一轮扎实反差，允许把第二轮压缩为
   "呼应式变体"（不完整重走一遍立的过程，但仍须有独立的破点）
4. 纠偏收尾（2-3 章）：回扣开场下注 + 给出可操作方法 + 定格
章节纪律：双栏面板是唯一跨章复用的核心图式，格式固定、内容随轮次
更换；非锚点元素完成使命后立即退场，禁止用降透明度在角落"存档"
堆积；一章一个主图示。

七、节奏与总量（硬性要求）
TTS 常速有效语速约 5.5-6 字/秒，estimated_duration_seconds = 旁白
字数 ÷ 5.5~6 + 画面复杂度补偿 0-1 秒。
- 成片 120-150 秒 → 旁白总字数 650-830 字，低于 650 字即不合格
- 章节 10-13 个，每章旁白 45-70 字；低于 40 字扩写或合并，超过 80 字
  拆章
- 节奏曲线：开庭立靶 8-12 秒 - 第一轮反差 45-55 秒 - 第二轮反差
  40-50 秒（可以比首轮快，观众已进入节奏）- 收尾纠偏 20-25 秒
- 密度纪律：每 1-2 句旁白对应一次画面增量；"破"的瞬间（划叉/翻转）
  必须独占一拍，前后各留 0.3-0.5 秒静止，不得和其他动作挤在一拍里
- 每章 3-6 拍：一句一拍起步，长句逗号处继续拆；单拍 2-4 秒

八、旁白措辞：连续讲述体
句间用时间/因果/转折自然承接；句长 8-22 字；"破"句本身要短促有力
（≤14 字独占一拍），制造"啪"的打脸感；禁止电报体与名词短语堆叠；
禁止报幕式过渡（"接下来我们看看"）。

九、自检（逐项执行）
1. 逐章统计旁白字数并求和：低于 650 字 → 回第一/二轮反差段扩写证据
   与机制解释
2. 总和 ÷ 5.5~6 须落在 120-150 秒
3. 至少两轮完整"立-破-释"，且两轮换了角度或场景
4. 每轮反差落地后机制解释是否紧跟其后，全片结尾前不应还欠着未解释
   的反差
5. 结尾方法是否可操作、是否回扣了开场下注

十、禁止
替观众下结论式说教开场、揭晓后自嘲/自夸式收尾、无证据支撑的形容词
堆叠、喊口号（"一定要警惕 XX！"）、方法论清单超过一条、贩卖焦虑式
恐吓、给没有心理学依据的"民科"式解释、反差轮次之间毫无关联地跳跃
话题。"""

COLOR_SCHEME_NAME = "反差心理学·暖橙冷青对照局"
COLOR_SCHEME_DESCRIPTION = (
    "中性浅灰白画布 + 暖橙(直觉)/冷青(真相)语义色对照局 + 无衬线粗体字体 + "
    "双栏对照面板核心图式，与概念传记的暖白衬线书卷感、暖纸双色形成区隔"
)

COLOR_SCHEME_PROMPT = """\
【视觉系统：反差心理学·暖橙冷青对照局】

〇、画面规格与画布
横屏 16:9。内容画布中性浅灰白 #F2F1ED（区别于概念传记的暖米白、暖纸
双色的暖纸质感，保持中性以让色彩语义落在"暖橙 vs 冷青"这组对照本身，
而不是背景色）。全片背景不变，无黑场，情感落差由节奏与色彩语义承担。

一、字体（本风格的身份标识）
无衬线粗体（区别于概念传记的衬线书卷感），标题短促有力（≤12 字）；
关键数字用大号无衬线等宽数字，强调"直给判断"的语感；"破"句可用
加粗或色块高亮，不使用手写体或装饰字体。

二、语义色（含义锁定，全片唯一色彩系统，不得挪用）
- 暖橙 #E0793C：直觉方案、"我以为"、尚未验证的判断——不代表"错误"，
  只代表"未经检验"
- 冷青 #2E7C74：证据/真相、"实际上"、被验证过的结论
- 砖红 #C0392B：仅用于"破"瞬间的划叉/否决动作本身，不作常驻色
- 石墨灰 #6B6B6B + 低透明：已完成使命、退场前的过渡态（不超过 0.3
  秒，不作为常驻状态使用）
单屏语义色不超过 3 种，色彩承载语义，禁止纯装饰性用色。

三、核心图式：双栏对照面板（全片唯一论证图式，格式锁定）
左栏 = 直觉（"我以为"），暖橙描边，内容为观众判断/常识画面；
右栏 = 真相（"实际上"），冷青描边，内容为证据/数据/结果画面；
面板顶部各配 ≤6 字短标题；"破"瞬间右栏内容以证据形式逐步显现，
左栏同步被打叉或整体转为石墨灰随即退场（不得长期停留在灰态）。
全片同一面板格式复用 2-3 次（对应两轮反差 + 可选的开场下注呈现），
格式不变、内容随轮次更换。

四、图示词汇表（按论证步骤选型，图标只作点缀，不作为镜头主体）
- 观众下注 → 二选一按钮卡 / 数轴刻度估算条
- 直觉支撑证据 → 简笔场景插画 + 数据标注
- 反证数据 → 散点/柱状/序列图，冷青主色
- 机制解释 → 因果箭头链（大脑图标 → 启发式标签 → 偏差结果）
- 纠偏方法 → 单条自检问句卡 / 条件动作对（❶❷两步，不超过两步）

五、布局骨架与排版纪律（硬性要求）
每章先定骨架再放元素：顶部标题区 + 中部主体区两段式；主体区内容
组织为 1 个（单主体居中）或 2 个（左右双栏，即上述对照面板）VGroup；
所有元素归属某个 VGroup，用 arrange / next_to / align_to 建立对齐
关系，禁止逐个指定绝对坐标导致元素散落四角；负空间 ≥ 55%，单屏只
呈现一个核心图示。

自检：一章内出现两个互相争夺注意力的主图示，或双栏面板格式与前几次
不一致，即为不合格构图。"""

ANIMATION_STYLE_NAME = "反差心理学·当庭翻案"
ANIMATION_STYLE_DESCRIPTION = (
    "立-破-释三段动作词汇表，破必须是干脆的单一动作（翻转或划叉+淡出），"
    "转场三选一/无中间态"
)

ANIMATION_STYLE_PROMPT = """\
【动画系统：反差心理学·当庭翻案】

总原则：每一次"立"都要让观众真的看见直觉方案被认真对待过，每一次
"破"都必须是一个干脆、不拖泥带水的单一动作——翻案不是慢慢演变，是
"啪"地一下。相机固定，禁止 zoom / pan。

一、核心动作词汇表
- 立：直觉方案以暖橙描边生长入场，配支撑证据逐条点出（0.15-0.2 秒
  间隔），让它"站稳"至少 1-2 秒
- 破：单一干脆动作二选一——
  1) 暖橙内容整体翻转（Flip）露出冷青背面的真相，0.4-0.5 秒
  2) 暖橙内容被砖红✗划叉（0.3 秒）后立即 FadeOut（不经过变灰过渡），
     冷青真相同步从右侧生长入场
  破的瞬间独占一拍，前后各留 0.3-0.5 秒静止，不与其他动作叠加
- 释：机制因果链逐节点出（0.2 秒间隔），节点间箭头生长 0.3 秒
- 收尾方法卡：淡入 + 轻微上浮 0.3 秒，自检问句逐字浮现

二、转场纪律（转场三选一，无中间态）
跨章元素只有三种归宿——原位保留（仍是当前轮论证的锚点）、复用变换
（同一面板格式换内容）、整体退场（0.5 秒内 FadeOut）。禁止把上一轮
内容缩小减淡后挪到角落"存档"——旧内容要么原位保留、要么变换为新章
正式成员、要么彻底退场，不存在中间态；每次转场结束自检：画面上只
允许存在当前章节清单内的对象，上一章其余对象必须已被显式 FadeOut。

三、节拍纪律
一拍一增量，每拍动画铺满时间窗口 70% 以上，拍间静置 ≤0.5 秒；"破"
独占一拍且前后留白，不得与"立"或"释"的动作压缩进同一拍；禁止循环
动画、装饰粒子、无语义弹跳、频繁闪白、每章清场重绘。

四、禁忌
循环动画、装饰粒子、无语义弹跳、持续旋转、频繁闪白、相机运动、
屏幕外滑入、每章清场重绘、黑场、转场特效。"""

EXEMPLAR_NAME = "反差心理学·直觉翻案（精简摘录）"
EXEMPLAR_DESCRIPTION = (
    "赌徒谬误示例的开场下注章与第一轮反差章两镜节选，示范押注钩子、"
    "双栏对照面板首次出现与「立-破-释」的具体画面/动画写法"
)

EXEMPLAR_PROMPT = """\
{
  "scenes": [
    {
      "scene_index": 0,
      "narration": "连续十次抛硬币都是正面，第十一次，你猜正面还是反面？大多数人此刻心里冒出了同一个答案——反面，该轮到反面了。",
      "description": "画布中央十枚硬币正面朝上依次点出排成一列，暖橙描边二选一按钮卡（正面/反面）滑入下方悬停待选。退场：无（首章）。保留：十枚硬币序列（下一章反差的锚点）。",
      "estimated_duration_seconds": 10.0,
      "beats": [
        {
          "beat_index": 0,
          "cue_text": "连续十次抛硬币都是正面，",
          "visual_action": "十枚硬币正面朝上按0.15秒间隔依次点出排成一列。",
          "emphasis": "十次都是正面",
          "transition": "reveal",
          "fallback_weight": 1.0
        },
        {
          "beat_index": 1,
          "cue_text": "第十一次，你猜正面还是反面？",
          "visual_action": "暖橙描边二选一按钮卡（正面/反面）从下方滑入并轻微悬停。",
          "emphasis": "你猜",
          "transition": "continue",
          "fallback_weight": 1.0
        },
        {
          "beat_index": 2,
          "cue_text": "大多数人此刻心里冒出了同一个答案——反面，该轮到反面了。",
          "visual_action": "反面按钮描边加粗并轻微放大一次，作为观众默认选择的视觉确认。",
          "emphasis": "该轮到反面了",
          "transition": "continue",
          "fallback_weight": 1.0
        }
      ]
    },
    {
      "scene_index": 1,
      "narration": "但硬币没有记忆。前十次的结果，对第十一次没有任何影响——第十一次依然是百分之五十对百分之五十。",
      "description": "双栏对照面板首次出现：左栏暖橙「该轮到反面了」承接上一章按钮，右栏冷青「50% vs 50%」概率条同步生长；左栏被砖红✗划叉后立即淡出。退场：左栏直觉按钮（划叉后0.3秒内淡出）。保留：右栏50/50概率条（本轮结论，下一章机制解释的锚点）。",
      "estimated_duration_seconds": 11.0,
      "beats": [
        {
          "beat_index": 0,
          "cue_text": "但硬币没有记忆。",
          "visual_action": "双栏面板顶部标题「我以为」「实际上」同步淡入生长，左栏继承上一章按钮卡。",
          "emphasis": "没有记忆",
          "transition": "continue",
          "fallback_weight": 1.0
        },
        {
          "beat_index": 1,
          "cue_text": "前十次的结果，对第十一次没有任何影响——",
          "visual_action": "砖红✗从左上到右下划过左栏按钮卡，0.3秒内左栏整体淡出。",
          "emphasis": "没有任何影响",
          "transition": "transform",
          "fallback_weight": 1.0
        },
        {
          "beat_index": 2,
          "cue_text": "第十一次依然是百分之五十对百分之五十。",
          "visual_action": "右栏冷青50%/50%概率条从中线向两侧生长，到达终点各轻微过冲一次定格。",
          "emphasis": "50%对50%",
          "transition": "continue",
          "fallback_weight": 1.0
        }
      ]
    }
  ],
  "fact_checks": [
    {
      "claim_text": "独立随机事件（如公平硬币投掷）的每次结果概率不受历史结果影响，这是概率论的独立性原理，常见的相反直觉被称为赌徒谬误",
      "scene_index": 1,
      "source_url": null,
      "source_description": "概率论独立事件定义；赌徒谬误为行为经济学经典偏差案例",
      "confidence": "high",
      "is_hypothesis": false,
      "assumptions": null,
      "controversy": null,
      "reviewer_verdict": null,
      "reviewer_note": null
    }
  ]
}"""

STYLE_TEMPLATE_DESCRIPTION = (
    "反差心理学的重构版风格族：暖橙冷青对照局视觉 + 至少两轮「立-破-释」"
    "反差循环叙事（押注钩子/证据菜单/机制段/工具化纠偏收尾）+ "
    "5.5-6字/秒打脸节奏 + 双轮翻案三段循环骨架 + 当庭翻案增量动画。"
    "适合心理学、行为经济学类反直觉现象知识选题。"
)

# 更新前的原文（downgrade 还原用），来自 dbc24a784da8_add_prompt_components.py
V1_NARRATIVE_STYLE = {
    "name": "反差心理学",
    "description": "从反直觉现象切入，揭示认知偏差，适合心理学/行为经济学类内容",
    "prompt_text": (
        "【叙事风格：反差心理学】\n"
        "整体娓娓道来，从一个反直觉的问题或现象切入，引发认知冲突，逐步揭示背后的"
        "心理机制，结尾给出可操作的认知纠偏方法。\n"
        "旁白负责讲解，每句话清晰有力，不空洞，不重复画面文字。\n"
        "语气：平静而充满反思感，像一位向朋友分享洞见的智者。"
    ),
}


def upgrade() -> None:
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

    # narrative_style 用 upsert 而非纯 UPDATE：这个内置组件的 id 在部分
    # 开发环境里已经被人工经由"风格提示词工作台"复制/删改过（原行不复
    # 存在），纯 UPDATE 会静默 0 行受影响；upsert 保证无论该 id 当前是否
    # 存在都能落地到同一条规范记录上。
    upsert_narrative = postgresql.insert(prompt_components).values(
        id=NARRATIVE_STYLE_ID,
        category="narrative_style",
        name=NARRATIVE_STYLE_NAME_V2,
        description=NARRATIVE_STYLE_DESCRIPTION_V2,
        prompt_text=NARRATIVE_STYLE_PROMPT_V2,
        is_builtin=True,
        created_by=None,
        created_at=now,
        updated_at=now,
    )
    op.execute(
        upsert_narrative.on_conflict_do_update(
            index_elements=["id"],
            set_={
                "name": NARRATIVE_STYLE_NAME_V2,
                "description": NARRATIVE_STYLE_DESCRIPTION_V2,
                "prompt_text": NARRATIVE_STYLE_PROMPT_V2,
                "updated_at": now,
            },
        )
    )

    op.bulk_insert(
        prompt_components,
        [
            {
                "id": NEW_COMPONENT_IDS["color_scheme"],
                "category": "color_scheme",
                "name": COLOR_SCHEME_NAME,
                "description": COLOR_SCHEME_DESCRIPTION,
                "prompt_text": COLOR_SCHEME_PROMPT,
                "is_builtin": True,
                "created_by": None,
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": NEW_COMPONENT_IDS["animation_style"],
                "category": "animation_style",
                "name": ANIMATION_STYLE_NAME,
                "description": ANIMATION_STYLE_DESCRIPTION,
                "prompt_text": ANIMATION_STYLE_PROMPT,
                "is_builtin": True,
                "created_by": None,
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": NEW_COMPONENT_IDS["exemplar"],
                "category": "exemplar",
                "name": EXEMPLAR_NAME,
                "description": EXEMPLAR_DESCRIPTION,
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
                "name": "反差心理学·直觉翻案",
                "description": STYLE_TEMPLATE_DESCRIPTION,
                "style_config": {
                    "narrative_style": str(NARRATIVE_STYLE_ID),
                    "color_scheme": str(NEW_COMPONENT_IDS["color_scheme"]),
                    "animation_style": str(NEW_COMPONENT_IDS["animation_style"]),
                    "exemplar": str(NEW_COMPONENT_IDS["exemplar"]),
                },
                "created_at": now,
                "updated_at": now,
            }
        ],
    )


def downgrade() -> None:
    now = datetime.now(timezone.utc)

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
        sa.column("name", sa.String),
        sa.column("description", sa.Text),
        sa.column("prompt_text", sa.Text),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    op.execute(
        prompt_components.delete().where(
            prompt_components.c.id.in_(list(NEW_COMPONENT_IDS.values()))
        )
    )

    upsert_narrative = postgresql.insert(
        sa.table(
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
    ).values(
        id=NARRATIVE_STYLE_ID,
        category="narrative_style",
        name=V1_NARRATIVE_STYLE["name"],
        description=V1_NARRATIVE_STYLE["description"],
        prompt_text=V1_NARRATIVE_STYLE["prompt_text"],
        is_builtin=True,
        created_by=None,
        created_at=now,
        updated_at=now,
    )
    op.execute(
        upsert_narrative.on_conflict_do_update(
            index_elements=["id"],
            set_={
                "name": V1_NARRATIVE_STYLE["name"],
                "description": V1_NARRATIVE_STYLE["description"],
                "prompt_text": V1_NARRATIVE_STYLE["prompt_text"],
                "updated_at": now,
            },
        )
    )
