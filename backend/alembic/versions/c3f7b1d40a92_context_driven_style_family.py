"""context_driven_style_family

优化「情境驱动知识叙事」叙事蓝图（可执行化：钩子形态清单、证据的四要素、
机制三步的展示纪律、结尾行动的可检验性、以及节奏与结构段落的自检项），
并为其配套专属视觉与动画系统：

- 视觉：冷白现场感 + 认知紫（#FAFAFC 冷白画布、深墨紫文字、认知紫焦点色、
  语义色含义锁定、无衬线现场标注排版）
- 动画：情境推演动画（同一情境舞台上的下注→揭晓→拆解→迁移，
  以「同场景前后对照」和「锚点复用」为身份动作，禁止模板化进场）
- 金样本：用非本族既有题材示范三件套如何协同

原通用组件「高对比亮底认知紫」「语义驱动动态图解」保持不变，不影响已有项目。

Revision ID: c3f7b1d40a92
Revises: a71c39d5e284
Create Date: 2026-08-26 10:00:00.000000

"""
from datetime import datetime, timezone
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "c3f7b1d40a92"
down_revision: Union[str, Sequence[str], None] = "a71c39d5e284"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


NARRATIVE_ID = uuid.UUID("b2c3d4e5-0001-4000-8000-000000000001")

STYLE_COMPONENT_IDS = {
    "color_scheme": uuid.UUID("b7a2f8c1-1009-4000-8000-000000000001"),
    "animation_style": uuid.UUID("b7a2f8c1-1009-4000-8000-000000000005"),
    "exemplar": uuid.UUID("b7a2f8c1-1009-4000-8000-000000000006"),
}

STYLE_TEMPLATE_ID = uuid.UUID("b7a2f8c1-1009-4000-8000-0000000000ff")


