import json
import random
import asyncio
from tqdm import tqdm
from typing import List, Dict, Tuple, Optional, Literal


from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, Field

from agent.my_llm import llm


def _json_dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False)


def pick_one(lst: List[str]) -> str: # 随机从列表里抽取
    return random.choice(lst)


def pick_two(lst: List[str]) -> Tuple[str, str]: # 保证a和b之间不相同
    a = random.choice(lst)
    b = random.choice(lst)
    while b == a:
        b = random.choice(lst)
    return a, b
# 以下是对应的plan的结构    
class PlanStep(BaseModel):
    """
    单个步骤：
    - description：自然语言描述这一步要做什么
    - capability：这一步需要的大致能力类型（后续由 Agent 选择具体工具）
    """
    description: str = Field(
        ...,
        description="该步骤要做的事情，用自然语言简述。",
    )
    capability: Literal[
        "none",
        "search",
        "rag_retrieve",
        "rag_rewrite_query",
        "file_read",
        "file_write",
        "create_file",
        "delete_file",
        "list_dir",
        "get_time",
        "calculate",
        "code_exec",
        "web_search",
        "external_mcp",
        "ask_user",
    ] = Field(
        "none",
        description="该步骤需要的大致能力类型，后续大模型根据能力类别映射具体工具。",
    )
class Planner(BaseModel):
    """
    LLM 规划输出：
    - plan_steps：步骤列表，每个步骤包含 description + capability
    - requires_rag：整体任务是否需要 RAG
    """
    plan_steps: List[PlanStep] = Field(
        description="为当前用户请求规划出的执行步骤，从上到下按顺序执行。"
    )
    requires_rag: bool = Field(
        default=False,
        description="当前任务是否需要从知识库 / 向量库中检索信息（RAG）。",
    )

def normalize_empty_memory(s: str) -> str: # 标准化空输出
    """
    统一“空画像”的表示，避免模型学到字面量“空”。
    这里用空列表字符串：[]，更结构化。
    """
    s = (s or "").strip()
    if s in {"空", "无", "None", "null", "NULL","nothing"}:
        return "[]"
    return s


