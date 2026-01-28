import json
import random
import asyncio
from tqdm import tqdm
from typing import List, Dict, Tuple
from templates import *


def _json_dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False)


def pick_one(lst: List[str]) -> str:  # 随机从列表里抽取
    return random.choice(lst)


def pick_two(lst: List[str]) -> Tuple[str, str]:  # 保证a和b之间不相同
    a = random.choice(lst)
    b = random.choice(lst)
    while b == a:
        b = random.choice(lst)
    return a, b

def normalize_empty_memory(s: str) -> str:  # 标准化空输出
    """
    统一“空画像”的表示，避免模型学到字面量“空”。
    这里用空列表字符串：[]，更结构化。
    """
    s = (s or "").strip()
    if s in {"空", "无", "None", "null", "NULL", "nothing"}:
        return "[]"
    return s

# 这里数据集加载分为身份|工具调用|用户画像刻画
class DatasetGenerator:
    """多任务数据集生成器[decision|memory]，直接写入 JSONL 文件"""

    def __init__(
        self,
        output_file: str = "Dataset.jsonl",
        seed: int = 42,
        decision_positive_ratio: float = 0.6,  # 使用工具的比例
        planner_concurrency: int = 10,
        planner_retries: int = 3,
    ):
        self.output_file = output_file
        self.decision_positive_ratio = decision_positive_ratio
        self.planner_concurrency = planner_concurrency
        self.planner_retries = planner_retries

        random.seed(seed)

        # 清空输出文件
        with open(self.output_file, "w", encoding="utf-8"):  # w下存在会清空内容
            pass

        self._init_parameter_pools()

        # 并发写文件锁（Planner 并发用）
        self._write_lock = asyncio.Lock()
    # 写入数据到对应的字典

    def _write_sample_sync(self, sample: Dict):  # 不断写入
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
            "计算机视觉", "图像识别", "目标检测", "语义分割", "图像生成", "路线规划",
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
            "监督学习", "无监督学习", "半监督学习", "自监督学习", "微积分", "导数", "积分", "微分方程",
            "线性代数", "向量", "线性变换", "矩阵", "特征值", "特征向量", "概率论", "随机变量", "期望", "方差", "标准差", "协方差", "相关系数"
            "RAG", "检索增强生成", "向量检索", "混合检索", "重排序",
            "知识图谱", "实体识别", "关系抽取", "事件抽取", "实体链接",
            "LangGraph", "LangChain", "Agent", "多智能体", "工作流",
            "微服务", "服务网格", "API网关", "服务发现", "负载均衡",
            "分布式系统", "CAP定理", "BASE理论", "一致性", "可用性",
            "缓存策略", "缓存穿透", "缓存击穿", "缓存雪崩", "缓存预热",
        ]
        self.programming = [
            "终端", "执行本地shell终端命令", "执行代码", "调试代码", "打印字符串", "输出结果", "写入文件", "读取文件", "删除文件"
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
            "API.md", "ARCHITECTURE.md", "DESIGN.md", "DEVELOPER.md", "file.txt", "outline.txt"
        ]

        self.paths = [
            "当前目录", "src目录", "test目录", "docs目录", "项目根目录", "上级目录", "下级目录"
            "config目录", "logs目录", "data目录", "scripts目录",
            "/home/user", "/var/log", "/usr/local", "/opt", "/tmp",
            "C:\\Users", "D:\\Projects", "E:\\Workspace", "F:\\Downloads",
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
            "请你读取该文件的代码并具体给我解释一下？"
        ]

        # 隐式需要工具（难正例 hard positive）
        self.decision_hard_positive_templates: List[Tuple[str, str]] = [
            ("当前的项目路径是什么呢？", "file"),
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
            "具体说一下这段代码是什么意思呢? a=2;",
            "帮我解释一下这段代码是什么意思呢?"
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
        negative_pool = negative_templates + self.decision_no_tool_templates + \
            self.decision_hard_negative_templates

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
            scenario = random.choice(scenarios)  # $ 随机抽选一个问题
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
                province=province,
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
                province=province,
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
                province=province,
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

    def generate_identity_samples(self, num_samples: int = 40, model_name: str = "Pgo", origin_model_name="Qwen3-3B"):
        for _ in tqdm(range(num_samples), desc="生成身份样本"):
            question1 = random.choice(model_identity_templates)
            sample1 = {
                "instruction": "当用户询问模型身份时，直接回答模型身份和能力。",
                "input": question1,
                "output": f"我是{model_name}多任务模型，由{origin_model_name}微调而来，具备工具判断、用户画像刻画和任务规划能力。",
            }
            self._write_sample_sync(sample1)

            question2 = random.choice(author_question)
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
        custom_name: str = "Pgo",
        origin_model_model: str = "Qwen3-3B",
    ):
        print("=" * 20)
        print("开始生成多任务数据集!")
        print("=" * 20)

        print("\n[1/3] 生成用户测试数据集...")
        self.generate_identity_samples(
            test_samples, model_name=custom_name, origin_model_name=origin_model_model)

        print("\n[2/3] 生成 Decision 数据集...")
        self.generate_decision_samples(decision_samples)

        print("\n[3/3] 生成 Memory 数据集...")
        self.generate_memory_samples(memory_samples)

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
        output_file="Dataset.jsonl",
        seed=42,
        decision_positive_ratio=0.6,
        planner_concurrency=2,
        planner_retries=3,
    )

    await generator.generate_all(
        decision_samples=1500,
        memory_samples=2000,
        planner_samples=200,
    )

author = "Soul-xu-yang"

# 生成的是多任务的Alpaca格式数据
if __name__ == "__main__":
    asyncio.run(main())