NARRATIVE_PROMPT = """\
【叙事风格：情境驱动知识叙事】

〇、身份
本蓝图的身份是「让观众先下注，再被证据打脸，最后拿走一条能用的判断规则」。
全片的推进动力来自观众自己的预期与事实之间的差距，而不是知识点的罗列顺序。
判断一稿是否合格的唯一标准：观众在第 6 秒之前已经在心里选了一个答案。

一、开场：情境与下注（不得违反）
- 第一句必须是一个具体的人、具体的时间地点、具体的动作或具体的数字，
  禁止以术语、定义、背景介绍、"我们都知道"、"今天聊聊"开场
- 开场必须让观众能形成一个可被判错的直觉判断。可用的下注形态（任选其一）：
  1) 二选一：两个方案/两条路径，问哪个结果更好
  2) 猜数字：给出量级悬殊的选项，让观众估一个
  3) 预测后果：描述一个动作，让观众预判会发生什么
  4) 找错：给出一个看起来完全合理的做法，暗示它有问题
- 下注对象必须在片中真的被揭晓，禁止开场抛问题、后文自说自话

二、反转：证据必须带四要素
揭晓结果后给出的第一份证据，必须同时说清：
  比较对象（和什么比）、关键数字（多少）、来源性质（实验/统计/案例/对照）、
  结论边界（在什么条件下成立）
四要素缺一即为不合格。禁止用"研究表明""科学家发现"代替具体对照与数字；
禁止把相关性说成因果；有争议的结论必须在同一段内说明分歧点，而不是留到结尾。

三、机制：先看见，再命名
- 机制拆成不超过三步，步与步之间必须有因果衔接词以外的实质连接：
  上一步的结果就是下一步的输入
- 每一步的顺序固定为「可观察的变化 → 这个变化叫什么」。
  先给概念名再解释的写法一律改写
- 抽象量必须落到人物、动作、空间关系或可数对象上；
  禁止连续两个镜头只出现定义与同义改写

四、迁移：回到同一个情境
现实迁移段必须复用开场那个人/那个场景，展示「常见做法」与「更有效做法」
在同一情境下的不同结果。禁止另起一个无关的新例子。

五、行动：可检验
结尾给出不超过三条行动，每条都要满足：有触发条件（什么时候用）、
有具体动作（做什么）、能自我检验（怎么知道做对了）。
最后一句必须回扣开场的下注，明确告诉观众"你当时选的那个，错在哪/对在哪"。
禁止升华、禁止号召关注、禁止"希望对你有帮助"式收尾。

六、语言
自然、清晰、有画面感的现代口语。每句只承担一个主要信息；不复述画面已经
表达清楚的内容；不使用空洞过渡句、连续反问、夸张煽动和排比抒情。
关键结论允许短句独立成段，形成认知落点。

七、成稿自检（逐条核对，任一不过必须改写）
1. 第一句里有没有具体的人/时间/动作/数字？
2. 观众在前 6 秒能不能选出一个答案？
3. 第一份证据的四要素齐了吗？
4. 机制每一步是不是"先看见后命名"？
5. 迁移段用的是不是开场那个情境？
6. 三条行动是否都能自我检验？
7. 最后一句有没有回扣开场的下注？

【叙事节奏：情境驱动·下注—揭晓节奏】

目标成片 140-170 秒；旁白总字数 550-700 个中文字符，
按每秒 4.0-4.8 字估算，不得靠堆镜头数凑时长。

- 全片 12-16 个镜头。普通镜头承担一个明确论点或一个过程步骤，
  旁白 25-45 字；复杂机制拆成连续的语义阶段，不写成一个长镜
- 纯标题镜头不超过 2 秒，且全片最多一个；禁止在标题页上停留长旁白
- 前 6 秒必须出现下注点（具体问题、异常结果或二选一）；
  前 20 秒内完成第一次揭晓或证据反转
- 每 20-35 秒必须形成一次段落推进：新证据、新机制、新反例或新应用；
  连续两段没有新增信息即为不合格
- 密度调制：下注与揭晓段落更快（单镜 5-7 秒），机制解释段落放缓
  （单镜 8-12 秒），关键数字与结论镜前后各留 0.5-1 秒静默
- 镜头内部约每 2-4 秒出现一次有意义的新信息、关系变化或视觉结果；
  变化必须服务理解，禁止靠装饰动效维持热闹
- estimated_duration_seconds = 旁白字数 ÷ 4.4 + 画面复杂度补偿 0-1.5 秒，
  单镜不低于 3 秒（标题镜除外）、不高于 12 秒；全片合计落在 140-170 秒
- 删除清单：不增加信息的铺垫、同义重复、预告式句子（"接下来我们看看"）、
  泛泛总结

【内容结构：情境—证据—机制—迁移—行动】

第一段「情境与下注」（0%-12%）：直接呈现一个具体人物、处境或选择，
让观众在两个结果之间形成直觉判断。不出现视频标题、术语定义、作者介绍。

第二段「揭晓与证据」（12%-30%）：尽快揭晓反直觉结果，
并用一份最有说服力的实验、数据、案例或对照支撑，
证据须包含比较对象、关键数字、来源性质与结论边界。

第三段「机制拆解」（30%-68%）：核心机制拆成不超过三个相互衔接的步骤，
每步先展示可观察变化再命名概念，优先表现因果链、状态变化、
角色关系和数量变化，不连续堆叠定义。

第四段「现实迁移」（68%-88%）：回到开场的同一情境，
对比常见错误做法与更有效做法，让知识发生可见的行为变化。

第五段「行动与回扣」（88%-100%）：给出不超过三条带触发条件、
具体动作和自检方式的方法，最后一句回扣开场的下注形成闭环。

段落边界通过证据揭晓、关系反转、视觉锚点变形或场景复用自然过渡，
不使用孤立章节页反复打断叙事。
"""