class DatasetGenerator:
    """多任务数据集生成器[decision|memory|plan]，直接写入 JSONL 文件"""

    def __init__(
        self,
        output_file: str = "Dataset.jsonl",
        seed: int = 42,
        decision_positive_ratio: float = 0.6, # 使用工具的比例
        planner_concurrency: int = 10,
        planner_retries: int = 3,
    ):
        self.output_file = output_file
        self.decision_positive_ratio = decision_positive_ratio
        self.planner_concurrency = planner_concurrency
        self.planner_retries = planner_retries

        random.seed(seed)

        # 清空输出文件
        with open(self.output_file, "w", encoding="utf-8") : # w下存在会清空内容
            pass

        self._init_parameter_pools()

        # 并发写文件锁（Planner 并发用）
        self._write_lock = asyncio.Lock()
    # 写入数据到对应的字典
    def _write_sample_sync(self, sample: Dict): # 不断写入
        with open(self.output_file, "a", encoding="utf-8") as f:
            f.write(_json_dumps(sample) + "\n")

    async def _write_sample_async(self, sample: Dict):
        async with self._write_lock:
            self._write_sample_sync(sample)

    # --------------------------
    # 参数池
    # --------------------------
    def _init_parameter_pools(self):
        # 1) 用户画像参数池
        self.professions = professions
        self.provinces = provinces
        self.cities = cities
        self.companies = companies
        self.sex = sex
        self.learning_goals = learning_goals
        self.preferences = preferences
        self.hobbies = hobbies
        self.work_styles = work_styles

        # 2) 知识库内容参数池
        self.knowledge_keywords = [
            "矩阵", "向量", "张量", "算法", "数据结构", "时间复杂度", "空间复杂度",
            "机器学习", "深度学习", "神经网络", "CNN", "RNN", "LSTM", "Transformer",
            "NLP", "自然语言处理", "词向量", "Embedding", "BERT", "GPT", "LLM",
            "计算机视觉", "图像识别", "目标检测", "语义分割", "图像生成",
            "Python", "Java", "JavaScript", "TypeScript", "Go", "Rust", "C++",
            "TensorFlow", "PyTorch", "Keras", "Scikit-learn", "Pandas", "NumPy",
            "React", "Vue", "Angular", "Node.js", "Express", "Django", "Flask",
            "Spring", "Spring Boot", "MyBatis", "Hibernate", "JPA",
            "MySQL", "PostgreSQL", "MongoDB", "Redis", "Elasticsearch", "InfluxDB",
            "Docker", "Kubernetes", "K8s", "Helm", "Istio", "Service Mesh",
            "RabbitMQ", "Kafka", "RocketMQ", "Pulsar", "NATS",
            "Nginx", "Apache", "HAProxy", "Traefik", "Envoy",
            "AWS", "Azure", "GCP", "阿里云", "腾讯云", "华为云", "AWS S3", "EC2",
            "Lambda", "ECS", "EKS", "RDS", "DynamoDB", "SQS", "SNS",
            "Git", "GitHub", "GitLab", "Jenkins", "GitLab CI", "GitHub Actions",
            "Jira", "Confluence", "Notion", "Figma", "Postman", "Swagger",
            "RAG", "检索增强生成", "向量检索", "混合检索", "重排序", "知识蒸馏",
            "LangGraph", "LangChain", "Agent", "多智能体", "工作流",
            "知识图谱", "实体识别", "关系抽取", "事件抽取", "文本分类",
            "情感分析", "主题建模", "文档摘要", "信息检索", "问答系统",
            "科学", "数学", "物理", "化学", "生物", "医学", "心理学", "社会学", "经济学", "政治学",
            "历史", "地理"
        ]

        self.knowledge_topics = [
            "Python编程", "Java开发", "前端开发", "后端开发", "全栈开发",
            "机器学习", "深度学习", "人工智能", "数据科学", "大数据",
            "系统架构", "微服务", "云原生", "DevOps", "SRE",
            "数据库", "缓存", "消息队列", "分布式系统", "高并发",
            "网络安全", "数据安全", "隐私保护", "加密算法",
            "电商系统", "支付系统", "推荐系统", "搜索系统", "广告系统",
            "内容管理", "用户管理", "权限管理", "日志系统", "监控系统",
            "动画角色", "卫星通信", "RAG系统", "Agent系统", "知识图谱",
            "信号处理", "图像处理", "视频处理", "音频处理",
        ]

        self.knowledge_concepts = [
            "机器学习", "深度学习", "神经网络", "强化学习", "迁移学习",
            "监督学习", "无监督学习", "半监督学习", "自监督学习",
            "RAG", "检索增强生成", "向量检索", "混合检索", "重排序",
            "知识图谱", "实体识别", "关系抽取", "事件抽取", "实体链接",
            "LangGraph", "LangChain", "Agent", "多智能体", "工作流",
            "微服务", "服务网格", "API网关", "服务发现", "负载均衡",
            "分布式系统", "CAP定理", "BASE理论", "一致性", "可用性",
            "缓存策略", "缓存穿透", "缓存击穿", "缓存雪崩", "缓存预热"
        ]
        self.programming = [
         "终端","执行代码","调试代码","打印字符串","输出结果","写入文件"
        ]
        # 3) 文件相关参数池
        self.files = [
            "README.md", "config.py", "config.toml", "config.yaml", "config.json",
            "settings.py", ".env", ".gitignore", ".dockerignore", "main.go", "main.java", "main.c",
            "main.py", "app.py", "index.py", "server.py", "client.py",
            "graph.py", "agent.py", "utils.py", "base_utils.py",
            "requirements.txt", "package.json", "pom.xml", "build.gradle",
            "Dockerfile", "docker-compose.yml", "docker-compose.yaml",
            "Dockerfile.dev", "Dockerfile.prod", "k8s.yaml", "helm-chart",
            "index.html", "app.js", "main.js", "App.jsx", "App.tsx",
            "index.js", "index.ts", "styles.css", "main.css",
            "test.py", "test.js", "test.ts", "test_agent.py", "test_rag.py",
            "pytest.ini", "jest.config.js", "vitest.config.ts",
            "CHANGELOG.md", "LICENSE", "CONTRIBUTING.md", "docs/",
            "API.md", "ARCHITECTURE.md", "DESIGN.md"
        ]

        self.paths = [
            "当前目录", "src目录", "test目录", "docs目录", "项目根目录",
            "config目录", "logs目录", "data目录", "scripts目录",
            "/home/user", "/var/log", "/usr/local", "/opt", "/tmp",
            "C:\\Users", "D:\\Projects", "E:\\Workspace"
        ]

        self._init_task_templates()

    # --------------------------
    # 任务模板：Planner - 根据用户所说返回对应的标签
    # --------------------------
    def _init_task_templates(self):
        """
        Decision 训练：建议用 route 多分类。
        route 取值：none | time | web_search | file | rag | db | mcp | multi
        """
        # 显式需要工具（易）
        self.decision_tool_templates: List[str] = [
            # RAG/知识库
            "查询知识库中关于{keyword}的信息",
            "检索知识库中{keyword}的内容",
            "从知识库中查找{keyword}相关资料",

            # 文件
            "读取{file}文件",
            "读取{file}并总结",
            "帮我查看{file}的内容",
            "分析{file}文件的结构",
            "检查{file}文件是否存在",
            "列出{path}目录的文件",
            "列出当前目录下的所有文件",
            "遍历{path}目录",

            # 时间
            "现在几点了？",
            "今天是几号？",
            "当前日期是什么？",
            "现在是星期几？",
            "查询系统时间",
            "未来的时间是多少?",
            "预估到达的时间是几点?",
            "预估多久?",

            # Web 搜索
            "在互联网上搜索{query}",
            "帮我搜索{keyword}相关内容",
            "查找关于{topic}的资料（要带来源）",
            "网上查找",

            # MCP
            "使用MCP工具查询{query}",
            "通过MCP工具搜索{query}",
            "用MCP工具执行",
            "用MCP获取信息",

            # DB（如果你确实有此能力）
            "查询数据库中的{table}表",
            "检查数据库连接",
            "从数据库中查询由哪些表格",
            "删除数据库中的数据",
            "更新数据库中的数据",
            "插入数据到数据库中",
            "创建数据库表",

            # 组合（多工具/复杂任务）
            "查询知识库中{keyword}的信息，然后总结",
            "读取{file}文件，分析其中的{topic}内容",
            "列出目录文件，然后读取{file}",
            "搜索{topic}，然后保存到{file}",
        ]

        # 隐式需要工具（难正例 hard positive）
        self.decision_hard_positive_templates: List[Tuple[str, str]] = [
            ("当前的项目路径是什么呢？","file"),
            ("{file}里主要讲了什么？", "file"),
            ("项目根目录有哪些文件？", "file"),
            ("把{path}下面的文件结构列出来", "file"),
            ("你帮我看看{file}有没有提到{keyword}", "file"),
            ("我这台机器现在的时间是多少？", "time"),
            ("给我{keyword}的最新资料，要有出处", "web"),
            ("你能从知识库里把{topic}的要点整理一下吗？", "rag"),
        ]

        # 不需要工具（易负例）
        self.decision_no_tool_templates = [
            "你好，{greeting}",
            "最近怎么样？",
            "在忙什么？",
            "今天心情如何？",
            "请介绍一下{topic}",
            "解释一下{concept}的概念",
            "什么是{topic}？",
            "{concept}是什么意思？",
            "帮我理解{topic}",
            "用简单的话解释{concept}",
            "帮我写一首{type}诗",
            "给我讲个{type}笑话",
            "写一段关于{topic}的文字",
            "创作一个{type}故事",
            "帮我翻译{text}",
            "把{text}翻译成英文",
            "将{text}翻译成中文",
            "总结一下{topic}的要点",
            "概括{concept}的主要内容",
            "简要说明{topic}",
            "你是什么模型呢?",
            "你最近忙了些什么呢?",
            "具体说一下这段代码是什么意思呢? a=2;"
        ]

        # 难负例 hard negative（出现文件/时间/知识词，但本质是解释/泛化）
        self.decision_hard_negative_templates = [
            "假设我有一个文件叫{file}，一般会包含哪些内容？（不用读文件）",
            "如果我要读取{file}，通常有哪些实现方式？",
            "解释一下为什么大家都用{concept}",
            "用通俗的话讲讲{topic}的核心思想（不需要查资料）",
            "讨论一下{keyword}可能有哪些应用场景",
            "请你不用工具搜索，帮我解释下{concept}是什么呢?"
        ]

        # Planner 模板：保持你原有方向，但更偏真实表达（含隐式与约束）
        self.planner_templates = [
            # RAG / 文件 / 组合
            "查询知识库中关于{keyword}的信息，然后总结成要点",
            "在知识库中对比{keyword1}和{keyword2}的差异",
            "读取{file}并总结，重点关注{topic}",
            "读取{file1}和{file2}，对比分析差异并给出结论",
            "列出{path}目录的文件结构，并指出最可能是入口文件的是哪个",
            "先搜索{topic}的资料（要有来源），再整理成学习计划",
            # 隐式
            "{file}里有没有提到{keyword}？有的话帮我摘出关键段落并总结",
            "我想快速了解{topic}，请给一个可执行的学习路径",
            # 简单问答
            "解释一下{concept}的概念，并给一个例子",
        ]

    # --------------------------
    # Decision 数据集生成
    # --------------------------
    def generate_decision_samples(self, num_samples: int = 1000):
        """
        判断的数据集生成
        { "requires_agent": true/false }
        """
        # 汇总正负样本模板，覆盖显式/隐式工具需求和纯对话场景
        positive_pool = (
                positive_templates
                + list(self.decision_tool_templates)
                + [tpl for tpl, _ in self.decision_hard_positive_templates]
        )
        negative_pool = negative_templates + self.decision_no_tool_templates + self.decision_hard_negative_templates

        positive_count = int(num_samples * self.decision_positive_ratio)
        negative_count = num_samples - positive_count

        for _ in tqdm(range(positive_count)):
            template = random.choice(positive_pool)
            question = template.format(
            keyword=pick_one(self.knowledge_keywords),
            file=pick_one(self.files),
            topic=pick_one(self.knowledge_topics),
            path=pick_one(self.paths),
            table=pick_one(["users", "orders", "logs", "products"]),
            concept=pick_one(self.knowledge_concepts),
            greeting=pick_one(greetings),
            programming=pick_one(self.programming),
            query=pick_one(self.knowledge_keywords),  
          )
            sample = {
                "task_type": "decision",
                "instruction": "判断用户问题是否需要调用外部工具(LLM本身不具备的工具)，并输出requires_agent=True或False",
                "input": question,
                "output": _json_dumps({"requires_agent": True}),
            }
            self._write_sample_sync(sample)

        for _ in tqdm(range(negative_count)):
            template = random.choice(negative_pool)
            question = template.format(
            greeting=pick_one(greetings),
            topic=pick_one(self.knowledge_topics),
            type=pick_one(types),
            text=pick_one(texts),
            concept=pick_one(self.knowledge_concepts),
            keyword=pick_one(self.knowledge_keywords),
            file=pick_one(self.files),          
            path=pick_one(self.paths),           
            )
            sample = {
                "task_type": "decision",
                "instruction": "判断用户问题是否需要调用外部工具(LLM本身不具备的工具)，并输出requires_agent=True或False",
                "input": question,
                "output": _json_dumps({"requires_agent": False}),
            }
            self._write_sample_sync(sample)

        print(f"✅ 当前已生成 {num_samples} 条 Decision 数据[仅 requires_agent 布尔判定]")

    # --------------------------
    # Memory 数据集生成
    # --------------------------
    def generate_memory_samples(self, num_samples: int = 1500):
        """
        Memory 输出格式：项目符号列表，空为 []
        强化覆盖：
        - 新增/补充
        - 更新
        - 无新信息
        - 不要记
        - 删除字段
        - 不确定信息（不更新）
        - 他人信息（不写入画像）
        """
        for _ in tqdm(range(num_samples)):
            scenario = random.choice(scenarios) #$ 随机抽选一个问题
            # 针对问题，填充变量
            profession = pick_one(self.professions)
            sex = pick_one(self.sex)
            city = pick_one(self.cities)
            company = pick_one(self.companies)
            goal = pick_one(self.learning_goals)
            preference = pick_one(self.preferences)
            hobby = pick_one(self.hobbies)
            work_style = pick_one(self.work_styles)
            province = pick_one(self.provinces)
            # 填充下面的三句话的内容
            existing_memory = scenario["existing_memory"].format(
                profession=profession,
                city=city,
                company=company,
                goal=goal,
                preference=preference,
                hobby=hobby,
                sex=sex,
                work_style=work_style,
                province = province,
            )
            existing_memory = normalize_empty_memory(existing_memory)

            conversation = scenario["conversation_template"].format(
                profession=profession,
                city=city,
                company=company,
                goal=goal,
                preference=preference,
                sex=sex,
                hobby=hobby,
                work_style=work_style,
                province = province,
            )

            output = scenario["output_template"].format(
                profession=profession,
                city=city,
                company=company,
                goal=goal,
                sex=sex,
                preference=preference,
                hobby=hobby,
                work_style=work_style,
                province = province,
            )
            output = normalize_empty_memory(output)

            sample = {
                "task_type": "memory",
                "instruction": "从对话中提取用户画像信息；只记录用户客观事实；可删除字段；空画像输出[]；使用项目符号列表",
                "input": f"当前已保存的用户信息：\n{existing_memory}\n\n最新聊天记录：\n{conversation}",
                "output": output,
            }
            self._write_sample_sync(sample)

        print(f"✅ 当前已生成 {num_samples} 条 关于用户画像的Memory 数据")

    # --------------------------
    # Planner 数据集生成（调用真实系统）
    # --------------------------
    @staticmethod
    def _planner_system_prompt( allowed_capabilities: List[str]) -> str:
        """
        强制 capability 白名单，避免模型发明工具名。
        注意:allowed_capabilities 必须与你系统 Planner/PlanStep 的 capability 期望值一致。
        """
        caps = "\n".join([f"- {c}" for c in allowed_capabilities])
        return (
            "你是任务规划助手，需要将用户需求拆解为清晰、原子化的步骤。\n"
            "输出结构：仅输出 plan_steps（不做额外解释），每步包含 description 与 capability。\n"
            "能力白名单（只能从下列取值，不得发明）：\n"
            f"{caps}\n"
            "规则：\n"
            "1) 步骤要原子化、先后清晰，例如：列目录 -> 读文件 -> 整理 -> 回答。\n"
            "2) 只写 capability，不出现具体工具名或实现细节。\n"
            "3) RAG 检索直接用 capability=rag_retrieve；若检索失败，先用 capability=rag_rewrite_query 重写 query，再重试 rag_retrieve。\n"
            "4) 信息不足时，首步应使用 capability=ask_user 进行澄清。\n"
            "5) 仅依据用户最新消息规划，不臆测外部环境。\n"
        )

    async def generate_planner_samples(
        self,
        num_samples: int = 20,
        allowed_capabilities: Optional[List[str]] = None,
    ):
        """
        输出 schema：
        {
          "plan_steps":[{"description":..., "capability":...}, ...],
          "requires_rag": true/false
        }
        """
        if allowed_capabilities is None: 
            # 默认为我系统真实支持的 capability 枚举
            allowed_capabilities = [
                "none",
                "list_dir",
                "web_search",
                "rag_retrieve",
                "rag_rewrite_query",
                "file_read",
                "file_write",
                "create_file",
                "delete_file",
                "get_time",
                "calculate",
                "code_exec",
                "external_mcp",
                "ask_user",
            ]

        sem = asyncio.Semaphore(self.planner_concurrency) #llm的并行信号量

        planner_llm = llm.with_structured_output(Planner, include_raw=True) # 使用对应的结构进行输出
        system_prompt = self._planner_system_prompt(allowed_capabilities) # 构建对应的提示词

        async def plan_one(idx: int):
            template = random.choice(self.planner_templates)
            file1, file2 = pick_two(self.files) # 保证二者不相同
            kw1, kw2 = pick_two(self.knowledge_keywords)

            question = template.format(
                keyword=pick_one(self.knowledge_keywords),
                keyword1=kw1,
                keyword2=kw2,
                file=pick_one(self.files),
                file1=file1,
                file2=file2,
                path=pick_one(self.paths),
                topic=pick_one(self.knowledge_topics),
                concept=pick_one(self.knowledge_concepts),
            )

            async with sem: # 异步收到信号量的限制
                last_err = None
                for attempt in range(self.planner_retries): # 最多重试次数
                    try:
                        resp = await planner_llm.ainvoke([ # invoke的计划
                            SystemMessage(content=system_prompt),
                            HumanMessage(content=question),
                        ])
                        planner = resp["parsed"] # 必须用解析后的数据来作为数据集

                        # 结构化输出（并做轻量防御：capability 不在白名单则替换为 ask_user）-安全检测
                        steps = []
                        for s in planner.plan_steps:
                            cap = getattr(s, "capability", None)
                            desc = getattr(s, "description", "").strip()
                            if cap not in allowed_capabilities:
                                cap = "ask_user"
                                if not desc:
                                    desc = "请澄清任务目标与可用数据源/文件位置。"
                            steps.append(
                                {"description": desc, "capability": cap})
                        # 最后的输出
                        output = {
                            "plan_steps": steps,
                            "requires_rag": bool(getattr(planner, "requires_rag", False)),
                        }

                        sample = {
                            "task_type": "planner",
                            "instruction": "将用户任务分解为执行步骤，每个步骤包含description和capability；capability必须来自白名单",
                            "input": question,
                            "output": _json_dumps(output),
                        }

                        await self._write_sample_async(sample)
                        return True

                    except Exception as e:
                        last_err = e
                        # 指数退避
                        await asyncio.sleep(0.5 * (2 ** attempt))

                # 多次失败则丢弃该样本
                print(f"  ⚠️ Planner生成失败 idx={idx}, err={last_err}")
                return False

        tasks = [asyncio.create_task(plan_one(i)) for i in range(num_samples)]
        ok = 0
        from tqdm.asyncio import tqdm as tqdm_async
        for fut in  tqdm_async(asyncio.as_completed(tasks),desc = "生成进度"): # 迭代器，按照结果立刻更新
            res = await fut
            if res: # 
                ok += 1

        print(f"✅ 目前已生成 {ok}/{num_samples} 条 Planner 数据（含白名单/并发/重试）")

    def generate_identity_samples(self,num_samples:int =40,model_name:str = "Pgo",origin_model_name = "Qwen3-3B"):
      for _ in tqdm(range(num_samples), desc="生成身份样本"):
         question1 = random.choice(model_identity_templates)
         sample1 = {
            "instruction": "当用户询问模型身份时，直接回答模型身份和能力。",
            "input": question1,
            "output": f"我是{model_name}多任务模型，由{origin_model_name}微调而来，具备工具判断、用户画像刻画和任务规划能力。",
         }
         self._write_sample_sync(sample1)

         question2 = random.choice(author_quesiton)
         sample2 = {
            "instruction": "当用户询问你是由谁微调、训练或者创建的时候",
            "input": question2,
            "output": author,
         }
         self._write_sample_sync(sample2)
      print(f"✅ 目前模型身份数据已经生成，共{num_samples * 2}条")

    # --------------------------
    # 统一入口
    # --------------------------
    async def generate_all(
        self,
        decision_samples: int = 1000,
        memory_samples: int = 1500,
        planner_samples: int = 40,
        test_samples: int = 40,
        allowed_capabilities: Optional[List[str]] = None,
        custom_name:str ="Pgo",
        origin_model_model:str = "Qwen3-3B",
    ):
        print("=" * 20)
        print("开始生成多任务数据集!")
        print("=" * 20)
        
        print("\n[1/4] 生成 Decision 数据集...")
        self.generate_identity_samples(test_samples,model_name=custom_name,origin_model_name=origin_model_model)

        print("\n[2/4] 生成 Decision 数据集...")
        self.generate_decision_samples(decision_samples)

        print("\n[3/4] 生成 Memory 数据集...")
        self.generate_memory_samples(memory_samples)

        print("\n[4/4] 生成 Planner 数据集（调用真实系统）...")
        await self.generate_planner_samples(planner_samples, allowed_capabilities=allowed_capabilities)

        total = decision_samples + memory_samples + planner_samples
        print("\n" + "=" * 60)
        print("*** 本Pgo项目的数据集生成完成！***")
        print(f"   总数据量: {total} 条")
        print(f"   - Decision: {decision_samples} 条")
        print(f"   - Memory: {memory_samples} 条")
        print(f"   - Planner: {planner_samples} 条")
        print(f"   文件位置: {self.output_file}")
        print("=" * 60)


