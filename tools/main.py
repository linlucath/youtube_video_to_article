#!/usr/bin/env python
"""
主执行脚本
用法: python main.py [youtube_link]
功能: 依次执行 downloader.py, converter.py, formatter.py
"""

import sys
import os
import subprocess
from pathlib import Path
import argparse
import shutil


def run_script(script_name: str, args: list = None) -> bool:
    """
    运行指定的脚本
    
    Args:
        script_name: 脚本名称
        args: 传递给脚本的参数列表
        
    Returns:
        成功返回True，失败返回False
    """
    script_path = Path(__file__).parent / script_name
    
    if not script_path.exists():
        print(f"❌ 错误: 找不到脚本 {script_name}")
        return False
    
    # 构建命令
    cmd = [sys.executable, str(script_path)]
    if args:
        cmd.extend(args)
    
    print(f"\n{'='*60}")
    print(f"🚀 执行: {script_name}")
    print(f"{'='*60}")
    
    try:
        # 执行脚本
        result = subprocess.run(
            cmd,
            check=True,
            text=True,
            encoding='utf-8'
        )
        
        print(f"✅ {script_name} 执行成功")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ {script_name} 执行失败，退出码: {e.returncode}")
        return False
    except Exception as e:
        print(f"❌ 执行 {script_name} 时出错: {e}")
        return False


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='YouTube视频处理工具 - 下载字幕、转换和格式化',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python main.py "https://www.youtube.com/watch?v=VIDEO_ID"
  python main.py "VIDEO_ID"
        """
    )
    
    parser.add_argument(
        '--youtube_link', '-l', 
        help='YouTube 视频链接或视频ID'
    )
    
    parser.add_argument(
        '--languages', '-L',
        nargs='+',
        default=['en'],
        help='要下载的字幕语言 (默认: en)'
    )
    
    args = parser.parse_args()
    
    print("="*60)
    print("🎬 YouTube 视频处理管道")
    print("="*60)
    print(f"📺 视频: {args.youtube_link}")
    print(f"🌐 语言: {', '.join(args.languages)}")
    
    # 步骤1: 下载字幕
    print("\n📥 步骤 1/4: 下载字幕...")
    downloader_args = [args.youtube_link, '--languages'] + args.languages
    if args.youtube_link:
        if not run_script('downloader.py', downloader_args):
            print("\n❌ 管道执行失败: 字幕下载失败")
            sys.exit(1)
    
    # 步骤2: 转换字幕
    print("\n🔄 步骤 2/4: 转换字幕...")
    # converter.py 会自动处理 raw 文件夹中的文件
    # 需要设置 DEEPSEEK_API_KEY 环境变量
    converter_args = ['--input_path', '../raw', '-o', '../processed']
    if not run_script('converter.py', converter_args):
        print("\n❌ 管道执行失败: 字幕转换失败")
        sys.exit(1)
    
    # 步骤3: 格式化输出
    print("\n📝 步骤 3/4: 格式化输出...")
    if not run_script('formatter.py'):
        print("\n❌ 管道执行失败: 格式化失败")
        sys.exit(1)
    
    # 步骤4: 清理临时文件夹
    print("\n🗑️  步骤 4/4: 清理临时文件夹...")
    try:
        raw_dir = Path(__file__).parent.parent / 'raw'
        processed_dir = Path(__file__).parent.parent / 'processed'
        
        if raw_dir.exists():
            shutil.rmtree(raw_dir)
            print(f"  ✅ 已删除: {raw_dir}")
        else:
            print(f"  ⚠️  目录不存在: {raw_dir}")
            
        if processed_dir.exists():
            shutil.rmtree(processed_dir)
            print(f"  ✅ 已删除: {processed_dir}")
        else:
            print(f"  ⚠️  目录不存在: {processed_dir}")
            
        print("✅ 清理完成")
        
    except Exception as e:
        print(f"❌ 清理文件夹时出错: {e}")
        # 不中断流程，继续执行
    
    # 完成
    print("\n" + "="*60)
    print("🎉 所有步骤执行完成!")
    print("="*60)
    print("📂 处理结果:")
    print("  - 最终输出: 博客文件夹")
    print("  - 临时文件已清理")
    print("="*60)


if __name__ == '__main__':
    main()
