"""
YouTube 字幕下载器
支持从 YouTube 视频链接下载字幕文件
"""

import os
import sys
import argparse
from pathlib import Path
from typing import Optional, List
import logging

# Windows 控制台输出优化（仅用于 print，不修改 sys.stdout）
if sys.platform == 'win32':
    try:
        # 尝试设置控制台为 UTF-8 模式
        os.system('chcp 65001 >nul 2>&1')
    except:
        pass

try:
    from youtube_transcript_api import YouTubeTranscriptApi
except ImportError:
    print("错误: 需要安装 youtube-transcript-api 库")
    print("请运行: pip install youtube-transcript-api")
    sys.exit(1)

try:
    import yt_dlp
except ImportError:
    print("警告: 未安装 yt-dlp 库，部分功能可能受限")
    print("建议运行: pip install yt-dlp")
    yt_dlp = None


class YouTubeSubtitleDownloader:
    """YouTube 字幕下载器类"""
    
    def __init__(self, output_dir: str = None):
        """
        初始化下载器
        
        Args:
            output_dir: 输出目录，默认为 raw 文件夹
        """
        # 设置日志
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
        # 设置输出目录
        if output_dir:
            self.output_dir = Path(output_dir)
        else:
            # 默认使用项目根目录下的 raw 文件夹
            current_dir = Path(__file__).parent
            project_root = current_dir.parent
            self.output_dir = project_root / "raw"
        
        # 确保输出目录存在
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.logger.info(f"输出目录: {self.output_dir}")
    
    def _sanitize_filename(self, filename: str) -> str:
        """
        清理文件名，移除非法字符
        
        Args:
            filename: 原始文件名
            
        Returns:
            清理后的文件名
        """
        import re
        
        # 移除 Windows 文件名非法字符: < > : " / \ | ? *
        illegal_chars = r'[<>:"/\\|?*]'
        cleaned = re.sub(illegal_chars, '_', filename)
        
        # 移除控制字符和多余空格
        cleaned = re.sub(r'[\x00-\x1f\x7f]', '', cleaned)
        cleaned = ' '.join(cleaned.split())
        
        # 限制文件名长度（保留足够空间给语言后缀）
        max_length = 200
        if len(cleaned) > max_length:
            cleaned = cleaned[:max_length].rstrip()
        
        return cleaned
    
    def extract_video_id(self, url: str) -> Optional[str]:
        """
        从 YouTube URL 中提取视频 ID
        
        Args:
            url: YouTube 视频 URL
            
        Returns:
            视频 ID，如果提取失败则返回 None
        """
        import re
        
        # 支持多种 YouTube URL 格式
        patterns = [
            r'(?:youtube\.com\/watch\?v=|youtu\.be\/)([^&\n?#]+)',
            r'youtube\.com\/embed\/([^&\n?#]+)',
            r'youtube\.com\/v\/([^&\n?#]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        # 如果不是 URL，可能直接是视频 ID
        if re.match(r'^[a-zA-Z0-9_-]{11}$', url):
            return url
        
        return None
    
    def get_video_info(self, video_id: str) -> dict:
        """
        获取视频信息（需要 yt-dlp）
        
        Args:
            video_id: YouTube 视频 ID
            
        Returns:
            视频信息字典
        """
        if not yt_dlp:
            return {"title": video_id}
        
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': True
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
                return {
                    "title": info.get('title', video_id),
                    "duration": info.get('duration', 0),
                    "uploader": info.get('uploader', 'Unknown')
                }
        except Exception as e:
            self.logger.warning(f"获取视频信息失败: {e}")
            return {"title": video_id}
    
    def get_available_transcripts(self, video_id: str) -> List[dict]:
        """
        获取可用的字幕列表
        
        Args:
            video_id: YouTube 视频 ID
            
        Returns:
            可用字幕列表
        """
        try:
            api = YouTubeTranscriptApi()
            transcript_list = api.list(video_id)
            
            available = []
            for transcript in transcript_list:
                available.append({
                    'language': transcript.language,
                    'language_code': transcript.language_code,
                    'is_generated': transcript.is_generated,
                    'is_translatable': len(transcript.translation_languages) > 0
                })
            
            return available
        except Exception as e:
            self.logger.error(f"获取字幕列表失败: {e}")
            return []

    def download_subtitle(self, url: str, languages: List[str]) -> List[str]:
        """
        使用 yt-dlp 下载字幕（支持 cookies 绕过验证）
        
        Args:
            url: YouTube 视频 URL
            languages: 语言列表
            
        Returns:
            下载的字幕文件路径列表
        """
        video_id = self.extract_video_id(url)
        if not video_id:
            self.logger.error(f"无法从 URL 提取视频 ID: {url}")
            return []
        
        downloaded_files = []
        
        try:
            self.logger.info(f"正在下载视频 {video_id} 的字幕...")
            
            # 构建语言参数
            lang_str = ','.join(languages)
            
            # 使用 yt-dlp 下载字幕
            ydl_opts = {
                'skip_download': True,  # 不下载视频
                'writesubtitles': True,  # 下载字幕
                'writeautomaticsub': True,  # 也下载自动生成的字幕
                'subtitleslangs': languages,  # 字幕语言
                'subtitlesformat': 'vtt/srt/best',  # 字幕格式
                'outtmpl': str(self.output_dir / '%(title)s.%(ext)s'),
                'quiet': False,
                'no_warnings': False,
                # 使用 cookies 文件绕过验证
                'cookiefile': str(Path(__file__).parent / 'cookies.txt'),
            }
            
            # 检查 cookies 文件是否存在
            cookies_path = Path(__file__).parent / 'cookies.txt'
            if not cookies_path.exists():
                self.logger.warning(f"未找到 cookies.txt 文件，尝试从浏览器获取...")
                # 尝试从 Edge 浏览器获取 cookies
                ydl_opts.pop('cookiefile')
                ydl_opts['cookiesfrombrowser'] = ('edge',)
            
            video_url = f"https://www.youtube.com/watch?v={video_id}"
            
            # 记录下载前的文件列表
            existing_files = set(self.output_dir.glob('*.*'))
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=True)
                video_title = info.get('title', video_id)
                safe_title = self._sanitize_filename(video_title)
                
                # 查找新下载的字幕文件
                new_files = set(self.output_dir.glob('*.*')) - existing_files
                
                for lang in languages:
                    # 查找匹配语言的字幕文件
                    for new_file in new_files:
                        if f'.{lang}.' in new_file.name and new_file.suffix in ['.vtt', '.srt']:
                            # 读取字幕并转换为纯文本
                            txt_content = self._extract_text_from_subtitle(new_file)
                            
                            # 保存为 TXT 文件
                            txt_filename = f"{safe_title}_{lang}.txt"
                            txt_path = self.output_dir / txt_filename
                            
                            with open(txt_path, 'w', encoding='utf-8') as f:
                                f.write(txt_content)
                            
                            self.logger.info(f"✓ 下载成功: {txt_filename}")
                            downloaded_files.append(str(txt_path))
                            
                            # 删除原始字幕文件
                            new_file.unlink()
                            break
            
            if not downloaded_files:
                self.logger.warning("未能下载任何字幕文件")
        
        except Exception as e:
            self.logger.error(f"字幕下载失败: {e}")
            import traceback
            self.logger.debug(traceback.format_exc())
        
        return downloaded_files
    
    def _extract_text_from_subtitle(self, subtitle_path: Path) -> str:
        """
        从 VTT/SRT 字幕文件中提取纯文本
        
        Args:
            subtitle_path: 字幕文件路径
            
        Returns:
            纯文本内容
        """
        import re
        
        with open(subtitle_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 移除 VTT 头部
        content = re.sub(r'^WEBVTT\n.*?\n\n', '', content, flags=re.DOTALL)
        
        # 移除时间戳行 (00:00:00.000 --> 00:00:00.000)
        content = re.sub(r'\d{2}:\d{2}:\d{2}[.,]\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}[.,]\d{3}.*?\n', '', content)
        
        # 移除 SRT 序号行
        content = re.sub(r'^\d+\n', '', content, flags=re.MULTILINE)
        
        # 移除 VTT 标签 (如 <c>, </c>, <00:00:00.000> 等)
        content = re.sub(r'<[^>]+>', '', content)
        
        # 移除空行并合并
        lines = [line.strip() for line in content.split('\n') if line.strip()]
        
        # 去除重复的连续行
        unique_lines = []
        for line in lines:
            if not unique_lines or line != unique_lines[-1]:
                unique_lines.append(line)
        
        return '\n'.join(unique_lines)
    
def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(
        description='YouTube 字幕下载器',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 下载英文字幕
  python downloader.py "https://www.youtube.com/watch?v=VIDEO_ID"
  
  # 下载指定语言字幕
  python downloader.py "https://www.youtube.com/watch?v=VIDEO_ID" --languages en zh-CN
  
  # 指定输出目录
  python downloader.py "VIDEO_ID" --output ./subtitles
  
  # 优先下载自动生成的字幕
  python downloader.py "VIDEO_ID" --auto-generated
        """
    )
    
    parser.add_argument(
        'url',
        help='YouTube 视频 URL 或视频 ID'
    )
    
    parser.add_argument(
        '--languages', '-l',
        nargs='+',
        default=['en', 'zh-CN', 'zh-TW'],
        help='要下载的字幕语言代码 (默认: en zh-CN zh-TW)'
    )
    
    parser.add_argument(
        '--output', '-o',
        help='输出目录 (默认: ../raw)'
    )
    
    parser.add_argument(
        '--auto-generated', '-a',
        action='store_true',
        help='优先下载自动生成的字幕（默认优先手动上传的字幕）'
    )
    
    args = parser.parse_args()
    
    # 创建下载器
    downloader = YouTubeSubtitleDownloader(output_dir=args.output)
    
    print(downloader.get_available_transcripts(downloader.extract_video_id(args.url)))

    # 下载字幕
    downloaded = downloader.download_subtitle(
        args.url,
        languages=args.languages
    )
    
    if downloaded:
        print(f"\n成功下载 {len(downloaded)} 个字幕文件:")
        for file in downloaded:
            print(f"  - {file}")
    else:
        print("\n未能下载任何字幕文件")
        sys.exit(1)


if __name__ == '__main__':
    main()