async def main():
    generator = DatasetGenerator(
        output_file="../3_tasks/Dataset.jsonl",
        seed=42,
        decision_positive_ratio=0.6,
        planner_concurrency=8,
        planner_retries=3,
    )

    # 如果你系统 capability 枚举与默认不同，请在这里传入
    allowed_capabilities = [
        "none",
        "list_dir",
        "search",
        "rag_retrieve",
        "rag_rewrite_query",
        "file_read",
        "file_write",
        "create_file",
        "delete_file",
        "get_time",
        "calculate",
        "code_exec",
        "external_mcp",
        "ask_user",
    ]

    await generator.generate_all(
        decision_samples=1500,
        memory_samples=2000,
        planner_samples=20,
        allowed_capabilities=allowed_capabilities,
    )
# ===常量===
scenarios = [
            # 首次建立画像
            {
                "existing_memory": "[]",
                "conversation_template": "HumanMessage: 你好，我是{profession}，目前在{province}-{city}工作。\nAIMessage: 很高兴认识你！",
                "output_template": "- 职业：{profession}\n- 地区：{province}-{city}",
            },
            # 构建性别
            {
                "existing_memory": "[]",
                "conversation_template": "HumanMessage: 你好，我是一名{profession}，性别{sex}\nAIMessage: 很高兴认识你！",
                "output_template": "- 职业：{profession}\n- 性别：{sex}",
            },
            #  补充公司信息
            {
                "existing_memory": "- 职业：{profession}",
                "conversation_template": "HumanMessage: 我在{company}工作。\nAIMessage: 了解了。",
                "output_template": "- 职业：{profession}\n- 公司：{company}",
            },
            #  补充学习目标
            {
                "existing_memory": "- 职业：{profession}\n- 地区：{province}-{city}",
                "conversation_template": "HumanMessage: 我准备考{goal}。\nAIMessage: 很好。",
                "output_template": "- 职业：{profession}\n- 地区：{province}-{city}\n- 学习目标：考{goal}",
            },
            #  补充偏好
            {
                "existing_memory": "- 职业：{profession}\n- 地区：{province}-{city}",
                "conversation_template": "HumanMessage: 我平时喜欢{preference}。\nAIMessage: 明白了。",
                "output_template": "- 职业：{profession}\n- 地区：{province}-{city}\n- 偏好：{preference}",
            },
            #  补充爱好
            {
                "existing_memory": "- 职业：{profession}",
                "conversation_template": "HumanMessage: 我的爱好是{hobby}。\nAIMessage: 很有趣。",
                "output_template": "- 职业：{profession}\n- 爱好：{hobby}",
            },
            #  补充工作风格
            {
                "existing_memory": "- 职业：{profession}",
                "conversation_template": "HumanMessage: 我习惯{work_style}。\nAIMessage: 好的。",
                "output_template": "- 职业：{profession}\n- 工作风格：{work_style}",
            },
            #  更新信息（变更）
            {
                "existing_memory": "- 职业：前端工程师\n- 地区：上海",
                "conversation_template": "HumanMessage: 我最近换工作了，现在是{profession}，搬到了{city}。\nAIMessage: 恭喜你！",
                "output_template": "- 职业：{profession}\n- 地区：{city}",
            },
            #  无新信息
            {
                "existing_memory": "- 职业：{profession}\n- 地区：{province}-{city}",
                "conversation_template": "HumanMessage: 你好！\nAIMessage: 你好，有什么可以帮助你的吗？",
                "output_template": "- 职业：{profession}\n- 地区：{province}-{city}",
            },
            #  多信息补充
            {
                "existing_memory": "[]",
                "conversation_template": "HumanMessage: 你好，我是{profession}，在{city}的{company}工作，最近在学习{goal}。\nAIMessage: 很高兴认识你！",
                "output_template": "- 职业：{profession}\n- 地区：{city}\n- 公司：{company}\n- 学习目标：学习{goal}",
            },

            #  不要记（保持不变）
            {
                "existing_memory": "- 职业：{profession}\n- 公司：{company}",
                "conversation_template": "HumanMessage: 公司信息不要记。\nAIMessage: 好的。",
                # 简化：若你要强执行“不记”，应当把公司移除；见下一条
                "output_template": "- 职业：{profession}\n- 公司：{company}",
            },
            #  明确删除字段（删公司）
            {
                "existing_memory": "- 职业：{profession}\n- 公司：{company}\n- 地区：{city}\n- 爱好：{hobby}",
                "conversation_template": "HumanMessage: 把我公司信息和我喜欢{hobby}删掉。\nAIMessage: 好的。",
                "output_template": "- 职业：{profession}\n- 地区：{city}",
            },
            #  明确删除字段（删地区）
            {
                "existing_memory": "- 职业：{profession}\n- 地区：{city}",
                "conversation_template": "HumanMessage: 地区信息别保存了。\nAIMessage: 明白。",
                "output_template": "- 职业：{profession}",
            },
            #   不确定信息（不更新）
            {
                "existing_memory": "- 地区：上海\n- 职业：{profession}\n- 性别：{sex}",
                "conversation_template": "HumanMessage: 我可能下个月去{city}，还不确定。\nAIMessage: 了解。",
                "output_template": "- 地区：上海\n- 职业：{profession}\n- 性别：{sex}",
            },
            #   他人信息（不写入画像）
            {
                "existing_memory": "[]",
                "conversation_template": "HumanMessage: 我朋友是医生，在北京。\nAIMessage: 了解。",
                "output_template": "[]",
            },
            #   短期状态
            {
                "existing_memory": "- 职业：{profession}\n- 地区：{city}",
                "conversation_template": "HumanMessage: 我今天在高铁上，信号不太好。\nAIMessage: 好的。",
                "output_template": "- 职业：{profession}\n- 地区：{city}",
            },
            #  短期状态
            {
                "existing_memory": "- 职业：{profession}\n- 地区：{province}-{city}",
                "conversation_template": "HumanMessage: 我朋友是嵌入式工程师，我想去他家里拜访，请给我规划一个从A到B的路线。\nAIMessage: 好的。",
                "output_template": "- 职业：{profession}\n- 地区：{province}-{city}",
            }, 
        ]