COLOR_SCHEME_PROMPT = """\
【视觉系统：情境驱动·冷白现场】

〇、风格身份与适配原则
身份是：冷白现场画布 + 无衬线现场标注 + 认知紫单焦点 + 语义色克制 +
可复用的"情境舞台"。画面像一块被反复标注的白板现场，而不是插画海报。
根据选题选择对应的具象情境与几何隐喻，禁止机械复制任何示例中的
人物、道具或题材。

一、画布与留白（硬性要求）
- 横屏 16:9，背景全片固定冷白 #FAFAFC，直接铺满画布
- 允许用极浅紫 #F2EFFB 作局部区域底（对照区、证据区、行动卡），
  单个区域面积不超过画面 40%，禁止整片长期低对比淡紫
- 稳定画面负空间 55%-70%；一屏只解释一个关系
- 禁止黑边/左右黑柱、播放器控件、状态栏、通知条、描边字幕、黑底插片、
  片尾推荐卡

二、语义色（含义锁定，不得随意换色）
- 主墨紫 #211936：正文、主轮廓、公式
- 辅助灰紫 #756A91：次级说明、坐标、单位、来源标注
- 认知紫 #6C4FD4 / 高亮紫 #8B6FE8：当前叙事焦点、关键路径、核心概念
- 风险/错误/被推翻的直觉 #E85353
- 警示/待行动/条件限制 #F39A3D
- 理性/解释/机制 #258E9B
- 正确/完成/有效做法 #25A85A
- 人物与情境辅助 #D96C9D
- 浅分隔线 #D9D0EE；深结构线 #51456F
- 低透明底色场：淡紫 #F2EFFB、淡青 #E2F1F2、淡绿 #E4F4EA，
  只作 8%-18% 填充或区域底，不作主体色
每个稳定画面确定一个主导色 + 最多两个辅助语义色。
红只表达风险/错误/阻断，绿只表达正确/完成/有效，不作装饰。
颜色变化必须对应语义状态变化，禁止随机彩虹配色。

三、下注色规则（本风格身份动作）
- 观众可选的两个选项在下注时都保持中性：主墨紫轮廓 + 无填充
- 只有在揭晓那一刻才上色：被推翻的选项转 #E85353，成立的选项转 #25A85A
- 在揭晓之前给任一选项上语义色即为不合格（会提前泄底）

四、字体与现场标注排版
- 全片中文使用无衬线字（黑体系）；数字与公式使用 LaTeX 字形
- 标题短、置于画面左上或上方居中，不超过 14 个汉字，字重高于正文
- 一句话只给 1-2 个关键词着认知紫或语义色，其余保持主墨紫
- 关键数字放大独立成组，配一行小号灰紫单位/来源说明；
  证据镜必须能看见"和什么比"的对照项，不允许孤立数字
- 最终停留态文字必须完全可读、互不重叠；文字穿插只允许出现在
  不超过 0.35 秒的变形过渡中
- 移动端优先：核心数字、结论与当前动作在手机尺寸下必须最先被读到

五、图形词汇表（按选题取用，不要求全用）
1. 情境元素：抽象人物（圆头 + 短圆角躯干 + 两点一线表情，无写实五官）、
   位置点、行动路径、视线方向线、场景边框
2. 下注元素：两个并列的中性选项框、指向选项的手形/箭头、遮住结果的盖板
3. 证据元素：对照条、大数字、简洁坐标轴、样本点群、来源小字标签
4. 机制元素：因果箭头、状态方块、通道、分配条、循环回路
5. 迁移元素：同一场景的左右前后对照、错误做法划叉、有效做法勾选
6. 行动元素：不超过三条的编号短句卡（细框、直角或小圆角，无阴影）

六、造型纪律
- 统一细线宽，低饱和低透明填充；不做大面积卡片墙、投影 UI、3D 拟真、
  霓虹渐变、仪表盘
- 同一对象跨镜复用时轮廓、颜色和尺寸关系保持一致
- 装饰不得比主体更深、更大；背景装饰降低透明度与复杂度
- 自检：去掉标题后若不能在 2 秒内看懂主体之间的关系，
  必须删元素而不是等比缩小全部元素
"""


