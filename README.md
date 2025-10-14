# 🎓 Stanford CS183B 创业课程字幕转笔记工具

这是一个专为 Stanford CS183B 创业课程设计的智能字幕转笔记工具，能够将英文字幕自动转换为高质量的中英对照学习笔记。支持单文件和批量处理模式。

## ✨ 特性

- 🚀 **高速并发处理** - 比传统方式快 5-8 倍
- � **批量处理模式** - 一次处理整个文件夹的所有字幕
- �📝 **段落级翻译** - 保持内容连贯性的智能翻译
- 🎨 **简洁格式** - 清晰的 Markdown 格式，便于阅读
- 🧠 **智能分块** - 保持段落完整性的分割算法
- � **处理报告** - 自动生成详细的批量处理报告
- �🔑 **API 密钥管理** - 安全便捷的密钥存储

## 📁 项目结构

```
startup/
├── README.md                           # 使用说明
├── prompt_command.md                   # 命令参考
├── raw/                               # 原始字幕文件夹
│   ├── [English] Lecture 5 - ...txt  # 原始字幕文件
│   └── ...
├── processed/                         # 处理后的文件夹
│   ├── Lecture5_Notes.md             # 处理后的笔记
│   ├── batch_process_report.md       # 处理报告
│   └── ...
├── subtle/                           # 手动处理的笔记
│   ├── Lecture1_Notes.md            # 示例笔记
│   └── ...
└── tools/                           # 工具目录
    ├── optimized_converter.py          # 核心转换器
    ├── optimized_convert.bat           # Windows批处理界面
    ├── set_api_key.bat                 # API密钥设置
    ├── install.bat                     # 一键安装脚本
    └── requirements.txt                # Python依赖
```

## 🚀 快速开始

### 1. 环境准备

```bash
# 方法1：一键安装（推荐）
tools\install.bat

# 方法2：手动安装
pip install -r tools\requirements.txt
```

### 2. 设置 API 密钥

获取 DeepSeek API 密钥：[https://platform.deepseek.com/](https://platform.deepseek.com/)

```bash
# 设置API密钥（一次性设置）
tools\set_api_key.bat "sk-your-deepseek-api-key"
```

### 3. 处理字幕文件

#### 🎯 批量处理（推荐）

```bash
# 图形化界面批量处理
tools\subtitle_processor.bat

# 或直接批量处理 raw 文件夹
tools\batch_process.bat
```

#### 📄 单文件处理

```bash
# 最简单的用法
tools\optimized_convert.bat "字幕文件.txt"

# 指定输出文件名
tools\optimized_convert.bat "字幕文件.txt" -o "笔记.md"

# 临时使用不同的API密钥
tools\optimized_convert.bat -k "sk-xxx" "字幕文件.txt"
```

## 📖 详细使用说明

### 批量处理模式

```bash
# 批量处理 raw 文件夹中的所有 .txt 文件
python tools\optimized_converter.py raw --batch -k "your-api-key" -c 6 -o processed

# 自定义文件夹和匹配模式
python tools\optimized_converter.py "custom_folder" --batch --pattern "Lecture*.txt" -c 4
```

### 单文件处理

```bash
# 转换单个文件
tools\optimized_convert.bat "[English] Lecture 1.txt"

# 指定输出文件和并发数
python tools\optimized_converter.py "lecture.txt" -o "notes.md" -c 8

# 调整AI参数
python tools\optimized_converter.py "lecture.txt" --temperature 0.1 --chunk-size 40
```

### 高级参数

| 参数                | 默认值   | 说明              |
| ------------------- | -------- | ----------------- |
| `-k, --api-key`     | 环境变量 | DeepSeek API 密钥 |
| `-o, --output`      | 自动生成 | 输出文件路径      |
| `-c, --concurrency` | 6        | 并发处理数量      |
| `--chunk-size`      | 35       | 每块处理的行数    |
| `--temperature`     | 0.2      | AI 创意度（0-1）  |

### 性能优化建议

- **并发数调整**：根据网络情况调整`-c`参数（建议 4-8）
- **块大小**：`--chunk-size`建议 30-50，太大可能超时
- **API 配额**：注意 DeepSeek API 的使用限制

## 📋 输出格式示例

转换后的文件将包含：

```markdown
# Welcome to CS183B

Welcome everyone. Can we turn on the microphone? Can people in the back hear clearly?

大家好。请问可以打开麦克风吗？后排的听众能听清楚吗？

I am Sam Altman, President of Y Combinator. Nine years ago, I was a student at Stanford University...

我是萨姆·奥尔特曼，Y Combinator 的总裁。九年前，我还是斯坦福大学的学生...
```

## 🛠️ 故障排除

### 常见问题

**1. API 密钥错误**

```bash
# 重新设置密钥
tools\set_api_key.bat "新的API密钥"
```

**2. 网络超时**

```bash
# 降低并发数
python tools\optimized_converter.py "file.txt" -c 2
```

**3. 文件编码问题**

- 确保字幕文件为 UTF-8 编码
- 使用记事本另存为 UTF-8 格式

**4. Python 环境问题**

```bash
# 重新安装依赖
pip install --upgrade openai aiohttp
```

## 📊 处理统计

转换完成后会显示：

- ⏱️ 处理时间
- 📊 分块数量
- 🚀 平均速度
- 📁 输出文件路径

## 🔧 开发信息

- **核心引擎**：DeepSeek API + Python asyncio
- **并发处理**：aiohttp 异步 HTTP 请求
- **智能分块**：保持段落完整性的文本分割
- **格式优化**：Markdown 格式化输出

## 📞 支持

如遇问题，请检查：

1. API 密钥是否正确设置
2. 网络连接是否正常
3. Python 环境是否完整
4. 字幕文件格式是否正确

---

**注意**：本工具专为 Stanford CS183B 课程设计，适用于英文字幕转中英对照笔记。其他用途的效果可能有所不同。