professions = [
            "电气工程师", "电子工程师", "通信工程师", "物联网工程师", "力学工程师", "桥梁与结构工程师", "建筑工程师", "汽车工程师",
            "前端工程师", "后端工程师", "全栈工程师", "数据科学家", "算法工程师", "硬件工程师", "嵌入式工程师",
            "机器学习工程师", "深度学习工程师", "AI工程师", "NLP工程师", "CV工程师", "图像处理工程师",
            "测试工程师", "QA工程师", "运维工程师", "DevOps工程师", "SRE工程师",
            "架构师", "技术总监", "CTO", "系统架构师", "云架构师",
            "移动开发工程师", "iOS开发", "Android开发", "小程序开发", "游戏开发",
            "区块链工程师", "安全工程师", "网络安全工程师", "渗透测试工程师",
            "产品经理", "项目经理", "UI设计师", "UX设计师", "交互设计师",
            "运营", "市场", "销售", "商务", "BD",
            "学生", "小学生", "初中生", "高中生", "大学", "研究生", "博士生", "教师", "教授", "讲师", "助教",
            "医生", "律师", "会计师", "咨询师", "分析师",
            "作家", "编辑", "记者", "翻译", "自由职业者"
        ]
provinces = [
            "陕西", "甘肃", "青海", "宁夏", "新疆", "西藏", "内蒙古", "广西", "云南", "贵州", "四川", "湖南", "湖北",
            "河南", "江西", "福建", "广东", "海南", "台湾", "山东", "山西", "河北", "天津", "北京", "上海", "江苏",
            "浙江", "安徽", "重庆", "辽宁", "吉林", "黑龙江", "香港", "澳门", "南海", "南海诸岛"
        ]