ANIMATION_STYLE_PROMPT = """\
【动画系统：情境驱动·现场推演】

总原则：相机固定。全片围绕一个「情境舞台」推进——开场建立的场景与人物
是后续所有解释的物理容器，机制、证据与迁移都在这块舞台上就地演化。
禁止每镜清空重画；锚点复用是本风格最重要的身份。

一、四类身份动作（本风格必须出现）
1. 下注（开场）
   两个中性选项并列建立 → 出现一个明确的"选哪个"提示（手形/箭头/问号）
   → 画面短暂静止 0.6-1.0 秒，给观众下注时间。禁止在此期间播放任何
   会暗示答案的高亮、抖动或颜色变化。
2. 揭晓（反转）
   遮盖被移开或结果条直接生长，被推翻的选项在同一位置转红并划叉，
   成立的选项转绿。反转必须发生在原选项自身上，禁止用新画面替换。
3. 就地拆解（机制）
   把揭晓后的主体原地展开为机制图：轮廓拉伸成通道、方块分裂成步骤、
   人物退到一侧成为参照。每步先播放可观察变化，变化停稳后再写出概念名，
   顺序不得颠倒。
4. 同场景对照（迁移）
   复用开场场景，左右或前后放置"常见做法"与"更有效做法"，
   两条路径同时推进到不同结果，结果差异用长度/数量/颜色直接可见。

二、动作占空比与时间
- 主要动作 0.55-1.10 秒；微动作 0.20-0.45 秒
- 同类元素错落间隔 0.06-0.16 秒
- 动作前留 0.2-0.4 秒观察起点；结论态留 0.8-1.6 秒读图
- 一个 beat 只承担一个主要语义变化，同时运动的独立对象不超过 3 组
- 揭晓镜的反转动作必须一次完成、干脆利落，不做二次强调

三、镜头内推进
采用「建立对象 → 发生变化 → 显示结果」。禁止镜头开始时一次性展示全部
元素，也禁止只播进场动画后长时间静止。前一阶段的视觉结果应成为后一阶段
的输入，通过移动、连接、分裂、聚合、替换、对照或强调持续演化。

四、跨镜转场优先级
1. 锚点变形：上一镜的人物、数字、路径或选项框改变形状/位置/标签，
   成为下一镜的解释对象
2. 舞台位移：情境舞台整体平移或缩放到局部特写，再展开新关系
3. 区域承接：淡紫区域底扩张为下一镜的证据区或行动区
4. 整组退场：仅当前后确实没有语义继承时，在 0.5 秒内整体淡出重建
全片不使用黑场和硬切；转场结束后画面必须回到冷白背景。

五、Manim 实现映射
- 线、框、路径：Create；文字与公式：Write
- 同类错落：LaggedStart / AnimationGroup，按空间阅读顺序组织
- 箭头与通道：GrowArrow / Create；粒子或对象传递：MoveAlongPath
- 就地变形：TransformMatchingShapes、TransformMatchingTex、
  ReplacementTransform、Transform
- 颜色是状态变量：用 animate.set_color / set_fill 改变，
  颜色变化与形状变化尽量放在同一次 play
- 跨镜复用上一镜变量，不重复创建看起来相同的新对象

六、生命周期与防碰撞
每个核心对象走完：建立 → 承载状态/关系 → 得出结论 → 复用变形或完整退场。
过渡时允许短暂穿插，但不超过 0.35 秒。每次 play 结束都检查标题、数字、
主体与标注的包围盒，稳定画面不得有文字压图或元素互相遮挡。
不再使用的辅助线、区域底和标注必须完整退场，禁止降透明后堆在角落。

七、禁止
- 所有镜头统一套用 FadeIn + shift
- 用 zoom / pan 代替对象关系变化
- 一次性播完整镜动画后长时间静止
- 每个 beat 重新创建标题、背景和主体
- 在观众下注之前用高亮、放大或颜色暗示正确答案
- 用循环、漂浮、呼吸缩放、脉冲或无信息量闪烁填满旁白时长
- 把录屏 UI、通知、字幕、黑柱、黑底插片或尾屏当作转场
"""


