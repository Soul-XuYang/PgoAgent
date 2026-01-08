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
    "昆明", "南宁", "贵阳", "南昌", "太原", "兰州", "乌鲁木齐", "银川", "西宁", "海口", "香港", "澳门", "台北", "台中", "台南", "高雄"
]
companies = [
    "腾讯", "阿里巴巴", "百度", "字节跳动", "美团", "京东", "滴滴", "知乎",
    "华为", "小米", "OPPO", "vivo", "网易", "新浪", "搜狐",
    "富士康", "比亚迪", "长江存储", "宁德时代",
    "拼多多", "快手", "B站", "小红书", "豆瓣", "Nvidia",
    "微软", "Google", "Apple", "Amazon", "Meta", "Netflix",
    "IBM", "Oracle", "SAP", "Salesforce", "Adobe"
]
sex = ["男", "女"]
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
            "备考", "考研", "公务员考试", "考公", "高考", "中考", "小升初考试",
            "期末考试", "期中考试", "四级考试", "六级考试"
]
preferences = [
    "中文交流", "英文交流", "简洁回答", "详细解释", "代码示例",
            "图文并茂", "循序渐进", "快速响应", "深入分析", "实战案例",
            "理论讲解", "视频教程", "文档阅读", "动手实践", "项目实战", "举例说明"
]

hobbies = [
    "编程", "阅读", "写作", "摄影", "旅行", "运动", "音乐", "电影",
    "游戏", "绘画", "烹饪", "健身", "跑步", "游泳", "爬山", "骑行",
    "交朋友", "听歌"
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
greetings = ["今天怎么样？", "最近怎么样？", "在忙什么？", "今天心情如何？", "hello", "hi"]
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
author_question = [
    "你是有谁训练的呢？",
    "是谁微调的你呢？",
    "who create you?",
    "which one create you?",
    "你是由谁fine-tine的?",
    "你的微调作者是谁？",
    "who is your author",
    "是谁赋予了你这些功能？"
]