cities = [
            "上海", "北京", "深圳", "广州",
            "杭州", "成都", "南京", "武汉", "西安", "重庆", "苏州", "天津",
            "长沙", "郑州", "青岛", "东莞", "佛山", "宁波", "无锡", "合肥",
            "大连", "厦门", "福州", "济南", "石家庄", "哈尔滨", "长春", "沈阳",
            "昆明", "南宁", "贵阳", "南昌", "太原", "兰州", "乌鲁木齐", "银川", "西宁", "海口", "香港", "澳门", "台北","台中","台南","高雄"
        ]
companies =[
            "腾讯", "阿里巴巴", "百度", "字节跳动", "美团", "京东", "滴滴", "知乎",
            "华为", "小米", "OPPO", "vivo", "网易", "新浪", "搜狐",
            "富士康", "比亚迪", "长江存储", "宁德时代",
            "拼多多", "快手", "B站", "小红书", "豆瓣", "Nvidia",
            "微软", "Google", "Apple", "Amazon", "Meta", "Netflix",
            "IBM", "Oracle", "SAP", "Salesforce", "Adobe"
        ]
sex = ["男","女"]
learning_goals = [
            "PMP证书", "CPA证书", "CFA证书", "FRM证书", "CISA证书",
            "CISSP证书", "AWS认证", "Azure认证", "GCP认证", "Kubernetes认证",
            "Docker认证", "Red Hat认证", "Oracle认证", "Cisco认证",
            "Python编程", "Java编程", "Go编程", "Rust编程", "C++编程",
            "机器学习", "深度学习", "强化学习", "NLP", "计算机视觉",
            "前端开发", "后端开发", "全栈开发", "移动开发", "小程序开发",
            "系统架构", "微服务架构", "云原生", "DevOps", "SRE",
            "数据库设计", "大数据", "数据挖掘", "数据分析", "商业智能",
            "Docker", "Kubernetes", "CI/CD", "监控运维", "性能优化",
            "区块链", "Web3", "智能合约", "DeFi", "NFT",
            "网络安全", "渗透测试", "安全审计", "漏洞挖掘",
            "备考","考研","公务员考试","考公","高考","中考","小升初考试",
            "期末考试","期中考试","四级考试","六级考试"
        ]