EXEMPLAR_PROMPT = """\
{
  "scenes": [
    {
      "scene_index": 0,
      "narration": "两家超市门口都摆了试吃台，一家摆 24 种果酱，一家只摆 6 种。你猜哪家卖得多？",
      "description": "冷白画布上建立情境舞台：左右两个中性主墨紫细框摊位，左框内 24 个小方块密排，右框内 6 个小方块疏排，中间一个灰紫问号。两个选项都不着语义色，画面在问号出现后静止，留出下注时间。",
      "estimated_duration_seconds": 7.0,
      "beats": [
        {
          "beat_index": 0,
          "cue_text": "两家超市门口都摆了试吃台，",
          "visual_action": "先画出中央一条极细的灰紫地面线，两个等大的主墨紫细框摊位从地面线两端依次生长出来，框内暂时为空。",
          "emphasis": "两家",
          "transition": "reveal",
          "fallback_weight": 1.0
        },
        {
          "beat_index": 1,
          "cue_text": "一家摆 24 种果酱，一家只摆 6 种。",
          "visual_action": "左框内 24 个小方块按阅读顺序错落填入并密排，右框内 6 个小方块疏排填入；两侧下方分别写出灰紫小号数字 24 与 6，方块与数字都保持主墨紫，不上语义色。",
          "emphasis": "24 种 / 6 种",
          "transition": "continue",
          "fallback_weight": 1.0
        },
        {
          "beat_index": 2,
          "cue_text": "你猜哪家卖得多？",
          "visual_action": "中央生长出一个灰紫问号，指向两个摊位的短箭头同时出现，随后画面完全静止 0.8 秒，不做任何高亮、放大或颜色变化。",
          "emphasis": "哪家",
          "transition": "continue",
          "fallback_weight": 1.0
        }
      ]
    },
    {
      "scene_index": 1,
      "narration": "6 种的那家，购买率是 30%；24 种那家只有 3%。停下试吃的人反而更多，但买单的少了十倍。",
      "description": "在同一情境舞台上就地揭晓：中央问号消散，两个摊位下方各生长出一条购买率对照条。左侧 24 种一方的条极短并转红，右侧 6 种一方的条明显更长并转绿，条旁标出 3% 与 30%，下方一行灰紫小字标注对照关系与来源性质。",
      "estimated_duration_seconds": 10.0,
      "beats": [
        {
          "beat_index": 0,
          "cue_text": "6 种的那家，购买率是 30%；",
          "visual_action": "问号收缩消失，右侧摊位框底部向右生长出一条较长的对照条并转为 #25A85A，条端写出放大的 30%。",
          "emphasis": "30%",
          "transition": "transform",
          "fallback_weight": 1.0
        },
        {
          "beat_index": 1,
          "cue_text": "24 种那家只有 3%。",
          "visual_action": "左侧摊位框底部生长出一条极短的对照条并转为 #E85353，条端写出 3%；两条同处一条基准线上，长度差直接可见。",
          "emphasis": "3%",
          "transition": "continue",
          "fallback_weight": 1.0
        },
        {
          "beat_index": 2,
          "cue_text": "停下试吃的人反而更多，但买单的少了十倍。",
          "visual_action": "左框上方浮出一个较高的灰紫细条表示停留人数更多，与下方的红色短条形成反向对照；画面底部写一行灰紫小字标明这是同一超市、同一时段的现场对照实验，随后停留读图。",
          "emphasis": "少了十倍",
          "transition": "continue",
          "fallback_weight": 1.0
        }
      ]
    },
    {
      "scene_index": 2,
      "narration": "选项越多，比较的次数就越多。每多一种，你要多做的不是一次判断，而是一整轮对比。",
      "description": "把左侧 24 个方块原地展开为机制图：方块退到画面左侧，中央生长出连接线网络，连线数量随方块增多而急剧变密。变化停稳后，右下角才写出概念名「比较成本」。",
      "estimated_duration_seconds": 11.0,
      "beats": [
        {
          "beat_index": 0,
          "cue_text": "选项越多，比较的次数就越多。",
          "visual_action": "左框边界淡出，24 个方块保持不变地移动到画面左侧排成弧形；先从 3 个方块之间画出 3 条认知紫连线，再扩展到 6 个方块的 15 条连线，连线逐条生长可数。",
          "emphasis": "比较的次数",
          "transition": "transform",
          "fallback_weight": 1.0
        },
        {
          "beat_index": 1,
          "cue_text": "每多一种，你要多做的不是一次判断，",
          "visual_action": "单独高亮新加入的一个方块，它与已有方块之间同时长出一束新连线；旁边短暂出现一个 #E85353 的划叉，否定「只多一次判断」的直觉。",
          "emphasis": "不是一次",
          "transition": "continue",
          "fallback_weight": 1.0
        },
        {
          "beat_index": 2,
          "cue_text": "而是一整轮对比。",
          "visual_action": "整束新连线一起加深为认知紫并短暂闪现一次，连线网络稳定后，右下角写出「比较成本」四字与一行灰紫注释，画面不再添加装饰。",
          "emphasis": "一整轮对比",
          "transition": "continue",
          "fallback_weight": 1.0
        }
      ]
    }
  ],
  "fact_checks": [
    {
      "claim_text": "在同一超市的果酱试吃现场对照实验中，选项较少的展台购买转化率显著高于选项较多的展台。",
      "scene_index": 1,
      "source_url": null,
      "source_description": "核查 Iyengar & Lepper 关于选择过载的果酱实验原始论文与后续重复研究的效应量结论。",
      "confidence": "medium",
      "is_hypothesis": false,
      "assumptions": "示意图中的条长只表达相对差异，不代表按原始数据等比绘制。",
      "controversy": "选择过载效应在后续元分析中并非在所有场景稳定复现，效应强度依赖商品类型、决策难度与消费者偏好清晰度。",
      "reviewer_verdict": null,
      "reviewer_note": null
    }
  ]
}"""


