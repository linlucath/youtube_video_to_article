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
        使用 YouTube Transcript API 直接下载字幕并保存为 TXT
        
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
            
            # 获取视频信息（标题等）
            video_info = self.get_video_info(video_id)
            video_title = video_info.get('title', video_id)
            
            # 清理文件名中的非法字符
            safe_title = self._sanitize_filename(video_title)
            
            # 创建 API 实例并获取可用字幕列表
            api = YouTubeTranscriptApi()
            transcript_list = api.list(video_id)
            
            # 尝试下载每种语言的字幕
            for lang in languages:
                try:
                    # 准备语言代码列表（包含可能的变体）
                    lang_variants = [lang]
                    if lang == 'zh-CN':
                        lang_variants = ['zh-Hans', 'zh-CN', 'zh']
                    elif lang == 'zh-TW':
                        lang_variants = ['zh-Hant', 'zh-TW']
                    
                    # 尝试获取字幕
                    subtitle_data = None
                    used_lang = None
                    
                    for variant in lang_variants:
                        try:
                            transcript = transcript_list.find_transcript([variant])
                            subtitle_data = transcript.fetch()
                            used_lang = variant
                            self.logger.info(f"找到 {variant} 字幕")
                            break
                        except:
                            continue
                    
                    if subtitle_data:
                        # 提取纯文本（使用 .text 属性而不是字典访问）
                        text_lines = [entry.text for entry in subtitle_data]
                        full_text = '\n'.join(text_lines)
                        
                        # 保存为 TXT 文件，使用视频标题作为文件名
                        txt_filename = f"{safe_title}_{lang}.txt"
                        txt_path = self.output_dir / txt_filename
                        
                        with open(txt_path, 'w', encoding='utf-8') as f:
                            f.write(full_text)
                        
                        self.logger.info(f"✓ 下载成功: {txt_filename}")
                        downloaded_files.append(str(txt_path))
                    else:
                        self.logger.warning(f"未找到 {lang} 字幕")
                        
                except Exception as e:
                    self.logger.warning(f"下载 {lang} 字幕失败: {e}")
                    continue
            
            if not downloaded_files:
                self.logger.warning("未能下载任何字幕文件")
        
        except Exception as e:
            self.logger.error(f"字幕下载失败: {e}")
            import traceback
            self.logger.debug(traceback.format_exc())
        
        return downloaded_files
    
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