preferences = [
            "中文交流", "英文交流", "简洁回答", "详细解释", "代码示例",
            "图文并茂", "循序渐进", "快速响应", "深入分析", "实战案例",
            "理论讲解", "视频教程", "文档阅读", "动手实践", "项目实战","举例说明"
        ]

hobbies = [
            "编程", "阅读", "写作", "摄影", "旅行", "运动", "音乐", "电影",
            "游戏", "绘画", "烹饪", "健身", "跑步", "游泳", "爬山", "骑行",
            "交朋友","听歌"
        ]

work_styles = [
            "早睡早起", "夜猫子", "高效工作", "慢工出细活", "团队协作",
            "独立工作", "远程办公", "办公室办公", "混合办公"
        ]
# === decision部分 ===
# 触发工具的关键词模板（正例）
positive_templates = [
            "现在几点了？",
            "今天是几号？",
            "查询系统时间",
            "在互联网上搜索{keyword}",
            "帮我搜索{keyword}相关内容",
            "查找关于{topic}的资料",
            "查询知识库中关于{keyword}的信息",
            "检索知识库中{keyword}的内容",
            "读取{file}文件",
            "读取{file}并总结",
            "帮我查看{file}的内容",
            "列出{path}目录的文件",
            "查询数据库中的{table}表",
            "使用MCP工具查询{keyword}",
            "给我{keyword}的最新资料，要有出处",
            "请你帮我查看终端",
            "请你帮我{programming}"
        ]