STYLE_TEMPLATE_DESCRIPTION = (
    "情境驱动的完整风格族：先让观众下注、再用带四要素的证据反转、"
    "机制先看见后命名、迁移回到同一情境、结尾给可自检的行动；"
    "冷白现场画布 + 认知紫单焦点视觉，配合下注/揭晓/就地拆解/同场景对照"
    "四类身份动作与锚点复用转场。"
)


OLD_NARRATIVE_PROMPT = '【叙事风格：情境驱动知识叙事】\n\n以一个观众能立即代入的具体处境、选择或冲突开场，不要先介绍术语、背景或定义。开头先让观众形成直觉判断，随后用事实、实验或反例制造认知反转，再解释背后的机制。\n\n叙事推进遵循“发生了什么 → 直觉为什么会判断错 → 证据说明什么 → 机制如何运作 → 现实中怎么做”。抽象概念必须先通过人物、行为、空间关系或可观察结果呈现，再给出概念名称。\n\n旁白使用自然、清晰、有画面感的现代口语。每句话只承担一个主要信息，不重复画面已经明确表达的内容，不使用空洞的过渡句、连续反问或夸张煽动。关键结论允许短句和停顿，形成认知落点。\n\n保持可信和克制：不把相关性说成因果，不为戏剧效果歪曲实验结论；有争议或依赖条件的观点要明确边界。\n\n结尾不要泛泛升华，应回到开头的具体处境，给出一个观众能够记住并执行的判断原则或行动方法。\n\n【叙事节奏：高留存标准节奏】\n\n目标成片时长为 140～170 秒，旁白总字数控制在 550～700 个中文字符，预计语速约为每秒 4.0～4.8 个中文字符。不要仅通过增加镜头数量控制时长。\n\n全片建议 12～16 个镜头。普通镜头承担一个明确论点或过程，旁白通常为 25～45 个中文字符；复杂机制可以更长，但应拆成连续的语义阶段。纯标题镜头应极短，不得用长旁白停留在标题页。\n\n前 6 秒必须出现具体问题、异常结果或需要观众判断的选择；前 20 秒内完成第一次信息反转或证据揭示。每 20～35 秒形成一次段落推进：新证据、新机制、新反例或新应用。\n\n保持信息密度变化：冲突与证据段落更快，机制解释段落适度放缓，关键数字和结论前后允许短暂停顿。删除不增加信息的铺垫、同义重复、预告式句子和泛泛总结。\n\n每个镜头内部应持续推进，约每 2～4 秒出现一次有意义的新信息、关系变化或视觉结果；变化必须服务理解，不能依赖无意义装饰维持热闹。\n\n【内容结构：情境—证据—机制—行动】\n\n第一段“情境与下注”（约全片 0%～12%）：直接呈现一个具体人物、处境或选择，让观众在两个结果之间形成直觉判断。不要先展示视频标题、术语定义或作者介绍。\n\n第二段“结果与证据”（约全片 12%～30%）：尽快揭示反直觉结果，并用一个最有说服力的实验、数据、案例或对照支撑。证据必须说明比较对象、关键数字和结论边界。\n\n第三段“机制拆解”（约全片 30%～68%）：将核心机制拆成不超过三个相互衔接的步骤。每一步先展示可观察变化，再命名概念。优先表现因果链、状态变化、角色关系和数量变化，不连续堆叠定义。\n\n第四段“现实迁移”（约全片 68%～88%）：回到一个与观众有关的现实场景，对比常见错误做法和更有效做法。尽量复用开头场景，让知识发生可见的行为变化。\n\n第五段“行动与回扣”（约全片 88%～100%）：给出不超过三条、动作明确、可以立即执行的方法。最后一句回扣开头的问题，形成闭环，不另起空泛升华。\n\n段落边界应通过证据揭晓、关系反转、视觉锚点变形或场景复用自然过渡，不使用孤立章节页反复打断叙事。'

