-- AI video workflow database initialization SQL
-- Exported from the current PostgreSQL database schema and style-library data.
\set ON_ERROR_STOP on
BEGIN;
SET search_path TO public;

-- Schema
CREATE TABLE IF NOT EXISTS public.ai_business_model_configs (
	id UUID NOT NULL, 
	business VARCHAR(50) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	model_id UUID NOT NULL, 
	CONSTRAINT ai_business_model_configs_pkey PRIMARY KEY (id), 
	CONSTRAINT ai_business_model_configs_business_key UNIQUE NULLS DISTINCT (business)
);
CREATE TABLE IF NOT EXISTS public.ai_call_records (
	id UUID NOT NULL, 
	provider VARCHAR(50) NOT NULL, 
	model VARCHAR(150) NOT NULL, 
	request_type VARCHAR(20) NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	input JSONB NOT NULL, 
	output TEXT, 
	usage JSONB, 
	prompt_tokens INTEGER, 
	completion_tokens INTEGER, 
	total_tokens INTEGER, 
	cached_tokens INTEGER, 
	reasoning_tokens INTEGER, 
	input_cost NUMERIC(18, 8), 
	output_cost NUMERIC(18, 8), 
	total_cost NUMERIC(18, 8), 
	currency VARCHAR(10) NOT NULL, 
	duration_ms INTEGER, 
	error_type VARCHAR(200), 
	error_message TEXT, 
	started_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	completed_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	business VARCHAR(50) DEFAULT 'unknown'::character varying NOT NULL, 
	CONSTRAINT ai_call_records_pkey PRIMARY KEY (id)
);
CREATE TABLE IF NOT EXISTS public.ai_model_providers (
	id UUID NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	provider_type VARCHAR(30) NOT NULL, 
	base_url VARCHAR(300) NOT NULL, 
	api_key TEXT NOT NULL, 
	timeout_seconds DOUBLE PRECISION NOT NULL, 
	site_url VARCHAR(300), 
	site_name VARCHAR(100), 
	is_active BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	CONSTRAINT ai_model_providers_pkey PRIMARY KEY (id)
);
CREATE TABLE IF NOT EXISTS public.ai_provider_models (
	id UUID NOT NULL, 
	provider_id UUID NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	model VARCHAR(150) NOT NULL, 
	content_max_tokens INTEGER NOT NULL, 
	json_max_tokens INTEGER NOT NULL, 
	input_cost_per_million NUMERIC(18, 8) NOT NULL, 
	cached_input_cost_per_million NUMERIC(18, 8) NOT NULL, 
	output_cost_per_million NUMERIC(18, 8) NOT NULL, 
	is_active BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	CONSTRAINT ai_provider_models_pkey PRIMARY KEY (id)
);
CREATE TABLE IF NOT EXISTS public.alembic_version (
	version_num VARCHAR(32) NOT NULL, 
	CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);
CREATE TABLE IF NOT EXISTS public.code_versions (
	id UUID NOT NULL, 
	project_id UUID NOT NULL, 
	version_number INTEGER NOT NULL, 
	scenes JSONB, 
	fact_checks JSONB, 
	render_engine VARCHAR(20) NOT NULL, 
	ai_model VARCHAR(50), 
	rejection_context JSONB, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	prompt_snapshot JSONB, 
	CONSTRAINT script_versions_pkey PRIMARY KEY (id)
);
CREATE TABLE IF NOT EXISTS public.narrative_versions (
	id UUID NOT NULL, 
	project_id UUID NOT NULL, 
	version_number INTEGER NOT NULL, 
	scenes JSONB, 
	fact_checks JSONB, 
	ai_model VARCHAR(50), 
	rejection_context JSONB, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	prompt_snapshot JSONB, 
	CONSTRAINT narrative_versions_pkey PRIMARY KEY (id)
);
CREATE TABLE IF NOT EXISTS public.performance_records (
	id UUID NOT NULL, 
	project_id UUID NOT NULL, 
	platform VARCHAR(30) NOT NULL, 
	views INTEGER, 
	completion_rate DOUBLE PRECISION, 
	likes INTEGER, 
	favorites INTEGER, 
	comment_tags VARCHAR(30)[], 
	comment_summary TEXT, 
	recorded_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	CONSTRAINT performance_records_pkey PRIMARY KEY (id), 
	CONSTRAINT uq_performance_records_project_id UNIQUE NULLS DISTINCT (project_id)
);
CREATE TABLE IF NOT EXISTS public.project_events (
	id BIGSERIAL NOT NULL, 
	project_id UUID NOT NULL, 
	event_type VARCHAR(50) NOT NULL, 
	from_status VARCHAR(30), 
	to_status VARCHAR(30), 
	actor VARCHAR(50) NOT NULL, 
	payload JSONB, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	CONSTRAINT project_events_pkey PRIMARY KEY (id)
);
CREATE TABLE IF NOT EXISTS public.prompt_components (
	id UUID NOT NULL, 
	category VARCHAR(30) NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	description TEXT, 
	prompt_text TEXT NOT NULL, 
	is_builtin BOOLEAN NOT NULL, 
	created_by VARCHAR(100), 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	CONSTRAINT prompt_components_pkey PRIMARY KEY (id)
);
CREATE TABLE IF NOT EXISTS public.style_templates (
	id UUID NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	description TEXT, 
	style_config JSONB DEFAULT '{}'::jsonb NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	CONSTRAINT style_templates_pkey PRIMARY KEY (id)
);
CREATE TABLE IF NOT EXISTS public.topics (
	id UUID NOT NULL, 
	title VARCHAR(200) NOT NULL, 
	description TEXT, 
	source VARCHAR(50) NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	score_counterintuitive SMALLINT, 
	score_defensibility SMALLINT, 
	score_visual SMALLINT, 
	score_freshness SMALLINT, 
	composite_score DOUBLE PRECISION GENERATED ALWAYS AS ((((((score_counterintuitive + score_defensibility) + score_visual) + score_freshness))::numeric / 4.0)) STORED, 
	performance_score DOUBLE PRECISION, 
	tags VARCHAR(50)[], 
	needs_recheck BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	research_data JSONB DEFAULT '[]'::jsonb NOT NULL, 
	CONSTRAINT topics_pkey PRIMARY KEY (id)
);
CREATE TABLE IF NOT EXISTS public.users (
	id UUID NOT NULL, 
	username VARCHAR(80) NOT NULL, 
	password_hash VARCHAR(255) NOT NULL, 
	display_name VARCHAR(100), 
	role VARCHAR(20) NOT NULL, 
	is_active BOOLEAN NOT NULL, 
	last_login_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	CONSTRAINT users_pkey PRIMARY KEY (id), 
	CONSTRAINT uq_users_username UNIQUE NULLS DISTINCT (username)
);
CREATE TABLE IF NOT EXISTS public.video_assets (
	id UUID NOT NULL, 
	project_id UUID NOT NULL, 
	code_version_id UUID, 
	video_file_key VARCHAR(500), 
	duration_seconds DOUBLE PRECISION, 
	resolution VARCHAR(20), 
	status VARCHAR(20) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	render_log TEXT, 
	error_message TEXT, 
	CONSTRAINT video_assets_pkey PRIMARY KEY (id)
);
CREATE TABLE IF NOT EXISTS public.video_projects (
	id UUID NOT NULL, 
	topic_id UUID NOT NULL, 
	status VARCHAR(30) NOT NULL, 
	render_engine VARCHAR(20) NOT NULL, 
	tts_voice VARCHAR(50) NOT NULL, 
	aspect_ratio VARCHAR(20) NOT NULL, 
	current_code_version_id UUID, 
	current_video_asset_id UUID, 
	temporal_workflow_id VARCHAR(100), 
	retry_count SMALLINT NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	current_narrative_version_id UUID, 
	narrative_context JSONB DEFAULT '[]'::jsonb NOT NULL, 
	style_config JSONB DEFAULT '{}'::jsonb NOT NULL, 
	CONSTRAINT video_projects_pkey PRIMARY KEY (id)
);
CREATE TABLE IF NOT EXISTS public.worker_tasks (
	id UUID NOT NULL, 
	project_id UUID NOT NULL, 
	code_version_id UUID, 
	task_type VARCHAR(30) NOT NULL, 
	engine VARCHAR(30), 
	status VARCHAR(20) NOT NULL, 
	input_payload JSONB, 
	output_payload JSONB, 
	retry_count SMALLINT NOT NULL, 
	max_retries SMALLINT NOT NULL, 
	temporal_workflow_id VARCHAR(100), 
	signal_name VARCHAR(50), 
	worker_id VARCHAR(100), 
	started_at TIMESTAMP WITH TIME ZONE, 
	completed_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	CONSTRAINT worker_tasks_pkey PRIMARY KEY (id)
);
CREATE INDEX IF NOT EXISTS ix_ai_business_model_configs_business ON public.ai_business_model_configs (business);
CREATE INDEX IF NOT EXISTS ix_ai_call_records_business ON public.ai_call_records (business);
CREATE INDEX IF NOT EXISTS ix_ai_call_records_model ON public.ai_call_records (model);
CREATE INDEX IF NOT EXISTS ix_ai_call_records_provider ON public.ai_call_records (provider);
CREATE INDEX IF NOT EXISTS ix_ai_call_records_started_at ON public.ai_call_records (started_at);
CREATE INDEX IF NOT EXISTS ix_ai_call_records_status ON public.ai_call_records (status);
CREATE INDEX IF NOT EXISTS ix_ai_model_providers_provider_type ON public.ai_model_providers (provider_type);
CREATE INDEX IF NOT EXISTS ix_ai_provider_models_model ON public.ai_provider_models (model);
CREATE INDEX IF NOT EXISTS ix_ai_provider_models_provider_id ON public.ai_provider_models (provider_id);
CREATE INDEX IF NOT EXISTS idx_code_versions_project_id ON public.code_versions (project_id);
CREATE INDEX IF NOT EXISTS idx_users_is_active ON public.users (is_active);
CREATE INDEX IF NOT EXISTS idx_users_role ON public.users (role);
CREATE INDEX IF NOT EXISTS idx_users_username ON public.users (username);
CREATE INDEX IF NOT EXISTS ix_prompt_components_category ON public.prompt_components (category);

-- Data: alembic_version
INSERT INTO "alembic_version" ("version_num")
VALUES ('9b1c2d3e4f5a')
ON CONFLICT ("version_num") DO NOTHING;