# 不触发工具的模板（负例）
negative_templates = [
            "你好，{greeting}",
            "最近怎么样？",
            "在忙什么？",
            "请介绍一下{topic}",
            "解释一下{concept}的概念",
            "什么是{topic}？",
            "帮我写一首{type}诗",
            "给我讲个{type}笑话",
            "总结一下{topic}的要点",
            "用简单的话解释{concept}",
        ] 
greetings = ["今天怎么样？", "最近怎么样？", "在忙什么？", "今天心情如何？","hello","hi"]
types = ["搞笑", "幽默", "有趣", "励志", "浪漫", "科幻", "悬疑"]
texts = ["Hello World", "你好世界", "Bonjour", "こんにちは", "Guten Tag"]

# 最后的身份识别模板
model_identity_templates = [
    "你是什么模型？",
    "你是哪个模型？",
    "what model are you?",
    "which base model?",
    "你是qwen3-3b finetune吗?",
    "你是用来干什么的呢？",
    "你的模型身份是什么？",
    "你具有哪些功能，可以做些什么呢？",
]
author_quesiton = [
   "你是有谁训练的呢？",
   "是谁微调的你呢？",
   "who create you?",
   "which one create you?",
   "你是由谁fine-tine的?",
   "你的微调作者是谁？",
   "who is your author",
   "是谁赋予了你这些功能？"
]
author = "Soul-xu-yang"

# 生成的是多任务的Alpaca格式数据
if __name__ == "__main__":
    asyncio.run(main())