OLD_NARRATIVE_DESCRIPTION = (
    "先让观众进入具体问题，再通过证据和机制完成认知反转；已并入叙事节奏与镜头结构组件"
)

NEW_NARRATIVE_DESCRIPTION = (
    "开场让观众下注，用带四要素的证据反转，机制先看见后命名，"
    "迁移回到同一情境，结尾给可自检的行动；已并入叙事节奏与镜头结构组件"
)


def _components_table() -> sa.Table:
    return sa.table(
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


def _upsert_components(rows: list[dict]) -> None:
    table = _components_table()
    for row in rows:
        stmt = postgresql.insert(table).values(**row)
        stmt = stmt.on_conflict_do_update(
            index_elements=["id"],
            set_={
                "category": stmt.excluded.category,
                "name": stmt.excluded.name,
                "description": stmt.excluded.description,
                "prompt_text": stmt.excluded.prompt_text,
                "is_builtin": stmt.excluded.is_builtin,
                "updated_at": stmt.excluded.updated_at,
            },
        )
        op.execute(stmt)


def _upsert_template(now: datetime, description: str) -> None:
    table = sa.table(
        "style_templates",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("name", sa.String),
        sa.column("description", sa.Text),
        sa.column("style_config", postgresql.JSONB),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    stmt = postgresql.insert(table).values(
        id=STYLE_TEMPLATE_ID,
        name="情境驱动·冷白现场",
        description=description,
        style_config={
            "narrative_style": str(NARRATIVE_ID),
            "color_scheme": str(STYLE_COMPONENT_IDS["color_scheme"]),
            "animation_style": str(STYLE_COMPONENT_IDS["animation_style"]),
            "exemplar": str(STYLE_COMPONENT_IDS["exemplar"]),
        },
        created_at=now,
        updated_at=now,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["id"],
        set_={
            "name": stmt.excluded.name,
            "description": stmt.excluded.description,
            "style_config": stmt.excluded.style_config,
            "updated_at": stmt.excluded.updated_at,
        },
    )
    op.execute(stmt)


def upgrade() -> None:
    """Rewrite the context-driven narrative blueprint and seed its style family."""
    now = datetime.now(timezone.utc)

    _upsert_components(
        [
            {
                "id": NARRATIVE_ID,
                "category": "narrative_style",
                "name": "情境驱动知识叙事",
                "description": NEW_NARRATIVE_DESCRIPTION,
                "prompt_text": NARRATIVE_PROMPT,
                "is_builtin": True,
                "created_by": None,
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": STYLE_COMPONENT_IDS["color_scheme"],
                "category": "color_scheme",
                "name": "情境驱动·冷白现场",
                "description": (
                    "冷白 #FAFAFC 现场画布、深墨紫无衬线标注、认知紫单焦点、"
                    "语义色含义锁定与揭晓前不上色的下注色规则"
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
                "name": "情境驱动·现场推演",
                "description": (
                    "情境舞台上的下注、揭晓、就地拆解与同场景对照四类身份动作；"
                    "锚点复用转场，禁止提前泄底与模板化进场"
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
                "name": "情境驱动·选择过载金样本",
                "description": (
                    "用选择过载选题示范下注静止、就地揭晓反转与机制原地展开，"
                    "防止生成端套用模板进场"
                ),
                "prompt_text": EXEMPLAR_PROMPT,
                "is_builtin": True,
                "created_by": None,
                "created_at": now,
                "updated_at": now,
            },
        ]
    )

    _upsert_template(now, STYLE_TEMPLATE_DESCRIPTION)


def downgrade() -> None:
    now = datetime.now(timezone.utc)

    style_templates = sa.table(
        "style_templates",
        sa.column("id", postgresql.UUID(as_uuid=True)),
    )
    op.execute(
        style_templates.delete().where(style_templates.c.id == STYLE_TEMPLATE_ID)
    )

    table = _components_table()
    op.execute(
        table.delete().where(
            table.c.id.in_(list(STYLE_COMPONENT_IDS.values()))
        )
    )
    op.execute(
        table.update()
        .where(table.c.id == NARRATIVE_ID)
        .values(
            description=OLD_NARRATIVE_DESCRIPTION,
            prompt_text=OLD_NARRATIVE_PROMPT,
            updated_at=now,
        )
    )
