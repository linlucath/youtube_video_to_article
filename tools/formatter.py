import os
import shutil
import re
import yaml
import requests
from datetime import datetime

# Base paths
base_path = "../"
processed_path = os.path.join(base_path, "output")

# Load config
config_path = os.path.join(base_path, "config.yml")
with open(config_path, 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)
output_path = config['output_path']

default_image = os.path.join(base_path, r"assets\default.jpg")

# DeepSeek API configuration
API_KEY = os.getenv('DEEPSEEK_API_KEY')
API_URL = "https://api.deepseek.com/chat/completions"


def extract_title_with_ai(original_filename: str) -> str:
    """
    使用AI从原始文件名中提取简洁的标题
    
    Args:
        original_filename: 原始文件名（不含扩展名）
        
    Returns:
        提取后的简洁标题
    """
    if not API_KEY:
        print("⚠️ 未设置 DEEPSEEK_API_KEY，使用备用方案")
        return fallback_title(original_filename)
    
    prompt = f"""请从以下视频标题中提取最核心的主题作为文章标题。

原始标题：{original_filename}

提取规则（按优先级）：
1. **优先提取课程主题**：如果标题中有具体的课程主题（如 Autoregressive Models, Generative AI with SDEs），直接使用该主题作为标题
2. **其次使用课程名称+序号**：如果没有具体主题但有课程序号，则提取课程名称和序号，格式为 "{{课程名称}} Lecture {{序号}}"
3. **仅使用课程名称**：如果既没有具体主题也没有序号，则只输出课程名称
4. **非课程内容**：如果这不是课程相关的视频，请自行提炼一个简洁、准确的标题，概括视频的核心内容

需要去除的内容：
- 学校名称（UC Berkeley, MIT 等）
- 学期信息（Spring 2024, SP24 等）
- 课程代号（CS294-158, 6.S184 等）
- 语言后缀（_en, _cn 等）
- 频道名称、视频编号等无关信息

示例：
输入：L2 Autoregressive Models -- CS294-158 SP24 Deep Unsupervised Learning -- UC Berkeley Spring 2024_en
输出：Autoregressive Models

输入：L1 Introduction -- CS294-158 SP24 Deep Unsupervised Learning -- UC Berkeley Spring 2024_en
输出：Deep Unsupervised Learning Lecture 1

输入：MIT 6.S184 Flow Matching and Diffusion Models - Lecture 01 - Generative AI with SDEs
输出：Generative AI with SDEs

输入：MIT 6.S184 Flow Matching and Diffusion Models - Lecture 02 - Constructing a Training Target
输出：Constructing a Training Target

输入：MIT_6.S184__Flow_Matching_and_Diffusion_Models_-_Lecture_02_-_Constructing_a_Training_Target
输出：Constructing a Training Target

输入：How to Build a Neural Network from Scratch - Full Tutorial 2024
输出：Build a Neural Network from Scratch

输入：Why Transformers are Taking Over AI - Explained Simply
输出：Why Transformers are Taking Over AI

只输出最终的标题，不要任何解释："""

    try:
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {
                    "role": "system",
                    "content": "你是一个专业的标题提取助手，擅长从冗长的视频标题中提取简洁的核心主题。"
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.1,
            "max_tokens": 100
        }
        
        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }
        
        response = requests.post(API_URL, json=payload, headers=headers, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            if 'choices' in result and result['choices']:
                title = result['choices'][0]['message']['content'].strip()
                print(f"🏷️ AI提取标题: {original_filename} -> {title}")
                return title
                
    except Exception as e:
        print(f"⚠️ AI提取标题失败: {e}")
    
    return fallback_title(original_filename)


def fallback_title(original_filename: str) -> str:
    """备用标题提取方案"""
    title = original_filename.replace('_en', '').replace('_', ' ')
    print(f"🏷️ 使用备用标题: {title}")
    return title


def sanitize_filename(title: str) -> str:
    """将标题转换为有效的文件夹名"""
    # 移除非法字符
    name = re.sub(r'[<>:"/\\|?*]', '', title)
    # 空格替换为下划线
    name = re.sub(r'\s+', '_', name)
    name = name.strip('_')
    return name


# Get all markdown files in processed folder
files = [f for f in os.listdir(processed_path) if f.endswith('.md')]

for filename in files:
    file_path = os.path.join(processed_path, filename)
    
    # 使用 AI 从原始文件名提取标题
    original_name = filename.replace('.md', '')
    title = extract_title_with_ai(original_name)
    folder_name = sanitize_filename(title)
    
    # Read original content
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Get current date
    current_date = datetime.now().strftime('%Y-%m-%d')
    
    # Create frontmatter
    frontmatter = f"""---
title: '{title[:59]}'
publishDate: {current_date}
description: 'TODO'
tags:
  - TODO
language: 'English'
heroImage: {{ src: './default.jpg', color: '#D58388' }}
---

"""
    
    # Combine frontmatter with content
    new_content = frontmatter + content
    
    # Create new folder
    new_folder = os.path.join(output_path, folder_name)
    os.makedirs(new_folder, exist_ok=True)
    
    # Write updated file to new folder (use sanitized filename)
    new_filename = f"{folder_name}.md"
    new_file_path = os.path.join(new_folder, new_filename)
    with open(new_file_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    # Copy default.jpg to new folder
    new_image_path = os.path.join(new_folder, "default.jpg")
    shutil.copy2(default_image, new_image_path)
    
    print(f"✅ Processed {filename} -> {folder_name}/")

print("\n🎉 All files processed successfully!")
print(f"📊 Total files processed: {len(files)}")
