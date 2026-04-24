import re
import os
from pathlib import Path

# 完全不依赖 yaml 库的简单解析实现
def simulate_load_knowledge(content):
    metadata = {}
    knowledge = ""
    
    # 正则匹配 YAML frontmatter: --- (yaml) --- (markdown)
    frontmatter_pattern = re.compile(r'^---\s*\n(.*?)\n---\s*\n', re.DOTALL | re.MULTILINE)
    match = frontmatter_pattern.search(content)
    
    if match:
        yaml_block = match.group(1)
        # 模拟简单 key: value 解析
        for line in yaml_block.split('\n'):
            line = line.strip()
            if not line or line.startswith('-'): continue
            if ':' in line:
                k, v = line.split(':', 1)
                metadata[k.strip()] = v.strip()
        
        # 提取 Markdown 正文
        knowledge = content[match.end():].strip()
    else:
        knowledge = content
        
    return metadata, knowledge

def test_standalone():
    # 模拟一个完整的 skill.md 内容
    test_content = """---
name: test_skill
description: 这是一个测试技能。
trigger_keywords:
  - test
  - demo
version: 1.0
---

# 技能正文标题
这里是具体的执行步骤：
1. 第一步
2. 第二步

> 注意事项：不要混淆。
"""
    
    print("=== 开始验证解析逻辑 (无依赖模式) ===")
    meta, body = simulate_load_knowledge(test_content)
    
    print("\n[1] 提取的元数据:")
    for k, v in meta.items():
        print(f"  {k}: {v}")
        
    print("\n[2] 提取的正文:")
    print("-" * 30)
    print(body)
    print("-" * 30)
    
    # 验证逻辑
    assert meta['name'] == 'test_skill'
    assert "技能正文标题" in body
    assert "---" not in body  # 关键点：分隔符不能在正文中
    print("\n✅ 验证通过：YAML 和正文已实现精准分离！")

if __name__ == "__main__":
    test_standalone()