-- Data: prompt_components
INSERT INTO "prompt_components" ("id", "category", "name", "description", "prompt_text", "is_builtin", "created_by", "created_at", "updated_at")
VALUES ('8ecd087d-e1be-425b-b5c7-6f00352ed3f9', 'animation_style', '语义驱动动态图解（副本）', '动画解释关系和过程，持续推进并避免模板化进场', '【动画系统：语义驱动动态图解】

动画的首要职责是解释知识变化，而不是装饰页面。每次主要运动都必须对应旁白中的一个新事实、关系、数量、状态或行动结果。

镜头内部采用“建立对象 → 发生变化 → 显示结果”的推进方式。不要在镜头开始时一次性展示全部元素，也不要只播放进场动画后长时间静止。前一阶段的视觉结果应尽量成为后一阶段的输入，通过移动、连接、分裂、聚合、替换、对比或强调持续演化。

根据内容选择视觉语法：人物与行为使用情境构图、视线、距离和行动路径；原因与结果使用方向明确的因果链；数量变化使用增长、分配、聚合和比例变化；正误判断使用同一场景的前后对照；实验与证据使用大数字、清晰对照和必要来源标识；抽象机制使用状态变化，不用一组同质圆点代替所有概念。

构图避免长期居中和过度留白。核心主体通常占画面主要视觉区域；根据叙事在全屏情境、左右对比、局部特写、流程关系和数据证据等版式之间切换。版式变化服务段落层级，不随机切换。

转场优先复用视觉锚点：让上一画面的核心人物、数字、图形或路径变形成下一画面的解释对象。只有在主题真正切换时才整体淡出重建。镜头切换需要保持动画流畅过渡，避免突然切换。

强调动作应短而明确，关键结果出现后留出可阅读时间。持续运动必须有语义，禁止用无意义循环、漂浮、呼吸或重复脉冲填满旁白时长。

装饰保持克制。光晕、阴影、弹性和粒子只用于突出当前重点，不作为所有镜头的统一模板。全片保持字体、圆角、线宽和图标语言一致。', false, NULL, '2026-07-03T08:57:06.766017+00:00'::timestamptz, '2026-07-03T08:58:37.017373+00:00'::timestamptz)
ON CONFLICT ("id") DO UPDATE SET "category" = EXCLUDED."category", "name" = EXCLUDED."name", "description" = EXCLUDED."description", "prompt_text" = EXCLUDED."prompt_text", "is_builtin" = EXCLUDED."is_builtin", "created_by" = EXCLUDED."created_by", "created_at" = EXCLUDED."created_at", "updated_at" = EXCLUDED."updated_at";
INSERT INTO "prompt_components" ("id", "category", "name", "description", "prompt_text", "is_builtin", "created_by", "created_at", "updated_at")
VALUES ('a1b2c3d4-0001-4000-8000-000000000001', 'narrative_style', '反差心理学', '从反直觉现象切入，揭示认知偏差，适合心理学/行为经济学类内容', '【叙事风格：反差心理学】
整体娓娓道来，从一个反直觉的问题或现象切入，引发认知冲突，逐步揭示背后的心理机制，结尾给出可操作的认知纠偏方法。
旁白负责讲解，每句话清晰有力，不空洞，不重复画面文字。
语气：平静而充满反思感，像一位向朋友分享洞见的智者。', true, NULL, '2026-07-01T06:14:21.897702+00:00'::timestamptz, '2026-07-01T06:14:21.897702+00:00'::timestamptz)
ON CONFLICT ("id") DO UPDATE SET "category" = EXCLUDED."category", "name" = EXCLUDED."name", "description" = EXCLUDED."description", "prompt_text" = EXCLUDED."prompt_text", "is_builtin" = EXCLUDED."is_builtin", "created_by" = EXCLUDED."created_by", "created_at" = EXCLUDED."created_at", "updated_at" = EXCLUDED."updated_at";
INSERT INTO "prompt_components" ("id", "category", "name", "description", "prompt_text", "is_builtin", "created_by", "created_at", "updated_at")
VALUES ('a1b2c3d4-0001-4000-8000-000000000004', 'pacing', '标准节奏（2-3分钟）', '15-20个镜头，每镜头30-50字旁白，适合大多数知识视频', '【叙事节奏：标准】
目标视频时长 2-3 分钟，需要 15-20 个镜头，每个镜头旁白约 30-50 字、时长 7-10 秒。
estimated_duration_seconds 根据旁白字数和画面复杂度估算，不得少于 5 秒。
先用直观图形和动态关系解释概念，再在确有必要时引入关键公式；公式服务于理解，不追求数量。', true, NULL, '2026-07-01T06:14:21.897702+00:00'::timestamptz, '2026-07-01T06:14:21.897702+00:00'::timestamptz)
ON CONFLICT ("id") DO UPDATE SET "category" = EXCLUDED."category", "name" = EXCLUDED."name", "description" = EXCLUDED."description", "prompt_text" = EXCLUDED."prompt_text", "is_builtin" = EXCLUDED."is_builtin", "created_by" = EXCLUDED."created_by", "created_at" = EXCLUDED."created_at", "updated_at" = EXCLUDED."updated_at";
INSERT INTO "prompt_components" ("id", "category", "name", "description", "prompt_text", "is_builtin", "created_by", "created_at", "updated_at")
VALUES ('a1b2c3d4-0001-4000-8000-000000000005', 'pacing', '快节奏（1分钟）', '8-12个镜头，每镜头20-30字旁白，适合短视频/竖屏格式', '【叙事节奏：快节奏】
目标视频时长约 1 分钟，需要 8-12 个镜头，每个镜头旁白约 20-30 字、时长 4-6 秒。
estimated_duration_seconds 不得少于 3 秒。
精简内容，只保留最核心的一个知识点，去掉所有铺垫和延伸。开头直接切入结论，结尾一句话总结。', true, NULL, '2026-07-01T06:14:21.897702+00:00'::timestamptz, '2026-07-01T06:14:21.897702+00:00'::timestamptz)
ON CONFLICT ("id") DO UPDATE SET "category" = EXCLUDED."category", "name" = EXCLUDED."name", "description" = EXCLUDED."description", "prompt_text" = EXCLUDED."prompt_text", "is_builtin" = EXCLUDED."is_builtin", "created_by" = EXCLUDED."created_by", "created_at" = EXCLUDED."created_at", "updated_at" = EXCLUDED."updated_at";
INSERT INTO "prompt_components" ("id", "category", "name", "description", "prompt_text", "is_builtin", "created_by", "created_at", "updated_at")
VALUES ('a1b2c3d4-0001-4000-8000-000000000006', 'scene_structure', '问题-分析-结论', '标准知识视频三段式结构', '【镜头结构：问题-分析-结论】
镜头 0-1：抛出问题或反直觉现象，引发好奇
镜头 2-4：拆解问题，建立分析框架
镜头 5-12：逐步展开分析，以图示和实例论证
镜头 13-15+：给出结论和实际启示', true, NULL, '2026-07-01T06:14:21.897702+00:00'::timestamptz, '2026-07-01T06:14:21.897702+00:00'::timestamptz)
ON CONFLICT ("id") DO UPDATE SET "category" = EXCLUDED."category", "name" = EXCLUDED."name", "description" = EXCLUDED."description", "prompt_text" = EXCLUDED."prompt_text", "is_builtin" = EXCLUDED."is_builtin", "created_by" = EXCLUDED."created_by", "created_at" = EXCLUDED."created_at", "updated_at" = EXCLUDED."updated_at";
INSERT INTO "prompt_components" ("id", "category", "name", "description", "prompt_text", "is_builtin", "created_by", "created_at", "updated_at")
VALUES ('a1b2c3d4-0001-4000-8000-000000000007', 'color_scheme', '亮底紫色系（默认）', '淡紫白背景 + 认知紫主色，适合心理学/思维类内容', '【配色系统：亮底紫色系】
背景主色（亮底）：#F7F3FF
亮底上的文字：#1C1433；辅助注释：#8E7DC0
核心概念色：认知紫 #6C4FD4、浅紫 #A98EE8
语义强调：错误红 #FF6B6B、警示橙 #FFB347、理性青 #4ECDC4、结论绿 #44CF6C、直觉粉 #FF9EBB
结构辅助：网格深底 #4A3880、网格亮底 #D4C5F0
配色原则：红色专用于偏差/错误，绿色专用于正确/结论，不可混用。以亮底 #F7F3FF 为主场景，主色饱和度高，确保手机小尺寸下清晰可辨。', true, NULL, '2026-07-01T06:14:21.897702+00:00'::timestamptz, '2026-07-01T06:14:21.897702+00:00'::timestamptz)
ON CONFLICT ("id") DO UPDATE SET "category" = EXCLUDED."category", "name" = EXCLUDED."name", "description" = EXCLUDED."description", "prompt_text" = EXCLUDED."prompt_text", "is_builtin" = EXCLUDED."is_builtin", "created_by" = EXCLUDED."created_by", "created_at" = EXCLUDED."created_at", "updated_at" = EXCLUDED."updated_at";
INSERT INTO "prompt_components" ("id", "category", "name", "description", "prompt_text", "is_builtin", "created_by", "created_at", "updated_at")
VALUES ('b2c3d4e5-0001-4000-8000-000000000001', 'narrative_style', '情境驱动知识叙事', '先让观众进入具体问题，再通过证据和机制完成认知反转', '【叙事风格：情境驱动知识叙事】

以一个观众能立即代入的具体处境、选择或冲突开场，不要先介绍术语、背景或定义。开头先让观众形成直觉判断，随后用事实、实验或反例制造认知反转，再解释背后的机制。

叙事推进遵循“发生了什么 → 直觉为什么会判断错 → 证据说明什么 → 机制如何运作 → 现实中怎么做”。抽象概念必须先通过人物、行为、空间关系或可观察结果呈现，再给出概念名称。

旁白使用自然、清晰、有画面感的现代口语。每句话只承担一个主要信息，不重复画面已经明确表达的内容，不使用空洞的过渡句、连续反问或夸张煽动。关键结论允许短句和停顿，形成认知落点。

保持可信和克制：不把相关性说成因果，不为戏剧效果歪曲实验结论；有争议或依赖条件的观点要明确边界。

结尾不要泛泛升华，应回到开头的具体处境，给出一个观众能够记住并执行的判断原则或行动方法。', true, NULL, '2026-07-02T07:13:22.255915+00:00'::timestamptz, '2026-07-02T07:13:22.255915+00:00'::timestamptz)
ON CONFLICT ("id") DO UPDATE SET "category" = EXCLUDED."category", "name" = EXCLUDED."name", "description" = EXCLUDED."description", "prompt_text" = EXCLUDED."prompt_text", "is_builtin" = EXCLUDED."is_builtin", "created_by" = EXCLUDED."created_by", "created_at" = EXCLUDED."created_at", "updated_at" = EXCLUDED."updated_at";
INSERT INTO "prompt_components" ("id", "category", "name", "description", "prompt_text", "is_builtin", "created_by", "created_at", "updated_at")
VALUES ('b2c3d4e5-0001-4000-8000-000000000002', 'pacing', '高留存标准节奏（2.5分钟）', '约150秒，每2～4秒产生一次有效信息或视觉变化', '【叙事节奏：高留存标准节奏】

目标成片时长为 140～170 秒，旁白总字数控制在 550～700 个中文字符，预计语速约为每秒 4.0～4.8 个中文字符。不要仅通过增加镜头数量控制时长。

全片建议 12～16 个镜头。普通镜头承担一个明确论点或过程，旁白通常为 25～45 个中文字符；复杂机制可以更长，但应拆成连续的语义阶段。纯标题镜头应极短，不得用长旁白停留在标题页。

前 6 秒必须出现具体问题、异常结果或需要观众判断的选择；前 20 秒内完成第一次信息反转或证据揭示。每 20～35 秒形成一次段落推进：新证据、新机制、新反例或新应用。

保持信息密度变化：冲突与证据段落更快，机制解释段落适度放缓，关键数字和结论前后允许短暂停顿。删除不增加信息的铺垫、同义重复、预告式句子和泛泛总结。

每个镜头内部应持续推进，约每 2～4 秒出现一次有意义的新信息、关系变化或视觉结果；变化必须服务理解，不能依赖无意义装饰维持热闹。', true, NULL, '2026-07-02T07:13:22.255915+00:00'::timestamptz, '2026-07-02T07:13:22.255915+00:00'::timestamptz)
ON CONFLICT ("id") DO UPDATE SET "category" = EXCLUDED."category", "name" = EXCLUDED."name", "description" = EXCLUDED."description", "prompt_text" = EXCLUDED."prompt_text", "is_builtin" = EXCLUDED."is_builtin", "created_by" = EXCLUDED."created_by", "created_at" = EXCLUDED."created_at", "updated_at" = EXCLUDED."updated_at";
INSERT INTO "prompt_components" ("id", "category", "name", "description", "prompt_text", "is_builtin", "created_by", "created_at", "updated_at")
VALUES ('b2c3d4e5-0001-4000-8000-000000000003', 'scene_structure', '情境—证据—机制—行动', '从具体冲突切入，以证据反转，解释机制后回到行动', '【内容结构：情境—证据—机制—行动】

第一段“情境与下注”（约全片 0%～12%）：直接呈现一个具体人物、处境或选择，让观众在两个结果之间形成直觉判断。不要先展示视频标题、术语定义或作者介绍。

第二段“结果与证据”（约全片 12%～30%）：尽快揭示反直觉结果，并用一个最有说服力的实验、数据、案例或对照支撑。证据必须说明比较对象、关键数字和结论边界。

第三段“机制拆解”（约全片 30%～68%）：将核心机制拆成不超过三个相互衔接的步骤。每一步先展示可观察变化，再命名概念。优先表现因果链、状态变化、角色关系和数量变化，不连续堆叠定义。

第四段“现实迁移”（约全片 68%～88%）：回到一个与观众有关的现实场景，对比常见错误做法和更有效做法。尽量复用开头场景，让知识发生可见的行为变化。

第五段“行动与回扣”（约全片 88%～100%）：给出不超过三条、动作明确、可以立即执行的方法。最后一句回扣开头的问题，形成闭环，不另起空泛升华。

段落边界应通过证据揭晓、关系反转、视觉锚点变形或场景复用自然过渡，不使用孤立章节页反复打断叙事。', true, NULL, '2026-07-02T07:13:22.255915+00:00'::timestamptz, '2026-07-02T07:13:22.255915+00:00'::timestamptz)
ON CONFLICT ("id") DO UPDATE SET "category" = EXCLUDED."category", "name" = EXCLUDED."name", "description" = EXCLUDED."description", "prompt_text" = EXCLUDED."prompt_text", "is_builtin" = EXCLUDED."is_builtin", "created_by" = EXCLUDED."created_by", "created_at" = EXCLUDED."created_at", "updated_at" = EXCLUDED."updated_at";
INSERT INTO "prompt_components" ("id", "category", "name", "description", "prompt_text", "is_builtin", "created_by", "created_at", "updated_at")
VALUES ('b2c3d4e5-0001-4000-8000-000000000004', 'color_scheme', '高对比亮底认知紫', '延续紫色品牌感，提高主体对比与移动端可读性', '【视觉系统：高对比亮底认知紫】

基础背景：暖白 #FBFAFF；允许使用极浅紫 #F3EEFF 构建局部区域，但不得让整片长期处于同一低对比淡紫色。

主要文字：深墨紫 #211936；辅助文字：灰紫 #756A91。核心文字与背景必须保持清晰对比，避免大面积使用浅紫小字。

品牌主色：认知紫 #6C4FD4；高亮紫 #8B6FE8。主色用于当前叙事焦点、关键路径和核心概念，不把所有节点同时染成主色。

语义颜色：风险/错误 #E85353；警示/待行动 #F39A3D；理性/解释 #258E9B；正确/完成 #25A85A；人物/情境辅助 #D96C9D。

结构颜色：浅分隔线 #D9D0EE；深结构线 #51456F。

每个画面确定一个主导色和最多两个辅助语义色。红色只表达风险、错误或阻断，绿色只表达正确、完成或有效行动，不作纯装饰。

关键主体应具有足够面积和明度对比；核心数字、结论和当前动作必须在手机尺寸下优先可读。背景装饰降低透明度和复杂度，不与主体争夺注意力。', true, NULL, '2026-07-02T07:13:22.255915+00:00'::timestamptz, '2026-07-02T07:13:22.255915+00:00'::timestamptz)
ON CONFLICT ("id") DO UPDATE SET "category" = EXCLUDED."category", "name" = EXCLUDED."name", "description" = EXCLUDED."description", "prompt_text" = EXCLUDED."prompt_text", "is_builtin" = EXCLUDED."is_builtin", "created_by" = EXCLUDED."created_by", "created_at" = EXCLUDED."created_at", "updated_at" = EXCLUDED."updated_at";
INSERT INTO "prompt_components" ("id", "category", "name", "description", "prompt_text", "is_builtin", "created_by", "created_at", "updated_at")
VALUES ('b2c3d4e5-0001-4000-8000-000000000005', 'animation_style', '语义驱动动态图解', '动画解释关系和过程，持续推进并避免模板化进场', '【动画系统：语义驱动动态图解】

动画的首要职责是解释知识变化，而不是装饰页面。每次主要运动都必须对应旁白中的一个新事实、关系、数量、状态或行动结果。

镜头内部采用“建立对象 → 发生变化 → 显示结果”的推进方式。不要在镜头开始时一次性展示全部元素，也不要只播放进场动画后长时间静止。前一阶段的视觉结果应尽量成为后一阶段的输入，通过移动、连接、分裂、聚合、替换、对比或强调持续演化。

根据内容选择视觉语法：人物与行为使用情境构图、视线、距离和行动路径；原因与结果使用方向明确的因果链；数量变化使用增长、分配、聚合和比例变化；正误判断使用同一场景的前后对照；实验与证据使用大数字、清晰对照和必要来源标识；抽象机制使用状态变化，不用一组同质圆点代替所有概念。

构图避免长期居中和过度留白。核心主体通常占画面主要视觉区域；根据叙事在全屏情境、左右对比、局部特写、流程关系和数据证据等版式之间切换。版式变化服务段落层级，不随机切换。

转场优先复用视觉锚点：让上一画面的核心人物、数字、图形或路径变形成下一画面的解释对象。只有在主题真正切换时才整体淡出重建。

强调动作应短而明确，关键结果出现后留出可阅读时间。持续运动必须有语义，禁止用无意义循环、漂浮、呼吸或重复脉冲填满旁白时长。

装饰保持克制。光晕、阴影、弹性和粒子只用于突出当前重点，不作为所有镜头的统一模板。全片保持字体、圆角、线宽和图标语言一致。', true, NULL, '2026-07-02T07:13:22.255915+00:00'::timestamptz, '2026-07-02T07:13:22.255915+00:00'::timestamptz)
ON CONFLICT ("id") DO UPDATE SET "category" = EXCLUDED."category", "name" = EXCLUDED."name", "description" = EXCLUDED."description", "prompt_text" = EXCLUDED."prompt_text", "is_builtin" = EXCLUDED."is_builtin", "created_by" = EXCLUDED."created_by", "created_at" = EXCLUDED."created_at", "updated_at" = EXCLUDED."updated_at";
INSERT INTO "prompt_components" ("id", "category", "name", "description", "prompt_text", "is_builtin", "created_by", "created_at", "updated_at")
VALUES ('b7a2f8c1-1002-4000-8000-000000000001', 'color_scheme', '暖白极简·多彩符号', '暖象牙白底、多彩循环主体色板、语义固定强调色、幽灵态状态语言与饱满构图规则', '【视觉系统：暖白极简·多彩符号】

一、背景基调
全片统一使用暖象牙白 #FAF7F0 背景，不使用纯白或深色背景，营造温纸质感。
画面保持约 30%-40% 负空间，每个镜头只有一个主要视觉中心。
留白必须是"有秩序的留白"——由标题、主体、标注三层撑起画面骨架后剩余的空间，
而不是元素过小、过少造成的空旷。

二、主体色板（用于图形元素、图标、数据系列）
- 珊瑚橙 #E8714A
- 青绿 #3DAA8C
- 蓝紫 #8B7BB5
- 宝蓝 #5B8DD9
- 金黄 #F0B429
同类元素成组出现时在主体色板内循环取色，形成多彩但和谐的群体感。
需要区分"主角与群众"时，主角用宝蓝或金黄并放大，群众用其余色循环。

三、语义强调色（含义固定，不得挪用）
- 砖红 #C4614A：代价、错误、约束、失败、警示
- 青绿 #3DAA8C：正确、成功、结论、正向方向
- 幽灵态：任意元素降为 fill_opacity 0.15-0.2 表示"未知/已排除/过去/失效"，
  这是表达状态退场的首选方式，优先于直接删除元素。

四、文字色
- 标题：依语义取砖红（困境/警示类）、青绿（结论/方法类）或深灰 #3C3C3C（中性）
- 辅助标注：暖灰 #8A7A6A，小字号，永远不与标题争夺注意力
- 结构线（分隔线、基准线、虚线框）：暖灰 #C0B0A0

五、页面元素与构图
每个镜头必须具备三层画面骨架，缺一即显空旷：
- 标题层：顶部居中或左上放置本镜头主题短语（不超过 10 字），
  除刻意留白的收尾镜头外每个镜头都有标题；关键标题下方可配细分隔线
- 主体层：核心图形整体占画面宽度的 50%-70%、高度的 30%-50%，
  居于画面中部；禁止主体缩成一条细带或一个小角落；页面元素要丰富，不可过于空旷
- 标注层：主体的关键部位配 2-4 个短标注（关键词、数字、小箭头），
  标注紧贴其锚定元素，不悬空

元素尺度规则：
- 单个图形元素的最小可辨识尺寸不低于画面高度的 4%；
  点阵/队列类元素单点直径不低于画面高度的 2%
- 群体元素数量以一眼可感知为度（一排不超过 20 个，矩阵不超过 8×8），
  数量本身是信息时优先用"少量大元素 + 计数数字"代替海量小元素
- 相邻元素间距 0.5-1.5 个元素宽度：既不粘连也不稀疏

区域与结构支撑：
- 画面出现分区语义（阶段、阵营、观察/选择区）时，必须用可见结构表达：
  虚线区域框、浅色底色块（填充透明度 0.08-0.15）或分隔线 + 区域标签，
  不能只靠元素颜色差异暗示分区
- 主体元素后方可放置同色系大圆或圆角矩形光晕衬底（填充透明度约 0.12）
  增加画面层次感和厚度

六、总原则
一屏之内主体色不超过 4 种加 1 个语义强调色。
色彩本身承载信息（状态、阵营、阶段），禁止纯装饰性用色。
同一概念跨镜头保持同色。
构图自检：若移除标题和标注后画面仍能成立，说明标注层缺失；
若主体缩到画面 1/4 以下，说明尺度失衡，必须放大主体或增加结构支撑。', true, NULL, '2026-07-05T09:30:59.919429+00:00'::timestamptz, '2026-07-05T09:47:52.746218+00:00'::timestamptz)
ON CONFLICT ("id") DO UPDATE SET "category" = EXCLUDED."category", "name" = EXCLUDED."name", "description" = EXCLUDED."description", "prompt_text" = EXCLUDED."prompt_text", "is_builtin" = EXCLUDED."is_builtin", "created_by" = EXCLUDED."created_by", "created_at" = EXCLUDED."created_at", "updated_at" = EXCLUDED."updated_at";
INSERT INTO "prompt_components" ("id", "category", "name", "description", "prompt_text", "is_builtin", "created_by", "created_at", "updated_at")
VALUES ('b7a2f8c1-1002-4000-8000-000000000002', 'narrative_style', '暖白极简·处境代入推演', '第二人称下注开场、概念命名延迟、预期反转与蓄势揭晓的悬念驱动叙事', '【叙事风格：暖白极简·处境代入推演】

一、切入方式
以观众亲身会遭遇的具体处境切入，而非直接给出概念定义。
先让观众体会到"直觉在此失灵"的困惑或代价，再引出严谨的解释，
最后落到超出知识本身的启示。

二、悬念与钩子工程（决定吸引力的核心规则）
- 开场 2 个镜头内必须用第二人称把观众拖进一道选择题或预判
  （"你会选哪个？""你觉得答案是多少？"），先让观众形成自己的立场
- 概念命名延迟：定律/效应/术语名称必须在观众亲眼看到反直觉结果
  之后才第一次出现；禁止在开头或前期镜头标题中亮出概念名——
  谜底不能写在谜面上
- 全片设计至少 2 次"预期→打破"：先把常识答案明确呈现在画面上
  （而不是一句话带过），再用实验、数据或推演将它推翻
- 关键数字揭晓前安排一句蓄势旁白（"结果出乎所有人意料"），
  揭晓那一句旁白只说数字和事实本身，不加解释；解释放到下一句/下一镜
- 在前 1/3 处埋一句利害钩子：告诉观众这件事正在影响他自己的
  某类日常决定，让后续推演与观众利益相关

三、旁白语气
像一个正在给你设局的聪明朋友：他知道谜底，故意一步步引你走进直觉
陷阱，语气里带着"你等着看"的笃定和一点狡黠，而不是照本宣科的讲解员。

- 多用第二人称和反问直接对观众说话："你确定吗？""换作是你呢？"
  全片至少 4-5 处，让观众始终处于被提问的位置
- 情绪有明确的起伏曲线：设问时上扬带钩、推演时平稳推进、
  蓄势时压低放慢、揭晓时短句直击、收尾时沉静有余味；
  禁止全片保持同一情绪强度
- 允许在打破预期处使用轻微的戏剧性表达："偏偏相反""诡异的是"
  "更过分的是"，制造转折的爽感
- 揭晓和结论用短促有力的断句，不超过 12 字，掷地有声
- 底线：不喊叫式营销腔（"太震撼了！""一定要看到最后！"）、
  不空洞感叹、不装神秘拖时间；每处情绪都必须由信息本身支撑

四、信息推进原则
- 每句旁白必须推进一个新信息（新事实、新转折、新视角），禁止复述已讲内容
- 旁白讲逻辑与含义，画面文字只承载关键词和数字，两者不得重复
- 诚实呈现方法或结论的局限与代价，避免制造万能感
- 结尾从知识升华到方法论或人生视角，用一句克制的话收束，不喊口号

五、禁止
说教式开场（"今天我们来讲"）、空洞形容（"非常神奇"）、堆砌术语、
无意义的总结复述、开头直接给出结论或概念名。', true, NULL, '2026-07-05T09:30:59.919429+00:00'::timestamptz, '2026-07-05T09:47:52.746218+00:00'::timestamptz)
ON CONFLICT ("id") DO UPDATE SET "category" = EXCLUDED."category", "name" = EXCLUDED."name", "description" = EXCLUDED."description", "prompt_text" = EXCLUDED."prompt_text", "is_builtin" = EXCLUDED."is_builtin", "created_by" = EXCLUDED."created_by", "created_at" = EXCLUDED."created_at", "updated_at" = EXCLUDED."updated_at";
INSERT INTO "prompt_components" ("id", "category", "name", "description", "prompt_text", "is_builtin", "created_by", "created_at", "updated_at")
VALUES ('b7a2f8c1-1002-4000-8000-000000000003', 'pacing', '暖白极简·密度分级节奏', '硬性镜头数下限、一镜一事拆分规则、按信息密度分级定时长', '【叙事节奏：暖白极简·密度分级节奏】

一、总量（硬性要求）
- 目标时长 2.5-3.5 分钟；实际时长由旁白字数决定，因此全片旁白总字数
  必须控制在 750-950 字之间，超出 950 字即为不合格输出
- scenes 数组长度必须在 18-24 之间，少于 18 个镜头即为不合格输出
- 每镜头旁白 25-40 字；单镜头旁白超过 45 字必须删减措辞或拆分镜头
- 镜头数与字数的关系：镜头多则每镜更短。22 个镜头时每镜旁白
  应压到 35 字左右，禁止"镜头又多、每镜又长"

二、一镜一事拆分规则（决定镜头数量的核心规则）
一个镜头只承载一个信息点：一个新概念、一次状态推演、一组对比或一个结论。
出现以下情况必须拆分为多个镜头，禁止压缩合并：
- "提出方案"与"推演该方案的后果"是两个镜头
- "展示现象"与"解释原因"是两个镜头
- 一个机制有 N 个步骤，就用 N 个镜头逐步演示，不得一镜带过
- 关键数字/结论单独占一个镜头，给观众停留时间
- 现实映射的每个场景各占一个镜头
写完后自检：若某镜头 description 里出现两次以上"然后/接着/再"，说明它塞了
多件事，必须拆开。

三、镜头时长按信息密度分级（全片平均须落在 8-9 秒）
- 引入/过渡镜头（1-2 个元素，单一信息点）：5-6 秒
- 展示镜头（并列卡片、群体元素、对比结构）：7-9 秒
- 推演镜头（多层元素 + 状态演化 + 标注）：9-12 秒，全片不超过 6 个
- 收尾镜头（极简元素 + 大量留白）：7-9 秒
任何镜头不得超过 12 秒；信息量确实撑满 12 秒的，拆成两个镜头。

四、节奏曲线
开场快（前 3 个镜头建立悬念），中段稳（推演层层递进），
高潮前安排一个短镜头蓄势，结尾放慢留白。

五、估算规则
estimated_duration_seconds = 旁白字数 ÷ 5 + 画面复杂度补偿 0-2 秒，
不低于 5 秒、不高于 12 秒。
全片 estimated_duration_seconds 之和必须落在 150-210 秒（2.5-3.5 分钟）：
- 不足 150 秒：内容深度不够，回到第三幕、第四幕补充推演步骤
- 超过 210 秒：逐镜删减旁白冗词（口头过渡、重复铺垫、修饰性从句），
  保持镜头数不变；旁白每句话只说必要信息，删掉不改变含义的字
beats 数量：引入镜头 1-2 个，展示镜头 2-3 个，推演镜头 3-4 个。', true, NULL, '2026-07-05T09:30:59.919429+00:00'::timestamptz, '2026-07-05T09:47:52.746218+00:00'::timestamptz)
ON CONFLICT ("id") DO UPDATE SET "category" = EXCLUDED."category", "name" = EXCLUDED."name", "description" = EXCLUDED."description", "prompt_text" = EXCLUDED."prompt_text", "is_builtin" = EXCLUDED."is_builtin", "created_by" = EXCLUDED."created_by", "created_at" = EXCLUDED."created_at", "updated_at" = EXCLUDED."updated_at";
INSERT INTO "prompt_components" ("id", "category", "name", "description", "prompt_text", "is_builtin", "created_by", "created_at", "updated_at")
VALUES ('b7a2f8c1-1002-4000-8000-000000000004', 'scene_structure', '暖白极简·五幕困境解法', '困境-规则-试错-解法-代价升华五幕结构，每幕有最小镜头数与内部展开模板', '【镜头结构：暖白极简·五幕困境解法】

五幕结构。每幕标注了最小镜头数，是硬性下限；全片合计不得少于 18 个镜头。
每幕给出内部展开模板，按模板逐镜展开，禁止把一幕压缩成一两个镜头。

第一幕·困境（至少 3 镜）：
1. 场景代入：呈现观众有代入感的具体处境，画面从单一元素开始
2. 观众下注：把处境收拢成一道二选一或预估题，两个选项并列呈现在
   画面上，旁白用第二人称引导观众先给出自己的答案
3. 悬置：暗示直觉答案可能有问题，但不揭晓，带着悬念进入下一幕
注意：本幕镜头标题只写现象或处境（如"一个奇怪的选择"），
禁止出现定律/效应/术语名——概念名最早在第四幕亮出。

第二幕·规则（至少 3 镜）：
1. 约束逐条呈现：每条关键约束用一个镜头（或一组并列卡片分镜头）展示
2. 约束叠加：多条约束同屏共存，让观众看到限制如何互相锁死
3. 难度定性：一个镜头明确"为什么直觉在这里会失灵"

第三幕·试错（至少 4 镜，每个直觉方案至少 2 镜）：
测试 1-2 个朴素/直觉方案（第一个必须是观众在第一幕下注的直觉答案），
每个方案按"提出 → 推演 → 失败结果"展开：
1. 方案提出：直觉策略以图形规则呈现
2. 方案推演：在已有模型上执行该策略，逐步展示过程
3. 失败显形：失败的代价用语义强调色和数字定格——这是第一次
   "预期→打破"，旁白要点明"你的直觉答案错了"这一层
两个方案时，第二个方案可压缩为"提出+推演失败"两镜。

第四幕·解法（至少 5 镜）：
信息密度最高的一幕，机制必须逐步构建而非一次给全：
1. 转折引入：宣告存在更优方法或更深解释，制造期待；
   概念/定律名称最早在此处第一次亮出
2. 机制拆解：方法的每个阶段/组成部分各占一个镜头（分区、分界线逐个出现）
3. 完整推演：在模型上完整走一遍新方法，展示其如何规避前面的失败
4. 蓄势 + 揭晓（两镜）：先用一个 3-5 秒短镜蓄势（旁白预告"结果出乎
   意料"，画面收敛安静）；紧接揭晓镜头——全片最反直觉的关键数字/
   结论作为画面唯一主体、全屏最大元素，使用语义强调色，
   这是全片的视觉高潮，禁止把该数字降级为小字标注
5. 原理点睛：一句话说透"为什么它有效"

第五幕·代价与升华（至少 3 镜）：
1. 代价诚实呈现：方法的局限或失败概率，用图形明确展示
2. 现实映射：将模型映射到 1-2 个普遍生活场景，各占一镜
3. 金句收尾：移除枝节只留核心元素，克制留白定格

连续性规则：
每一幕内部镜头之间保持视觉元素连续（复用同一批图形演化），
幕与幕之间才允许清场换景。
相邻镜头至少保留一个视觉锚点（核心人物、分界线、基准线或关键数字）。

自检：输出前核对每幕镜头数是否达到下限；若总数不足 18，
优先在第三幕补完整的"提出→推演→失败"链条、在第四幕细化机制拆解步骤。', true, NULL, '2026-07-05T09:30:59.919429+00:00'::timestamptz, '2026-07-05T09:47:52.746218+00:00'::timestamptz)
ON CONFLICT ("id") DO UPDATE SET "category" = EXCLUDED."category", "name" = EXCLUDED."name", "description" = EXCLUDED."description", "prompt_text" = EXCLUDED."prompt_text", "is_builtin" = EXCLUDED."is_builtin", "created_by" = EXCLUDED."created_by", "created_at" = EXCLUDED."created_at", "updated_at" = EXCLUDED."updated_at";
INSERT INTO "prompt_components" ("id", "category", "name", "description", "prompt_text", "is_builtin", "created_by", "created_at", "updated_at")
VALUES ('b7a2f8c1-1002-4000-8000-000000000005', 'animation_style', '暖白极简·原地生长动效', '原地 grow-in 入场、幽灵态代替删除、三层出场秩序的克制动画语言', '【动画系统：暖白极简·原地生长动效】

总原则：动画表达一次状态或信息的变化。

一、视觉层次
每个镜头分三层构建：结构层（分隔线/区域框/坐标）→ 主体层（图形/图标/数据）
→ 标注层（关键词/数字/箭头）。出场顺序：结构层 → 主体层 → 标注层。
标题固定于顶部，主体集中于中部区域。

二、入场规则
- 图形元素：在最终位置原地从零缩放放大出现（grow-in），禁止从屏幕外滑入
- 群体元素（同类元素排/阵）：按空间顺序依次 grow-in，错落间隔 0.1-0.2 秒，
  形成波浪式入场；单个元素约 0.3 秒
- 需要强调的单个主体：独立入场，约 0.5 秒，可配轻微回弹
- 标题与文字：淡入，约 0.4 秒；标注在其锚定元素出现后延迟约 0.2 秒跟随出现
- 关键数字：单独入场并适度放大定格，与旁白说出该数字的时刻对齐

三、状态变化规则（表达信息演化的核心手段）
- 排除/失效/过去：原地降为幽灵态（fill_opacity 0.15-0.2），保留轮廓不删除
- 选中/强调：放大 1.2-1.4 倍加颜色加深，可加同色外圈描边
- 转移焦点：旧焦点缩回原尺寸恢复常态色，新焦点同时放大，形成"接力"
- 群体状态批量变化：按空间顺序错落进行，呈扫过效果
- 对比/取舍：被否定一方变幽灵态或划线，被肯定一方高亮，二者动画同时进行
- 退场：当切换镜头时，不再使用的元素务必退场，避免与下一镜头产生遮挡

四、结构元素动画
- 分隔线/基准线：沿自身方向生长绘制，0.5-0.6 秒，画完后再出现两侧标签
- 区域框：先描边后填充，填充透明度不超过 0.15，约 0.7 秒
- 箭头：从起点向终点生长，约 0.4 秒，仅用于表达因果或指向
- 图表（饼图/柱状/进度）：数值从零生长到目标值，约 1 秒，
  让观众看到量的形成过程

五、beat 内时间分配
- 每个 beat 的主要视觉变化在该 beat 时间窗内完成，动作间可留 0.3-0.5 秒静置
- 首个 beat 完成结构层与主体层首批元素；后续 beat 只做增量
  （新增元素或状态变化）
- 相邻 beat 优先通过已有元素的变色、变形、移动、放缩衔接，避免清场重绘
- 镜头末尾保持最终画面静置，禁止补时用的空等待或循环动画

六、跨镜头连续性
- 同一幕内相邻镜头复用上一镜头的元素变量，元素空间位置保持一致
- 贯穿多镜头的固定角色/参照物，位置全片固定不移动
- 清场仅发生在幕间切换，用整体淡出完成，不逐个删除', true, NULL, '2026-07-05T09:30:59.919429+00:00'::timestamptz, '2026-07-05T09:47:52.746218+00:00'::timestamptz)
ON CONFLICT ("id") DO UPDATE SET "category" = EXCLUDED."category", "name" = EXCLUDED."name", "description" = EXCLUDED."description", "prompt_text" = EXCLUDED."prompt_text", "is_builtin" = EXCLUDED."is_builtin", "created_by" = EXCLUDED."created_by", "created_at" = EXCLUDED."created_at", "updated_at" = EXCLUDED."updated_at";
INSERT INTO "prompt_components" ("id", "category", "name", "description", "prompt_text", "is_builtin", "created_by", "created_at", "updated_at")
VALUES ('b7a2f8c1-1003-4000-8000-000000000001', 'color_scheme', '群像剧场·暖白符号剧场', '暖米白底、可数个体母题菜单（小人/粒子/图标物件）、条件式观众化身、大号语义数字与唯一黑场例外', '【视觉系统：群像剧场·暖白符号剧场】

一、背景基调
全片统一暖米白 #F8F4EB 背景，纸面质感，不用纯白与深色。
全片允许且仅允许一个"情感转场"镜头使用纯黑背景——黑场是稀缺资源，
第二次使用即失效，除该镜头外任何镜头不得改变背景。

二、主体母题（本风格的身份标识 + 按题材选型）
把核心概念翻译成"可数的、有状态的个体"是本风格不变的身份——
观众看到的是一群个体的处境变化，而不是抽象示意图。
个体是什么，按选题选定一种并贯穿全片，禁止中途混用：
- 群像小人（凡话题涉及人、选择、群体行为时首选）：
  圆头 + 方肩短身，无五官，靠颜色、体型、姿态、透明度表达状态
- 圆点/方块粒子（抽象数量、数据、概率、集合）：
  等大圆点或圆角方块，靠颜色、亮度、聚散表达状态
- 图标物件（话题主角是具体事物：硬币、星球、细胞、货币）：
  几何简笔风格图标，同一物件全片造型固定
个体通用规则（无论哪种母题）：
- 队列/阵列 10-25 个，等距排列，整体占画面宽度 70%-85%
- 主体色循环：宝蓝 #5B8DD9 / 青绿 #3DAA8C / 珊瑚橙 #E8714A /
  蓝紫 #8B7BB5，同组循环取色，制造"群体感"而非制服感
- 数量本身是信息时，配计数数字标注而不是堆更多个体

三、观众化身（条件规则）
- 话题涉及观众的决策、选择或视角时，设一个固定"你"角色：
  蓝紫色个体，位置固定在画面左上区域，配「你」或身份标签；
  "你"不进入队列，队列会动而"你"不动；
  "你"的动作（观察、拒绝、选择）用从"你"出发的箭头表达
- 纯客观现象/规律类话题可省略"你"角色，指示用中性箭头完成

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
三层骨架：顶部标题层 / 中部主体层 / 紧贴主体的标注层。
负空间 55%-70%；收尾镜头只留 1-3 个元素加大片留白。
自检：若一屏出现两个互相争夺注意力的大数字，或主体阵列缩到
画面宽度一半以下，即为不合格构图。', true, NULL, '2026-07-06T09:11:22.188565+00:00'::timestamptz, '2026-07-06T10:40:41.772950+00:00'::timestamptz)
ON CONFLICT ("id") DO UPDATE SET "category" = EXCLUDED."category", "name" = EXCLUDED."name", "description" = EXCLUDED."description", "prompt_text" = EXCLUDED."prompt_text", "is_builtin" = EXCLUDED."is_builtin", "created_by" = EXCLUDED."created_by", "created_at" = EXCLUDED."created_at", "updated_at" = EXCLUDED."updated_at";
INSERT INTO "prompt_components" ("id", "category", "name", "description", "prompt_text", "is_builtin", "created_by", "created_at", "updated_at")
VALUES ('b7a2f8c1-1003-4000-8000-000000000002', 'narrative_style', '群像剧场·张力驱动叙事', '不变内核（十秒认知张力、局中人、预期打破、诚实反面、金句收束）+ 钩子/命名/论证/升华四组按选题形态选取的菜单', '【叙事风格：群像剧场·张力驱动】

〇、选题形态判定（动笔前先判定，决定后文所有菜单的取法）
- 决策形：话题围绕"怎么选 / 怎么做"，存在可对比的策略与更优解
- 现象形：话题围绕"为什么会这样"，存在反常现象与背后机制
- 规律形：话题围绕"一条定律 / 效应"，存在核心结论与适用边界
判定一次，全片一致，禁止中途换形态。

一、不变内核（风格身份，任何选题不得省略）
1. 开场 10 秒内制造一次认知张力：让观众意识到"我以为的可能是错的"
   或"这件事不该是这样的"
2. 第二人称局中人：观众始终处于被提问、被代入的位置，全片至少 6 处
   第二人称，关键转折处直接质问观众
3. 至少一次完整的"预期→打破"：常识答案先在画面上立起来，再被推翻
4. 关键断言全部有数字或事实支撑，禁止无支撑的形容词
5. 揭晓之后必须出现诚实反面：代价、局限或边界，至少一处
6. 结尾迁移升华，用一句克制的金句收束

二、开场钩子菜单（四选一，选定后一以贯之，禁止叠用）
- 打脸式：第一句替观众说出常识判断（"只要……就总能……"句式），
  紧接反问加干脆否定。适用：大众普遍持有错误直觉的题
- 悬念数字式：亮出核心反常数字但绝不解释，数字当钩子、原理当悬念。
  适用：核心结论是一个惊人数字的题
- 反常现象式：直接演示一个"不该发生却发生"的现象，让画面先制造
  困惑。适用：现象形
- 切身困境式：把观众放进一个熟悉的两难处境，收拢成一道选择题让
  观众先下注。适用：决策形

三、概念命名时机（弹性规则）
- 概念命名不得晚于全片 1/3 处
- 概念名自带悬念感（有反差、令人好奇）→ 钩子落地后立即亮出，
  像介绍一位传奇人物出场，配学科出身（"在X理论中"）
- 概念名平淡 → 放在第一次预期打破之后，作为"这个现象有名字"的揭示

四、论证方式菜单（按形态取一种为主，至多再取一种为辅）
- 对照处刑（决策形首选）：让 1-2 个直觉方案先上台，用可量化的惨败
  数字当众处刑，失败具体到画面上谁被错过、错在哪一步；
  直觉方案的数字与最优解数字形成数量级反差
- 逐步排除（现象形首选）：把候选解释逐个摆上台再逐个划掉，
  每次排除都有依据，最后只剩真因
- 极端推演（规律形首选）：把规律推到极端参数或极端场景，
  让结论在极端处自己显形
- 反例检验（辅助）：用一个精心挑选的反例暴露常识或规律的边界
共同纪律：论证必须落到画面上"谁 / 什么发生了状态变化"，
禁止旁白空转讲道理而画面无事发生。

五、诚实反面（弹性规则）
- 揭晓后至少 1 镜反面：方法的代价、结论的失败概率或规律的适用边界
- 反面确有多层时才使用递进句式串联；只有一层时一击即可，禁止为凑气势硬造三连
- 反面用数字和画面支撑，不用感叹词渲染

六、升华菜单（四选一）
- 情感迁移：模型平移到爱情、人际、人生选择——同一套图形语言不换，
  只换标签与语境（话题与个人决策相关时首选）
- 方法论迁移：把结论抽象成一条可带走的决策原则
- 敬畏收束：回到自然或数学本身的深邃与秩序（纯自然科学题首选）
- 开放问题：抛出一个至今无解的延伸问题，把好奇心留给观众
金句收尾规则不变：对仗句式，回扣核心数字或核心意象，
冷酷与温情（或严谨与浪漫）同框。

七、禁止
说教开场（"今天我们来讲"）、揭晓后自夸（"是不是很神奇"）、
无数字支撑的形容词、结尾喊口号、通篇第三人称冷讲解、
为凑风格硬造打脸或硬凑三连拆台。', true, NULL, '2026-07-06T09:11:22.188565+00:00'::timestamptz, '2026-07-06T10:40:41.772950+00:00'::timestamptz)
ON CONFLICT ("id") DO UPDATE SET "category" = EXCLUDED."category", "name" = EXCLUDED."name", "description" = EXCLUDED."description", "prompt_text" = EXCLUDED."prompt_text", "is_builtin" = EXCLUDED."is_builtin", "created_by" = EXCLUDED."created_by", "created_at" = EXCLUDED."created_at", "updated_at" = EXCLUDED."updated_at";
INSERT INTO "prompt_components" ("id", "category", "name", "description", "prompt_text", "is_builtin", "created_by", "created_at", "updated_at")
VALUES ('b7a2f8c1-1003-4000-8000-000000000003', 'pacing', '群像剧场·1.2倍速快节奏', '按 1.2 倍速 TTS 校准的时长估算、快-稳-爆-缓节奏曲线与一拍一动作的高密度推进', '【叙事节奏：群像剧场·1.2倍速快节奏】

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
- 快：前 3 镜（钩子 + 概念引入）合计不超过 25 秒，
  开场 10 秒内完成第一次认知张力
- 稳：设定与论证区间匀速推进，一镜一个信息点，不加速也不拖长
- 爆：关键揭晓独占一镜，旁白只有一句（不超过 25 字），
  该镜前可安排一个 4-5 秒短镜蓄势
- 缓：升华与收尾镜头允许降密度——句子变短、旁白字数降到
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
- 递进换挡词（"更扎心的是 / 更过分的是"）是快节奏中的合法减速带，
  全片不超过 3 次
- 画面已呈现的信息旁白不重复，只讲画面看不出的逻辑与含义

五、自检
全片 estimated_duration_seconds 之和须落在 150-180 秒：
不足 150 秒回到论证段补推演步骤；超过 180 秒逐镜删旁白冗词，
保持镜头数不变。', true, NULL, '2026-07-06T09:11:22.188565+00:00'::timestamptz, '2026-07-06T10:40:41.772950+00:00'::timestamptz)
ON CONFLICT ("id") DO UPDATE SET "category" = EXCLUDED."category", "name" = EXCLUDED."name", "description" = EXCLUDED."description", "prompt_text" = EXCLUDED."prompt_text", "is_builtin" = EXCLUDED."is_builtin", "created_by" = EXCLUDED."created_by", "created_at" = EXCLUDED."created_at", "updated_at" = EXCLUDED."updated_at";
INSERT INTO "prompt_components" ("id", "category", "name", "description", "prompt_text", "is_builtin", "created_by", "created_at", "updated_at")
VALUES ('b7a2f8c1-1003-4000-8000-000000000004', 'scene_structure', '群像剧场·五段张力骨架', '钩子-设定-张力-反面-升华五段固定骨架，每段提供按选题形态选取的实现模板与镜头纪律', '【镜头结构：群像剧场·五段张力骨架】

总原则：固定的是张力骨架与镜头纪律，不固定具体剧情。
全片 16-20 镜，五段按序推进；每段给出按选题形态
（决策形 / 现象形 / 规律形，与叙事风格组件的判定保持一致）
选取的实现模板，选定后段内一以贯之。

第一段·钩子（1-2 镜）
按选定的钩子类型实现：
- 打脸式：常识陈述 + 当场否定（两镜，或一镜两拍：画面先立后灰）
- 悬念数字 / 反常现象式：数字或现象独占一镜，第二镜提出"为什么"
- 切身困境式：处境呈现一镜 + 收拢成选择题一镜，观众先下注

第二段·设定（2-4 镜）
1. 概念亮相镜：概念名与别名大字标题卡待遇（位置按命名时机规则，
   可前移至钩子后或后移至首次打破后）
2. 世界观镜：核心模型与主体阵列入场，交代对象、数量与条件
3. 规则/前提镜：决策形用"你只能 / 你必须"卡片逐条立起；
   现象形、规律形用"已知条件"逐条呈现；3 条以上拆镜

第三段·张力（4-7 镜，信息密度最高的一段）
共同纪律：
- 至少一次完整"预期→打破"：常识答案先在画面立起来，再被推翻
- 一镜只推进一步；高潮揭晓独占一镜，全片最反直觉的数字或结论
  作为画面唯一主体，揭晓前可安排一个 4-5 秒短镜蓄势
按论证方式展开：
- 对照处刑（决策形）：实验设定 → 直觉方案A提出并处刑（1-2 镜）→
  直觉方案B处刑（可选 1 镜）→ 更优方案分步执行（2 镜）→ 对比揭晓
- 逐步排除（现象形）：候选解释并列上台 → 逐个检验划掉（每个 1 镜）
  → 真因揭示 → 机制完整演示
- 极端推演（规律形）：规律小尺度呈现 → 参数逐级放大（每级 1 镜）
  → 极端结果揭晓 → 原理点睛

第四段·反面（1-3 镜）
揭晓后的诚实反面：代价、失败概率或适用边界，每层一镜；
单层一击即可，确有多层才用递进标题串联，禁止硬凑

第五段·升华（2-3 镜）
1. 迁移镜：按升华菜单（情感 / 方法论 / 敬畏 / 开放问题）实现；
   允许 0-1 个黑场隐喻镜头，仅在情感迁移时使用，其余升华不强制黑场
2. 现实描摹镜（可选）：用最简阵列重演观众自己的日常行为
3. 金句收尾镜：清场只留核心数字或 1-2 个元素，对仗句定格

连续性规则：
- 同一套主体母题贯穿全片复用；段内禁止清场，清场只发生在段间
- 分区虚线、基准线一旦建立即跨镜保留
- 相邻镜头至少保留一个视觉锚点
- 黑场硬切全片至多一次

自检：五段俱全且顺序不乱；张力段不少于 4 镜；
某镜同时承担两段职能的，拆镜；总数不足 16 镜时优先在张力段
补完整的论证链条。', true, NULL, '2026-07-06T09:11:22.188565+00:00'::timestamptz, '2026-07-06T10:40:41.772950+00:00'::timestamptz)
ON CONFLICT ("id") DO UPDATE SET "category" = EXCLUDED."category", "name" = EXCLUDED."name", "description" = EXCLUDED."description", "prompt_text" = EXCLUDED."prompt_text", "is_builtin" = EXCLUDED."is_builtin", "created_by" = EXCLUDED."created_by", "created_at" = EXCLUDED."created_at", "updated_at" = EXCLUDED."updated_at";
INSERT INTO "prompt_components" ("id", "category", "name", "description", "prompt_text", "is_builtin", "created_by", "created_at", "updated_at")
VALUES ('b7a2f8c1-1003-4000-8000-000000000005', 'animation_style', '群像剧场·状态流转词汇表', '阵列波浪入场、六态状态词汇表（已阅/被拒/否决/离场/焦点/锁定）、数字弹性定格与做减法收尾', '【动画系统：群像剧场·状态流转】

总原则：动画只做一件事——把"个体"的状态变化演出来。
每个动作对应一次语义变化（入场 / 被检验 / 被排除 / 被选中 / 被错过），
禁止装饰性运动；宁可静止也不做无意义的循环与飘动。

一、入场
- 队列/阵列：按空间顺序波浪式 grow-in（原地从零放大 + 轻微过冲），
  单个约 0.3 秒，间隔 0.08-0.15 秒；禁止屏幕外滑入
- "你"角色（如设有）：独立入场约 0.5 秒，之后全片位置锁定不移动
- 标题淡入 0.4 秒；标注在锚定元素出现后延迟 0.2 秒跟随

二、状态流转词汇表（核心，含义锁定）
- 已检验 / 已流逝：fill_opacity 降到 0.25-0.35，保留原位不删除
- 被排除 / 被拒绝：变灰 + 整体下沉（小人母题配垂头姿态）
- 被否决（强调版）：砖红斜线从左上划过该元素，0.3 秒
- 被错过 / 已离场：只剩空心轮廓（描边保留、填充清空），
  这是比变灰更重的终局状态
- 当前焦点：放大 1.2-1.4 倍加同色描边；转移焦点时旧焦点缩回、
  新焦点放大，同时进行形成接力
- 最终选中锁定：金黄光圈 + 对勾，每个论证过程至多出现一次

三、指向与出手
- 设有"你"角色时："你"的观察与出手一律用灰色细长箭头表达，
  从"你"出发向目标生长约 0.4 秒；扫视多个对象时箭头依次指向，
  被扫过者转入"已检验"态，形成波浪扫过效果
- 无"你"角色时：因果与指向用中性灰箭头，仅用于表达因果或指向，
  禁止装饰性箭头

四、结构与数字
- 分区虚线：自上而下生长 0.5 秒，画完后两侧标签淡入；
  建立后跨镜保留，不重绘
- 基准/标尺线：从参照个体处水平生长并保留至段结束
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
- 同段镜头间禁止清场：阵列、虚线、标尺原位继承，只做增量变化
- 段间切换用整体淡出淡入
- 黑场硬切全片至多一次，仅用于情感迁移镜头（切入切出各一次）
- 收尾做减法：元素逐层淡出，最后只留 1-3 个元素加大片留白定格

七、禁忌
无意义弹跳、持续旋转、频繁闪白、装饰粒子、每句清场重绘、
所有元素同帧出现、屏幕外滑入、黑场滥用。', true, NULL, '2026-07-06T09:11:22.188565+00:00'::timestamptz, '2026-07-06T10:40:41.772950+00:00'::timestamptz)
ON CONFLICT ("id") DO UPDATE SET "category" = EXCLUDED."category", "name" = EXCLUDED."name", "description" = EXCLUDED."description", "prompt_text" = EXCLUDED."prompt_text", "is_builtin" = EXCLUDED."is_builtin", "created_by" = EXCLUDED."created_by", "created_at" = EXCLUDED."created_at", "updated_at" = EXCLUDED."updated_at";
INSERT INTO "prompt_components" ("id", "category", "name", "description", "prompt_text", "is_builtin", "created_by", "created_at", "updated_at")
VALUES ('b7a2f8c1-1004-4000-8000-000000000001', 'color_scheme', '记忆唤醒·白底明亮知识卡片', '纯白底、学科主色条带、明黄结论胶囊、竖屏三层卡片骨架与幽灵态残缺开场', '【视觉系统：记忆唤醒·白底明亮知识卡片 v2】

〇、Manim 代码强制要求（最高优先级，违反则视频不可用）

1. 背景颜色
   每个 Scene 的 construct() 方法第一行必须写：
       self.camera.background_color = "#FFFFFF"
   Manim 默认背景为黑色。不写这行，视频背景全黑，文字看不清。

2. 字体大小（frame_height=16、frame_width=9 的竖屏坐标系）
   Manim 的 font_size 单位不是像素。frame_height=16 时，font_size=48 的文字
   高约 1 frame 单位，极易超出画面边界。必须使用以下数值：
   - 顶部标题（Text）：font_size=32，绝对不超过 36
   - 图解标注（Text）：font_size=24
   - 结论胶囊文字（Text）：font_size=28
   - 数学公式（MathTex）：font_size=36，绝对不超过 42
   - 小号辅助说明：font_size=20

3. 坐标安全区
   所有元素（文字、图形、公式）必须保持在以下范围内：
   - 水平：x ∈ [-3.8, 3.8]（画面宽 9 个单位，留 0.7 边距）
   - 垂直：y ∈ [-7.0, 7.0]（画面高 16 个单位，留 1.0 边距）
   放置元素前用 .get_width() / .get_height() 检查尺寸是否合法。

一、背景与分区
- 主背景：纯白 #FFFFFF（通过 self.camera.background_color 设置）
- 卡片内分区底色：浅灰 Rectangle，fill_color="#F4F6F9"，fill_opacity=1

二、学科主色（同一视频内固定，跨镜头不变）
- 数学：钴蓝 #2563EB（ManimColor: "#2563EB"）
- 物理：橙红 #EA580C
- 化学：翠绿 #16A34A
视频开始时由选题学科决定本片主色，全片不混用。

三、结论高亮（语义固定）
- 明黄底 Rectangle：fill_color="#FEF08A"，fill_opacity=1，圆角 corner_radius=0.15
- 文字颜色：#1E293B

四、图解线条
- 主线/坐标轴：color="#1E293B"，stroke_width=3
- 标注箭头：color=学科主色，stroke_width=2.5
- 辅助虚线：DashedLine，color="#94A3B8"，stroke_width=1.5

五、幽灵态（开场专用）
- fill_opacity=0.15，stroke_opacity=0.15
- 仅用于第一镜头的残缺图解，其他镜头不使用

六、三层卡片骨架（每镜头必须具备）
顶层（y ∈ [6.0, 7.0]）：
  - 学科主色色条带：Rectangle，width=9，height=1.0，fill_color=学科主色
  - 标题 Text 叠于色条带上，color=WHITE，font_size=32
主体区（y ∈ [-3.0, 5.5]）：Manim 图解动画，逐步构建
底层（y ∈ [-7.0, -5.0]）：
  - 明黄底 Rectangle，width=8.5，height=1.8，y=-6.0
  - 结论文字 Text，font_size=28，color="#1E293B"，置于矩形中央

七、用色纪律
- 单镜头主色不超过 3 种（背景白 + 学科主色 + 结论黄）
- 色彩承载语义，禁止纯装饰性用色', true, NULL, '2026-07-08T08:05:43.040091+00:00'::timestamptz, '2026-07-08T09:43:30.297045+00:00'::timestamptz)
ON CONFLICT ("id") DO UPDATE SET "category" = EXCLUDED."category", "name" = EXCLUDED."name", "description" = EXCLUDED."description", "prompt_text" = EXCLUDED."prompt_text", "is_builtin" = EXCLUDED."is_builtin", "created_by" = EXCLUDED."created_by", "created_at" = EXCLUDED."created_at", "updated_at" = EXCLUDED."updated_at";
INSERT INTO "prompt_components" ("id", "category", "name", "description", "prompt_text", "is_builtin", "created_by", "created_at", "updated_at")
VALUES ('b7a2f8c1-1004-4000-8000-000000000002', 'narrative_style', '记忆唤醒·记忆钩子三段式', '唤醒-重建-升华三段式，第二人称记忆钩子开场，残缺图解提问，语气像一起回忆而非重新教', '【叙事风格：记忆唤醒·记忆钩子三段式 v2】

一、核心气质
不是在教陌生知识，而是在帮观众找回遗忘的记忆。
语气像同龄人聊天："你肯定学过这个，只是忘了——来，咱们一起想想。"
亲切不说教，有趣不油腻，理科严谨但不学术腔。

二、三段式结构（叙事骨架，镜头总数不得少于 10 个）

第一段——唤醒（2-3 镜头）
目标：让观众在 3 秒内产生"我学过这个！"的模糊记忆感。
镜头 1：显示残缺图解（核心元素幽灵态）+ 第二人称提问
  "还记得初中物理课的这张图吗？这里是什么，你想到了吗？"
镜头 2：部分揭晓，给观众即时满足感，引发好奇"后面还有什么"
镜头 3（可选）：设置本视频的核心悬念/问题

第二段——重建（5-7 镜头，每镜一个推导步骤）
目标：一步步重新推导，让观众"哦对！就是这样！"
- 每个推导步骤独占一个镜头，配合 Manim 图解或公式变换动画
- 语气用"对，就是这一步" / "你想到了吗？" / "没错——"
- 公式用 MathTex 渲染，步骤间用 TransformMatchingTex 连接
- 结论/公式名称在推导完成后才亮出（延迟命名）
- 不假设观众记得细节，但不当外行——他学过，只是忘了

第三段——升华（1-2 镜头）
目标：让职场观众感到"这个知识其实还在用"。
- 一句话现实延伸，克制不展开
- 结论胶囊放最核心的那句话

三、旁白语气规则
- 多用第二人称和反问，全片至少 4 处
- 短句为主，每句 10-18 字
- 每句推进一个新信息，禁止复述已讲内容
- 旁白讲逻辑，画面承载图解，两者不重复

四、钩子工程
- 开场残缺图解是最强钩子
- 第二镜必须"揭晓"第一镜的问题
- 每 2-3 镜安排一次小"对了！"时刻

五、禁止
说教开场、空洞形容、喊口号、提前给答案、通篇冷讲解、
把观众当成从未学过的外行、把多个推导步骤压缩进一个镜头。', true, NULL, '2026-07-08T08:05:43.040091+00:00'::timestamptz, '2026-07-08T09:43:30.297045+00:00'::timestamptz)
ON CONFLICT ("id") DO UPDATE SET "category" = EXCLUDED."category", "name" = EXCLUDED."name", "description" = EXCLUDED."description", "prompt_text" = EXCLUDED."prompt_text", "is_builtin" = EXCLUDED."is_builtin", "created_by" = EXCLUDED."created_by", "created_at" = EXCLUDED."created_at", "updated_at" = EXCLUDED."updated_at";
INSERT INTO "prompt_components" ("id", "category", "name", "description", "prompt_text", "is_builtin", "created_by", "created_at", "updated_at")
VALUES ('b7a2f8c1-1004-4000-8000-000000000003', 'pacing', '记忆唤醒·短视频竖屏节奏', '60-90秒总时长、8-12镜、每镜5-8秒卡片节奏，开场3秒必现课本感元素', '【叙事节奏：记忆唤醒·短视频竖屏节奏 v2】

〇、时长估算基准
estimated_duration_seconds = 旁白字数 ÷ 5 + 画面复杂度补偿 0-2 秒
单镜不低于 5 秒、不高于 12 秒。

一、总量（硬性要求，违反即为不合格输出）
- 成片目标：75-100 秒
- scenes 数组长度：10-14 个（不足 10 个必须补充推导步骤）
- 全片旁白总字数：375-500 字
- 每镜旁白：30-50 字；超过 50 字必须拆镜

二、镜头分配规则
唤醒段：2-3 镜，合计 15-20 秒
重建段：5-7 镜，每镜处理一个且仅一个推导步骤，5-10 秒
升华段：1-2 镜，4-8 秒

重建段镜头拆分规则（一镜一步骤，不得合并）：
- 提问/展示残缺图解：1 镜
- 每个公式推导步骤：1 镜（如"设 x = 0.999…"是 1 镜，"两边×10"是 1 镜，"两式相减"是 1 镜）
- 结论揭示：1 镜
- 现实映射：1 镜
写完后自检：若某镜头 description 里出现两次以上"然后/接着/再"，必须拆开。

三、镜头时长按信息密度分级
- 提问/唤醒镜头（1-2 个元素）：5-7 秒
- 单步推导镜头（公式变换或图形构建）：6-10 秒
- 复杂图解镜头（多元素同屏+标注）：8-12 秒，全片不超过 3 个
- 升华/收尾镜头：5-8 秒

四、旁白措辞纪律
- 短句直给，每句 10-18 字
- 前一句说过的内容不得复述
- 禁止口头过渡句，镜头切换靠画面衔接
- 画面已呈现的公式/图解旁白不复述，只讲逻辑含义

五、自检
全片 estimated_duration_seconds 之和须落在 75-100 秒：
- 不足 75 秒：在重建段拆分推导步骤，补充镜头
- 超过 100 秒：逐镜删旁白冗词，保持镜头数不变', true, NULL, '2026-07-08T08:05:43.040091+00:00'::timestamptz, '2026-07-08T09:43:30.297045+00:00'::timestamptz)
ON CONFLICT ("id") DO UPDATE SET "category" = EXCLUDED."category", "name" = EXCLUDED."name", "description" = EXCLUDED."description", "prompt_text" = EXCLUDED."prompt_text", "is_builtin" = EXCLUDED."is_builtin", "created_by" = EXCLUDED."created_by", "created_at" = EXCLUDED."created_at", "updated_at" = EXCLUDED."updated_at";
INSERT INTO "prompt_components" ("id", "category", "name", "description", "prompt_text", "is_builtin", "created_by", "created_at", "updated_at")
VALUES ('b7a2f8c1-1004-4000-8000-000000000004', 'scene_structure', '记忆唤醒·知识卡片三层结构', '残缺图解开场、逐步补全推导、升华收束的三段镜头序列，每镜固定三层卡片骨架', '【镜头结构：记忆唤醒·知识卡片三层结构 v2】

一、必须包含的镜头序列（最少 10 镜）

镜头 1——记忆钩子（必须）
顶部标题："[学科]｜还记得这个吗？"
主体区：残缺图解，核心元素 fill_opacity=0.15（幽灵态）
底层：显示"？"占位，不放结论
旁白：第二人称 + 具体课堂场景，制造悬念

镜头 2——部分揭晓（必须）
用 FadeIn 补全第一镜的幽灵态元素
主体区：完整基础图解
底层结论胶囊：知识点一句话定义
旁白："对——就是这里。[知识点名称]。"

镜头 3——建立模型/设定变量（必须有，不可省略）
顶部标题："我们来重新推一遍"
主体区：用 MathTex 显示初始条件或设定（如"令 x = 0.999…"）
底层结论胶囊：本步骤的出发点
旁白：解释为何这样设定

镜头 4 至 N-2——逐步推导（每步一镜，共 4-6 镜）
每个镜头严格处理一个推导步骤：
  顶部：步骤序号 + 本步标题（如"第一步：两边同乘 10"）
  主体区：
    - 公式推导用 MathTex + TransformMatchingTex 动态变换
    - 几何证明用 Create/GrowArrow 逐步构建图形
    - 函数关系用 Axes.plot() 描绘曲线
  底层结论胶囊：本步的中间结论
旁白："你想到了吗？下一步——"

镜头 N-1——关键结论揭示（必须）
顶部标题："所以答案是——"
主体区：用 MathTex 大号显示最终结论，font_size=42（此处可适当放大）
底层结论胶囊：结论的完整表述
旁白：揭晓结论，1-2 句，不超过 30 字

镜头 N——升华收束（必须）
顶部标题："其实你一直用着它"或同义句
主体区：清场只保留 1-2 个核心元素，大面积留白
底层结论胶囊：一句话现实延伸（≤20 字）
旁白：连接日常生活，1 句话克制收束

二、三层骨架（每镜固定）

┌──────────────────────────────┐  ← 顶层 y ∈ [6.0, 7.0]
│  [学科主色条带]   本镜标题    │     色条 height=1.0, 标题 font_size=32
├──────────────────────────────┤
│                              │
│      Manim 图解/公式区        │  ← 主体 y ∈ [-3.0, 5.5]
│   MathTex / Axes / Create   │
│                              │
├──────────────────────────────┤
│  💡 结论胶囊文字               │  ← 底层 y ∈ [-7.0, -5.0]
│  （明黄底 Rectangle + Text） │     胶囊 y=-6.0, height=1.8
└──────────────────────────────┘

三、Manim 元素使用要求（必须在推导镜头中体现）
- 数学公式：MathTex，至少 3 个镜头使用
- 公式变换：至少 1 处 TransformMatchingTex 展示推导过程
- 几何图形/坐标系/函数图像：至少 1 处（视选题而定）
- 箭头标注：Arrow 或 GrowArrow，指向关键元素

四、连续性规则
- 推导镜头间复用 Manim 对象，保持空间位置一致
- 坐标轴、分界线一旦建立即跨镜保留
- 清场仅发生在升华镜前（FadeOut 整体）

五、禁止
整页文字卡（无图解无公式）、把多步骤压缩进一镜、
结论比推导出现得更早、升华镜还在推导新知识。', true, NULL, '2026-07-08T08:05:43.040091+00:00'::timestamptz, '2026-07-08T09:43:30.297045+00:00'::timestamptz)
ON CONFLICT ("id") DO UPDATE SET "category" = EXCLUDED."category", "name" = EXCLUDED."name", "description" = EXCLUDED."description", "prompt_text" = EXCLUDED."prompt_text", "is_builtin" = EXCLUDED."is_builtin", "created_by" = EXCLUDED."created_by", "created_at" = EXCLUDED."created_at", "updated_at" = EXCLUDED."updated_at";
INSERT INTO "prompt_components" ("id", "category", "name", "description", "prompt_text", "is_builtin", "created_by", "created_at", "updated_at")
VALUES ('b7a2f8c1-1004-4000-8000-000000000005', 'animation_style', '记忆唤醒·Manim图解动效', '逐笔描线图解构建、FadeIn幽灵态补全、GrowFromCenter结论弹出、卡片FadeIn入场', '【动画系统：记忆唤醒·Manim 图解动效 v2】

总原则：动画服务于理解，不做装饰。Manim 的数学可视化能力是本风格
最大差异化优势，必须充分使用 MathTex、Axes、graph 等核心功能。

一、Manim 公式动画（核心，必须在推导镜头中使用）

基础公式显示：
    formula = MathTex(r"x = 0.999\ldots", font_size=36, color="#1E293B")
    self.play(Write(formula))

公式推导变换（TransformMatchingTex，关键）：
    step1 = MathTex(r"x", r"=", r"0.999\ldots", font_size=36)
    step2 = MathTex(r"10x", r"=", r"9.999\ldots", font_size=36)
    step3 = MathTex(r"9x", r"=", r"9", font_size=36)
    step4 = MathTex(r"x", r"=", r"1", font_size=36)
    self.play(TransformMatchingTex(step1, step2))
    self.wait(0.5)
    self.play(TransformMatchingTex(step2, step3))

公式分组（VGroup 对齐）：
    equations = VGroup(step1, step2).arrange(DOWN, buff=0.6)

二、Manim 函数图像（适用于数学/物理中的函数关系）

    axes = Axes(
        x_range=[-1, 5, 1],
        y_range=[-1, 3, 1],
        x_length=6,
        y_length=4,
        axis_config={"color": "#1E293B", "stroke_width": 2},
    ).move_to(ORIGIN)
    graph = axes.plot(lambda x: x**0.5, color="#2563EB", stroke_width=3)
    self.play(Create(axes))
    self.play(Create(graph), run_time=1.5)

三、几何图形构建

    # 逐笔描线
    circle = Circle(radius=1.5, color="#2563EB", stroke_width=3)
    self.play(Create(circle), run_time=0.8)

    # 箭头（受力图、指向）
    arrow = Arrow(start=LEFT*2, end=RIGHT*2, color="#EA580C", stroke_width=3)
    self.play(GrowArrow(arrow), run_time=0.5)

    # 虚线
    dashed = DashedLine(start=LEFT*3, end=RIGHT*3, color="#94A3B8",
                        stroke_width=1.5, dash_length=0.15)
    self.play(Create(dashed), run_time=0.6)

四、开场幽灵态补全

    # 第一镜：幽灵态元素
    ghost = MathTex(r"= 1", font_size=36)
    ghost.set_opacity(0.15)
    self.add(ghost)

    # 第二镜：FadeIn 补全
    self.play(ghost.animate.set_opacity(1), run_time=0.4)

五、卡片入场

    card_content = VGroup(formula, diagram)
    self.play(FadeIn(card_content, shift=UP*0.3), run_time=0.4)

六、结论胶囊出场

    capsule_bg = RoundedRectangle(
        width=8.0, height=1.6, corner_radius=0.2,
        fill_color="#FEF08A", fill_opacity=1, stroke_width=0
    ).move_to([0, -6.0, 0])
    capsule_text = Text("结论文字", font_size=28, color="#1E293B")
    capsule_text.move_to(capsule_bg.get_center())
    capsule = VGroup(capsule_bg, capsule_text)
    self.play(GrowFromCenter(capsule), run_time=0.4)
    self.wait(0.3)
    self.play(Flash(capsule_bg, color="#2563EB", flash_radius=0.3, run_time=0.3))

七、镜头切换

连续推导镜头（保留上一镜图形，增量构建）：
    # 不清场，直接在已有元素基础上 Create/Write 新元素
    self.play(Create(new_element), run_time=0.6)

幕间清场（升华镜前）：
    self.play(FadeOut(VGroup(*self.mobjects)), run_time=0.5)

八、beat 时间分配
- 动画完成后静置 0.3-0.5 秒再推进
- 关键公式/结论前安排 0.2 秒停顿
- 一个 beat 对应一次有意义的图解动画，不做无意义运动

九、禁忌
- 使用 Text 代替 MathTex 显示数学公式
- 字体大小超过 color_scheme 规定的上限
- 所有元素同帧出现（无动画直接 add）
- 屏幕外滑入、持续旋转、频繁闪白
- 每镜清场重绘（连续推导镜头内）', true, NULL, '2026-07-08T08:05:43.040091+00:00'::timestamptz, '2026-07-08T09:43:30.297045+00:00'::timestamptz)
ON CONFLICT ("id") DO UPDATE SET "category" = EXCLUDED."category", "name" = EXCLUDED."name", "description" = EXCLUDED."description", "prompt_text" = EXCLUDED."prompt_text", "is_builtin" = EXCLUDED."is_builtin", "created_by" = EXCLUDED."created_by", "created_at" = EXCLUDED."created_at", "updated_at" = EXCLUDED."updated_at";

-- Data: style_templates
INSERT INTO "style_templates" ("id", "name", "description", "style_config", "created_at", "updated_at")
VALUES ('11acd020-2817-4b90-97fb-27119957ecd5', '暖白极简科普', '反差、科普', '{"pacing": "b7a2f8c1-1002-4000-8000-000000000003", "color_scheme": "b7a2f8c1-1002-4000-8000-000000000001", "animation_style": "b7a2f8c1-1002-4000-8000-000000000005", "narrative_style": "b7a2f8c1-1002-4000-8000-000000000002", "scene_structure": "b7a2f8c1-1002-4000-8000-000000000004"}', '2026-07-05T10:11:02.262085+00:00'::timestamptz, '2026-07-05T10:11:02.262089+00:00'::timestamptz)
ON CONFLICT ("id") DO UPDATE SET "name" = EXCLUDED."name", "description" = EXCLUDED."description", "style_config" = EXCLUDED."style_config", "created_at" = EXCLUDED."created_at", "updated_at" = EXCLUDED."updated_at";
INSERT INTO "style_templates" ("id", "name", "description", "style_config", "created_at", "updated_at")
VALUES ('b7a2f8c1-1003-4000-8000-0000000000ff', '群像剧场（快节奏知识叙事）', '从高完播率概率知识短片抽象出的风格族 v2：暖白符号剧场视觉 + 张力驱动叙事（钩子/论证/升华按选题形态选取）+ 1.2倍速快节奏 + 五段张力骨架 + 状态流转动画词汇表。适配决策、现象、规律等各形态知识选题。', '{"pacing": "b7a2f8c1-1003-4000-8000-000000000003", "color_scheme": "b7a2f8c1-1003-4000-8000-000000000001", "animation_style": "b7a2f8c1-1003-4000-8000-000000000005", "narrative_style": "b7a2f8c1-1003-4000-8000-000000000002", "scene_structure": "b7a2f8c1-1003-4000-8000-000000000004"}', '2026-07-06T09:11:22.188565+00:00'::timestamptz, '2026-07-06T10:40:41.772950+00:00'::timestamptz)
ON CONFLICT ("id") DO UPDATE SET "name" = EXCLUDED."name", "description" = EXCLUDED."description", "style_config" = EXCLUDED."style_config", "created_at" = EXCLUDED."created_at", "updated_at" = EXCLUDED."updated_at";
INSERT INTO "style_templates" ("id", "name", "description", "style_config", "created_at", "updated_at")
VALUES ('b7a2f8c1-1004-4000-8000-0000000000ff', '记忆唤醒·理科卡片', '面向职场人复习初高中数理化的短视频风格族：白底明亮知识卡片视觉 + 记忆钩子三段式叙事 + 短视频竖屏节奏 + 知识卡片三层结构 + Manim 图解动效。竖屏 9:16，Manim 引擎，适合数学/物理/化学初高中知识复习类选题。', '{"pacing": "b7a2f8c1-1004-4000-8000-000000000003", "color_scheme": "b7a2f8c1-1004-4000-8000-000000000001", "animation_style": "b7a2f8c1-1004-4000-8000-000000000005", "narrative_style": "b7a2f8c1-1004-4000-8000-000000000002", "scene_structure": "b7a2f8c1-1004-4000-8000-000000000004"}', '2026-07-08T08:05:43.040091+00:00'::timestamptz, '2026-07-08T08:05:43.040091+00:00'::timestamptz)
ON CONFLICT ("id") DO UPDATE SET "name" = EXCLUDED."name", "description" = EXCLUDED."description", "style_config" = EXCLUDED."style_config", "created_at" = EXCLUDED."created_at", "updated_at" = EXCLUDED."updated_at";

COMMIT;
