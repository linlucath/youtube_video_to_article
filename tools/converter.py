import os
import asyncio
import aiohttp
import json
import time
import argparse
from typing import List, Dict, Any
import logging
import re
import sys
import glob
from pathlib import Path

# 设置标准输出编码为UTF-8以支持中文字符
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer)
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer)

class OptimizedSubtitleConverter:
    def __init__(self, api_key: str, config: Dict[str, Any] = None):
        """
        初始化优化转换器
        
        Args:
            api_key: DeepSeek API密钥
            config: 配置参数
        """
        self.api_key = api_key
        self.base_url = "https://api.deepseek.com/chat/completions"
        
        # 优化的默认配置
        default_config = {
            "model": "deepseek-chat",
            "temperature": 0.1,  # 低温度确保准确性
            "max_tokens": 3500,
            "chunk_size": 200,  # 每块默认包含的单词数
            "request_timeout": 40,
            "retry_attempts": 3,
            "retry_delay": 2,
            "enable_retry": True  # 默认启用重处理
        }
        
        self.config = {**default_config, **(config or {})}
        
        # 失败内容收集
        self.failed_chunks = []
        
        # 设置日志 - 同时输出到控制台和文件
        log_dir = Path('logs')
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / f'converter_{time.strftime("%Y%m%d_%H%M%S")}.log'
        
        # 创建专属的logger，避免与其他logger冲突
        self.logger = logging.getLogger(f'OptimizedSubtitleConverter_{id(self)}')
        self.logger.setLevel(logging.DEBUG)  # 设置为DEBUG级别以捕获所有日志
        
        # 清除可能存在的旧handlers
        self.logger.handlers.clear()
        
        # 文件handler - 使用utf-8-sig编码以便Windows记事本能正确显示
        file_handler = logging.FileHandler(log_file, encoding='utf-8-sig', mode='w')
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(file_formatter)
        
        # 控制台handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(console_formatter)
        
        # 添加handlers
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
        
        # 防止日志传播到root logger
        self.logger.propagate = False
        
        self.logger.info(f"📝 日志文件: {log_file}")
        self.logger.debug(f"🔧 Logger初始化完成，ID: {id(self)}")
        
        
        self.prompt_template = """你是专业的文档编辑专家和翻译专家, 请严格按照以下要求处理字幕文本：

==== 处理要求 ====
1. **错误修正**：识别并修正可能存在的识别错误, 确保文本准确性
2. **完整性检查**：检查文本末尾，识别被截断的不完整句子
3. **段落整理**：仅对完整句子进行段落重组, 将不完整句子原样返回
4. **翻译准确性**：提供准确、专业、符合中文表达习惯的翻译

==== 输出格式 ====
必须严格按照以下格式输出，不得添加任何其他内容：

[去除不完整句子的英文整理段落]

[对应中文翻译]

[不完整句子: 原始不完整文本]

==== 禁止事项 ====
- 禁止添加任何解释说明
- 禁止添加处理步骤描述  
- 禁止翻译不完整句子
- 禁止自行补全截断的句子
- 禁止添加标题、序号或其他格式化标记

原始文本：
{chunk}

请直接输出处理结果："""

    def read_file(self, file_path: str) -> str:
        """读取文件内容，支持多种编码"""
        encodings = ['utf-8', 'gbk', 'gb2312', 'ascii']
        
        self.logger.info(f"📖 开始读取文件: {file_path}")
        
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    content = f.read()
                self.logger.info(f"✅ 文件读取成功，编码: {encoding}, 长度: {len(content)}字符")
                self.logger.debug(f"📄 文件内容预览:\n{content[:300]}...")
                return content
            except UnicodeDecodeError:
                self.logger.debug(f"❌ 编码 {encoding} 读取失败，尝试下一个...")
                continue
        
        self.logger.error(f"❌ 无法读取文件，尝试的所有编码均失败: {encodings}")
        raise ValueError(f"无法读取文件 {file_path}，尝试的编码: {encodings}")
    
    
    def strip_content(self, content: str) -> str:
        """清理AI返回的内容"""
        return content.strip()

    async def process_chunk_async(self, session: aiohttp.ClientSession, chunk: str, chunk_index: int) -> tuple:
        """异步处理单个文本块"""
        
        self.logger.debug(f"📤 开始处理块 {chunk_index + 1}, 输入长度: {len(chunk)}字符")
        self.logger.debug(f"📤 输入内容预览: '{chunk[:200]}...'")
        
        for attempt in range(self.config['retry_attempts']):
            try:
                prompt = self.prompt_template.format(chunk=chunk)
                self.logger.debug(f"🔧 生成的提示词长度: {len(prompt)}字符")
                
                payload = {
                    "model": self.config['model'],
                    "messages": [
                        {
                            "role": "system",
                            "content": "你是专业的双语文档编辑助手，专注于高质量的内容整理和翻译。"
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "temperature": self.config['temperature'],
                    "max_tokens": self.config['max_tokens']
                }
                
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
                
                timeout = aiohttp.ClientTimeout(total=self.config['request_timeout'])
                
                self.logger.debug(f"🌐 发送API请求到 {self.base_url}")
                
                async with session.post(
                    self.base_url,
                    json=payload,
                    headers=headers,
                    timeout=timeout
                ) as response:
                    
                    self.logger.debug(f"📡 收到响应，状态码: {response.status}")
                    
                    if response.status == 200:
                        result = await response.json()
                        if 'choices' in result and result['choices']:
                            raw_content = result['choices'][0]['message']['content'].strip()
                            self.logger.debug(f"🤖 AI原始返回长度: {len(raw_content)}字符")
                            self.logger.debug(f"🤖 AI返回开头: '{raw_content[:150]}...'")
                            
                            # 清理内容
                            content = self.strip_content(raw_content)
                            self.logger.debug(f"🧹 清理后长度: {len(content)}字符")
                            
                            # 检查是否包含不完整句子标记
                            if '[不完整句子:' in content:
                                self.logger.info(f"🔗 AI检测到不完整句子在块 {chunk_index + 1}")
                            else:
                                self.logger.debug(f"✅ 块 {chunk_index + 1} 无不完整句子")
                            
                            self.logger.info(f"✅ 完成块 {chunk_index + 1}")
                            return (chunk_index, content)
                        else:
                            raise Exception(f"API响应格式错误: {result}")
                    else:
                        error_text = await response.text()
                        self.logger.error(f"API错误详情 - 状态码: {response.status}, 响应: {error_text}")
                        raise Exception(f"API错误 {response.status}: {error_text}")
                        
            except Exception as e:
                wait_time = self.config['retry_delay'] * (2 ** attempt)
                self.logger.warning(f"块 {chunk_index + 1} 失败 (第{attempt + 1}次): {e}")
                
                if attempt < self.config['retry_attempts'] - 1:
                    self.logger.info(f"等待 {wait_time} 秒后重试...")
                    await asyncio.sleep(wait_time)
                else:
                    self.logger.error(f"块 {chunk_index + 1} 彻底失败，保留原始内容")
                    # 记录失败的块信息
                    failed_chunk_info = {
                        'index': chunk_index,
                        'content': chunk,
                        'error': str(e)
                    }
                    self.failed_chunks.append(failed_chunk_info)
                    return (chunk_index, f"# 处理失败的内容\n\n{chunk}")

    def split_text(self, text: str) -> List[str]:
        """分割文本为块"""
        chunk_size = self.config['chunk_size']
        words = text.split()
        self.logger.info(f"📊 文本统计: 总字符数={len(text)}, 总单词数={len(words)}")
        self.logger.info(f"📊 分块配置: 每块{chunk_size}单词")
        
        chunks = []

        for i in range(0, len(words), chunk_size):
            chunk = ' '.join(words[i:i + chunk_size])
            chunks.append(chunk)
            self.logger.debug(f"✂️  块 {len(chunks)}: {len(chunk)}字符, {len(chunk.split())}单词")

        self.logger.info(f"✂️  分割完成: 共{len(chunks)}块")
        return chunks

    async def process_file_async(self, input_file: str, output_file: str = None):
        """异步顺序处理文件"""
        if not os.path.exists(input_file):
            raise FileNotFoundError(f"找不到文件: {input_file}")
        
        if output_file is None:
            name, ext = os.path.splitext(input_file)
            output_file = f"{name}_optimized.md"
        
        self.logger.info(f"🚀 开始处理: {input_file}")
        self.logger.info(f"📁 输出文件: {output_file}")
        
        # 读取和分割文件
        content = self.read_file(input_file)
        chunks = self.split_text(content)
        total_chunks = len(chunks)
        
        self.logger.info(f"📊 智能分割为 {total_chunks} 块")
        self.logger.info(f"🔄 使用顺序处理模式")
        
        start_time = time.time()
        
        # 顺序处理并处理不完整句子
        processed_chunks = await self.process_chunks_sequentially(chunks)
        
        # 检查是否有失败的块需要重新处理
        if self.failed_chunks and self.config.get('enable_retry', False):
            self.logger.info(f"🔄 发现 {len(self.failed_chunks)} 个失败的块，开始重新处理...")
            reprocessed_chunks = await self.reprocess_failed_chunks()
            
            # 创建失败块索引到重处理结果的映射
            reprocess_map = {r['original_index']: r for r in reprocessed_chunks}
            
            # 替换失败的内容
            for i, chunk in enumerate(processed_chunks):
                if chunk.startswith("# 处理失败的内容"):
                    # 根据位置推断原始块索引
                    if i in reprocess_map:
                        reprocessed = reprocess_map[i]
                        processed_chunks[i] = reprocessed['content']
                        status = "✅ 成功" if reprocessed['success'] else "🔧 已清理"
                        self.logger.info(f"{status} 替换块 {i+1} 的失败内容")
            
            # 清空失败列表
            self.failed_chunks.clear()
        elif self.failed_chunks:
            self.logger.info(f"⚠️  有 {len(self.failed_chunks)} 个块处理失败，但未启用自动重处理")
        
        # 合并内容
        final_content = self.merge_content(processed_chunks)
        
        # 写入文件
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(final_content)
        
        elapsed_time = time.time() - start_time
        self.logger.info(f"🎉 处理完成！")
        self.logger.info(f"⏱️  用时: {elapsed_time:.1f} 秒")
        self.logger.info(f"📈 平均速度: {total_chunks/elapsed_time:.1f} 块/秒")
        
        return output_file

    async def process_chunks_sequentially(self, chunks: List[str]) -> List[str]:
        """顺序处理文本块，处理不完整句子传递"""
        processed_chunks = []
        incomplete_sentence = ""
        
        connector = aiohttp.TCPConnector(limit=1, limit_per_host=1)
        
        async with aiohttp.ClientSession(connector=connector) as session:
            for i, chunk in enumerate(chunks):
                self.logger.info(f"\n{'='*60}")
                self.logger.info(f"🔄 开始处理块 {i+1}/{len(chunks)}")
                
                original_chunk = chunk
                # 如果有不完整句子，添加到当前块开头
                if incomplete_sentence:
                    chunk = incomplete_sentence + " " + chunk
                    self.logger.info(f"📎 块 {i+1} 合并了前一块的不完整句子")
                    self.logger.debug(f"🔗 不完整句子: '{incomplete_sentence[:100]}...'")
                    self.logger.debug(f"📝 原始块开头: '{original_chunk[:100]}...'")
                    self.logger.debug(f"� 合并后块开头: '{chunk[:100]}...'")
                else:
                    self.logger.debug(f"📝 当前块开头: '{chunk[:100]}...'")
                
                self.logger.info(f"📊 当前块统计: {len(chunk)}字符, {len(chunk.split())}单词")
                
                # 处理当前块
                try:
                    result = await self.process_chunk_async(session, chunk, i)
                    index, content = result

                    self.logger.info(f"ai 返回内容:\n{content}\n")
                    
                    # 检查是否有不完整句子
                    content, new_incomplete = self.extract_incomplete_sentence(content)
                    
                    self.logger.debug(f"📊 处理后内容长度: {len(content)}字符")
                    processed_chunks.append(content)
                    
                    # 更新不完整句子状态
                    if new_incomplete:
                        self.logger.info(f"🔗 提取到不完整句子: '{new_incomplete[:80]}...'")
                        self.logger.info(f"� 将传递给块 {i+2}")
                        incomplete_sentence = new_incomplete
                    else:
                        if incomplete_sentence:
                            self.logger.info(f"✅ 前一个不完整句子已处理完成")
                        incomplete_sentence = ""
                    
                except Exception as e:
                    self.logger.error(f"❌ 块 {i+1} 处理失败: {e}")
                    processed_chunks.append(f"# 处理失败的内容\n\n{chunk}")
                    incomplete_sentence = ""  # 重置不完整句子
        
        # 处理最后可能剩余的不完整句子
        if incomplete_sentence:
            self.logger.warning(f"⚠️  文件末尾存在未处理的不完整句子: {incomplete_sentence}")
            if processed_chunks:
                processed_chunks[-1] += f"\n\n[文件末尾不完整句子: {incomplete_sentence}]"
        
        return processed_chunks
    
    def extract_incomplete_sentence(self, content: str) -> tuple[str, str]:
        """从处理结果中提取不完整句子"""
        if not content:
            self.logger.debug("⚠️  内容为空，跳过不完整句子检查")
            return content, ""
        
        self.logger.debug(f"🔍 检查不完整句子标记，内容长度: {len(content)}字符")
        self.logger.debug(f"🔍 内容预览: '{content[:300]}...'")
        
        # 查找不完整句子标记
        incomplete_pattern = r'\[不完整句子:\s*([^\]]+)\]'
        match = re.search(incomplete_pattern, content)
        
        if match:
            incomplete_sentence = match.group(1).strip()
            self.logger.info(f"🔗 发现不完整句子标记!")
            self.logger.info(f"🔗 不完整句子内容: '{incomplete_sentence[:150]}...'")
            self.logger.debug(f"🔗 不完整句子长度: {len(incomplete_sentence)}字符")
            
            # 从内容中移除不完整句子标记
            clean_content = re.sub(incomplete_pattern, '', content).strip()
            self.logger.debug(f"🧹 移除标记前长度: {len(content)}字符")
            self.logger.debug(f"🧹 移除标记后长度: {len(clean_content)}字符")
            self.logger.debug(f"🧹 清理后内容预览: '{clean_content[:200]}...'")
            return clean_content, incomplete_sentence
        else:
            self.logger.debug("✅ 未发现不完整句子标记")
            self.logger.debug(f"✅ 完整内容预览: '{content[:200]}...'")
        
        return content, ""
    
    def merge_content(self, chunks: List[str]) -> str:
        """合并内容"""
        self.logger.info(f"🔗 开始合并内容: 总块数={len(chunks)}")
        
        # 过滤空内容
        valid_chunks = [chunk for chunk in chunks if chunk and chunk.strip()]
        self.logger.info(f"🔗 有效块数: {len(valid_chunks)}/{len(chunks)}")
        
        if len(valid_chunks) < len(chunks):
            empty_count = len(chunks) - len(valid_chunks)
            self.logger.warning(f"⚠️  发现 {empty_count} 个空块已被过滤")
        
        # 合并
        content = '\n\n'.join(valid_chunks)
        self.logger.info(f"🔗 合并后总长度: {len(content)}字符")
        self.logger.debug(f"🔗 合并后的内容预览:\n{content[:500]}...")
        
        # 最终清理
        self.logger.info("🧹 开始最终清理...")
        content = self.final_cleanup(content)
        self.logger.info(f"🧹 清理后总长度: {len(content)}字符")
        
        return content

    def final_cleanup(self, content: str) -> str:
        """最终内容清理"""
        self.logger.info("🧹 开始最终清理...")
        self.logger.info(f"🧹 清理前内容长度: {len(content)} 字符")
        self.logger.debug(f"🧹 清理前内容开头:\n{content[:500]}...")
        
        # 查找所有方括号内容并分类处理
        brackets_content = re.findall(r'\[[^\]]*\]', content)
        if brackets_content:
            self.logger.info(f"🔍 发现方括号内容: {len(brackets_content)} 个")
            for i, bracket in enumerate(brackets_content[:5]):  # 显示前5个
                self.logger.debug(f"  📋 方括号 {i+1}: {bracket[:100]}...")
        else:
            self.logger.info("✅ 未发现方括号内容")
        
        # 只移除特定的格式标记和不完整句子标记，但保留其他可能有用的标记
        format_markers = [
            r'\[英文整理段落\]',
            r'\[对应中文翻译\]', 
            r'\[如有不完整句子\]',
            r'\[不完整句子:[^\]]*\]',
            r'\[文件末尾不完整句子:[^\]]*\]',
            r'\[不完整句子\]'
        ]
        
        self.logger.info(f"🔧 准备移除 {len(format_markers)} 种格式标记")
        
        # 移除AI添加的格式说明标记
        total_removed = 0
        for pattern in format_markers:
            before_len = len(content)
            content = re.sub(pattern, '', content)
            after_len = len(content)
            if before_len != after_len:
                removed = before_len - after_len
                total_removed += removed
                self.logger.info(f"  ✂️  移除格式标记: {pattern[:30]}..., 减少 {removed} 字符")
        
        if total_removed > 0:
            self.logger.info(f"🗑️  共移除格式标记: {total_removed} 字符")
        else:
            self.logger.info("✅ 未发现需要移除的格式标记")
        
        # 移除可能包含长文本的方括号块（这些通常是AI错误返回的格式）
        # 但要小心不要移除真正的内容
        long_bracket_pattern = r'\[[^\]]{100,}\]'  # 超过100字符的方括号内容
        long_brackets = re.findall(long_bracket_pattern, content)
        if long_brackets:
            self.logger.warning(f"⚠️  发现 {len(long_brackets)} 个长方括号块，可能是格式错误")
            for i, bracket in enumerate(long_brackets[:3]):
                self.logger.debug(f"  📋 长方括号 {i+1} ({len(bracket)}字符): {bracket[:150]}...")
            before_len = len(content)
            content = re.sub(long_bracket_pattern, '', content)
            after_len = len(content)
            self.logger.info(f"  ✂️  移除长方括号块，减少 {before_len - after_len} 字符")
        else:
            self.logger.info("✅ 未发现异常长方括号块")
        
        self.logger.info(f"📊 移除格式标记后长度: {len(content)} 字符")
        
        # 确保标题格式正确
        before_len = len(content)
        content = re.sub(r'\n(#{1,6}\s)', r'\n\n\1', content)
        if len(content) != before_len:
            self.logger.debug(f"🔧 标题格式调整，长度变化: {len(content) - before_len}")
        
        # 清理多余的空行
        before_len = len(content)
        content = re.sub(r'\n{3,}', '\n\n', content)
        if len(content) != before_len:
            self.logger.debug(f"🔧 清理多余空行，减少 {before_len - len(content)} 字符")
        
        # 清理首尾空行
        before_len = len(content)
        content = content.strip()
        if len(content) != before_len:
            self.logger.debug(f"🔧 清理首尾空行，减少 {before_len - len(content)} 字符")
        
        self.logger.info(f"✅ 最终清理完成，长度: {len(content)} 字符")
        self.logger.debug(f"✅ 清理后内容开头:\n{content[:500]}...")
        
        return content

    def process_file(self, input_file: str, output_file: str = None):
        """同步接口"""
        return asyncio.run(self.process_file_async(input_file, output_file))

    def batch_process_folder(self, input_folder: str, output_folder: str = None, file_pattern: str = "*.txt"):
        """批量处理文件夹中的所有文件"""
        input_path = Path(input_folder)
        if not input_path.exists():
            raise FileNotFoundError(f"找不到文件夹: {input_folder}")
        
        if not input_path.is_dir():
            raise ValueError(f"路径不是文件夹: {input_folder}")
        
        # 设置输出文件夹
        if output_folder is None:
            output_folder = input_path.parent / "processed"
        output_path = Path(output_folder)
        output_path.mkdir(exist_ok=True)
        
        # 查找所有匹配的文件
        pattern_path = input_path / file_pattern
        files = list(input_path.glob(file_pattern))
        
        if not files:
            self.logger.warning(f"在文件夹 {input_folder} 中未找到匹配 {file_pattern} 的文件")
            return []
        
        self.logger.info(f"📁 找到 {len(files)} 个待处理文件")
        
        processed_files = []
        total_start_time = time.time()
        
        for i, input_file in enumerate(files, 1):
            try:
                self.logger.info(f"\n{'='*50}")
                self.logger.info(f"📄 处理文件 {i}/{len(files)}: {input_file.name}")
                self.logger.info(f"{'='*50}")
                
                # 生成输出文件名
                # 将文件名中的特殊字符替换为更简洁的格式
                clean_name = self.clean_filename(input_file.stem)
                output_file = output_path / f"{clean_name}.md"
                
                # 处理文件
                result_file = self.process_file(str(input_file), str(output_file))
                processed_files.append({
                    'input': str(input_file),
                    'output': result_file,
                    'status': 'success'
                })
                
                self.logger.info(f"✅ 完成: {input_file.name} -> {Path(result_file).name}")
                
            except Exception as e:
                self.logger.error(f"❌ 处理失败 {input_file.name}: {e}")
                processed_files.append({
                    'input': str(input_file),
                    'output': None,
                    'status': 'failed',
                    'error': str(e)
                })
        
        total_elapsed = time.time() - total_start_time
        
        # 统计结果
        success_count = sum(1 for f in processed_files if f['status'] == 'success')
        failed_count = len(processed_files) - success_count
        
        self.logger.info(f"\n🎉 批量处理完成!")
        self.logger.info(f"📊 总计: {len(processed_files)} 个文件")
        self.logger.info(f"✅ 成功: {success_count} 个")
        self.logger.info(f"❌ 失败: {failed_count} 个")
        self.logger.info(f"⏱️  总用时: {total_elapsed/60:.1f} 分钟")
        self.logger.info(f"📁 输出文件夹: {output_folder}")
        
        return processed_files

    def clean_filename(self, filename: str) -> str:
        """清理文件名，生成更简洁的输出文件名"""
        # 提取讲座编号
        lecture_match = re.search(r'Lecture\s*(\d+)', filename, re.IGNORECASE)
        if lecture_match:
            lecture_num = lecture_match.group(1)
            return f"Lecture{lecture_num}_Notes"
        
        # 如果没有找到讲座编号，清理特殊字符
        clean = re.sub(r'[\[\](){}]', '', filename)
        clean = re.sub(r'[^\w\s-]', '', clean)
        clean = re.sub(r'\s+', '_', clean.strip())
        clean = clean.replace('__', '_').strip('_')
        
        # 限制长度
        if len(clean) > 50:
            clean = clean[:50].rstrip('_')
        
        return clean or "processed_file"

    async def batch_process_folder_async(self, input_folder: str, output_folder: str = None, file_pattern: str = "*.txt"):
        """异步批量处理文件夹"""
        # 这个方法可以用于未来的优化，现在先使用同步版本
        return self.batch_process_folder(input_folder, output_folder, file_pattern)


def main():
    parser = argparse.ArgumentParser(description='优化字幕转换器 - 顺序处理、智能分块、段落级翻译')
    parser.add_argument('--input_path', help='输入字幕文件路径或文件夹路径', default='./raw')
    parser.add_argument('-o', '--output', help='输出文件路径或文件夹路径', default="output.md")
    parser.add_argument('-k', '--api-key', help='DeepSeek API密钥')
    parser.add_argument('--chunk-size', type=int, help='每块包含的单词数', default=200)
    parser.add_argument('--temperature', type=float, default=0.1, help='AI温度参数')
    parser.add_argument('--batch', action='store_true', help='批量处理模式，处理文件夹中的所有文件')
    parser.add_argument('--pattern', default='*.txt', help='批量模式下的文件匹配模式 (默认: *.txt)')
    parser.add_argument('--enable-retry', action='store_true', help='启用失败内容自动重处理')
    
    args = parser.parse_args()
    
    # 获取API密钥
    api_key = args.api_key or os.getenv('DEEPSEEK_API_KEY')
    if not api_key:
        print("❌ 错误: 请提供DeepSeek API密钥")
        print("💡 方法1: 使用 -k 参数")
        print("💡 方法2: 设置环境变量 DEEPSEEK_API_KEY")
        return
    
    # 配置
    config = {
        "chunk_size": args.chunk_size,
        "temperature": args.temperature,
        "enable_retry": args.enable_retry
    }
    
    try:
        converter = OptimizedSubtitleConverter(api_key, config)
        
        # 判断是批量处理还是单文件处理
        input_path = Path(args.input_path)
    
        print("🚀 启动批量处理模式")
        if not input_path.is_dir():
            print(f"❌ 错误: 批量模式需要文件夹路径，但提供的是文件: {args.input_path}")
            return
        
        results = converter.batch_process_folder(
            str(input_path), 
            args.output
        )
        
        success_count = sum(1 for r in results if r['status'] == 'success')
        print(f"\n🎉 批量处理完成!")
        print(f"📊 成功处理 {success_count}/{len(results)} 个文件")
        
    except Exception as e:
        print(f"❌ 处理失败: {e}")
        logging.error(f"处理失败: {e}", exc_info=True)


if __name__ == "__main__":
    main()