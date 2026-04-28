#!/usr/bin/env python3
"""
提取GIF动画的第一帧，生成静态GIF
用于减小assets表情文件大小

用法:
    python gif_first_frame.py <input_dir> [output_dir]
    
示例:
    python gif_first_frame.py main/boards/lulu-esp32s3/assets
    python gif_first_frame.py main/boards/lulu-esp32s3/assets output_gifs
"""

import os
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("错误: 需要安装 Pillow 库")
    print("请运行: pip install Pillow")
    sys.exit(1)


def extract_first_frame(input_path, output_path):
    """提取GIF的第一帧并保存"""
    try:
        with Image.open(input_path) as img:
            # 确保是GIF格式
            if img.format != 'GIF':
                print(f"  跳过 (非GIF): {input_path}")
                return False
            
            # 获取第一帧
            img.seek(0)
            first_frame = img.copy()
            
            # 获取原始文件大小
            original_size = os.path.getsize(input_path)
            
            # 保存为GIF（保持调色板）
            if first_frame.mode == 'P':
                # 已经是调色板模式
                first_frame.save(output_path, format='GIF')
            elif first_frame.mode == 'RGBA':
                # 转换为调色板模式，保持透明度
                first_frame.save(output_path, format='GIF', transparency=0)
            else:
                # RGB或其他模式
                first_frame = first_frame.convert('P', palette=Image.ADAPTIVE, colors=256)
                first_frame.save(output_path, format='GIF')
            
            # 获取新文件大小
            new_size = os.path.getsize(output_path)
            
            # 计算压缩比
            ratio = (1 - new_size / original_size) * 100
            
            print(f"  ✓ {os.path.basename(input_path)}: {original_size/1024:.1f}KB -> {new_size/1024:.1f}KB ({ratio:.1f}% 减小)")
            return True
            
    except Exception as e:
        print(f"  ✗ 处理失败 {input_path}: {e}")
        return False


def process_directory(input_dir, output_dir=None):
    """处理目录中的所有GIF文件"""
    input_path = Path(input_dir)
    
    if not input_path.exists():
        print(f"错误: 目录不存在: {input_dir}")
        return
    
    # 如果没有指定输出目录，就地修改
    if output_dir is None:
        output_path = input_path
        in_place = True
    else:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        in_place = False
    
    # 查找所有GIF文件
    gif_files = list(input_path.glob("*.gif")) + list(input_path.glob("*.GIF"))
    
    if not gif_files:
        print(f"未找到GIF文件: {input_dir}")
        return
    
    print(f"找到 {len(gif_files)} 个GIF文件")
    print(f"输入目录: {input_path}")
    print(f"输出目录: {output_path}")
    print(f"模式: {'就地修改' if in_place else '输出到新目录'}")
    print("-" * 50)
    
    success_count = 0
    total_original = 0
    total_new = 0
    
    for gif_file in sorted(gif_files):
        original_size = os.path.getsize(gif_file)
        total_original += original_size
        
        if in_place:
            # 就地修改：先保存到临时文件
            temp_file = gif_file.with_suffix('.gif.tmp')
            if extract_first_frame(gif_file, temp_file):
                # 替换原文件
                os.replace(temp_file, gif_file)
                total_new += os.path.getsize(gif_file)
                success_count += 1
            else:
                if temp_file.exists():
                    temp_file.unlink()
        else:
            output_file = output_path / gif_file.name
            if extract_first_frame(gif_file, output_file):
                total_new += os.path.getsize(output_file)
                success_count += 1
    
    print("-" * 50)
    print(f"处理完成: {success_count}/{len(gif_files)} 个文件")
    print(f"总大小: {total_original/1024:.1f}KB -> {total_new/1024:.1f}KB")
    print(f"总共减小: {(total_original - total_new)/1024:.1f}KB ({(1 - total_new/total_original) * 100:.1f}%)")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        print("\n示例目录:")
        print("  main/boards/lulu-esp32s3/assets")
        sys.exit(1)
    
    input_dir = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None
    
    process_directory(input_dir, output_dir)


if __name__ == "__main__":
    main()
