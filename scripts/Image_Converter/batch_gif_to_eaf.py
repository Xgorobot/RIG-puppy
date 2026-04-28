#!/usr/bin/env python3
"""
Batch GIF to EAF Converter
Uses Espressif's online service: https://esp32-gif.espressif.com/

Usage:
    python batch_gif_to_eaf.py <input_dir> [output_dir]
    python batch_gif_to_eaf.py --file <single_file.gif> [output_dir]
"""

import os
import sys
import time
import requests
import argparse
from pathlib import Path


class GifToEafConverter:
    """Converter using Espressif's online GIF to EAF service"""
    
    API_URL = "https://esp32-gif.espressif.com/api/v1/convert"
    
    def __init__(self, bit_depth=8, encoding="rle", debug=False):
        """
        Initialize converter
        
        Args:
            bit_depth: Color depth (4, 8, or 24)
            encoding: Compression method ("rle", "huffman", or "jpeg")
            debug: Print debug information
        """
        self.bit_depth = bit_depth
        self.encoding = encoding
        self.debug = debug
        self.session = requests.Session()
        # Set headers to mimic browser
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': '*/*',
            'Origin': 'https://esp32-gif.espressif.com',
            'Referer': 'https://esp32-gif.espressif.com/',
        })
    
    def convert_file(self, input_path, output_path=None):
        """
        Convert a single GIF file to EAF
        
        Args:
            input_path: Path to input GIF file
            output_path: Path to output EAF file (auto-generated if None)
            
        Returns:
            bool: True if conversion succeeded
        """
        input_path = Path(input_path)
        
        if not input_path.exists():
            print(f"Error: File not found: {input_path}")
            return False
        
        if output_path is None:
            output_path = input_path.with_suffix('.eaf')
        else:
            output_path = Path(output_path)
        
        print(f"Converting: {input_path.name} -> {output_path.name}")
        
        try:
            # Read GIF file
            with open(input_path, 'rb') as f:
                gif_data = f.read()
            
            # POST directly to convert API with GIF data as body
            url = f"{self.API_URL}?filename={input_path.name}"
            
            if self.debug:
                print(f"  POST to: {url}")
                print(f"  Data size: {len(gif_data)} bytes")
            
            response = self.session.post(
                url,
                data=gif_data,
                headers={'Content-Type': 'image/gif'},
                timeout=120
            )
            
            if self.debug:
                print(f"  Status: {response.status_code}")
                print(f"  Content-Type: {response.headers.get('content-type', 'N/A')}")
                print(f"  Content-Length: {len(response.content)} bytes")
            
            if response.status_code == 200 and len(response.content) > 16:
                # Verify it's EAF format (magic byte 0x89)
                if response.content[0] == 0x89:
                    with open(output_path, 'wb') as f:
                        f.write(response.content)
                    
                    file_size = len(response.content)
                    print(f"  Success: {file_size} bytes saved")
                    return True
                else:
                    print(f"  Error: Response is not valid EAF format")
                    if self.debug:
                        print(f"  First bytes: {response.content[:20].hex()}")
                    return False
            else:
                print(f"  Error: HTTP {response.status_code}")
                if self.debug and response.text:
                    print(f"  Response: {response.text[:200]}")
                return False
                
        except requests.exceptions.Timeout:
            print(f"  Error: Request timeout")
            return False
        except requests.exceptions.RequestException as e:
            print(f"  Error: Network error - {e}")
            return False
        except Exception as e:
            print(f"  Error: {e}")
            if self.debug:
                import traceback
                traceback.print_exc()
            return False
    
    def convert_directory(self, input_dir, output_dir=None, recursive=False):
        """
        Convert all GIF files in a directory
        
        Args:
            input_dir: Input directory path
            output_dir: Output directory path (same as input if None)
            recursive: Search subdirectories
            
        Returns:
            tuple: (success_count, total_count)
        """
        input_dir = Path(input_dir)
        
        if not input_dir.is_dir():
            print(f"Error: Not a directory: {input_dir}")
            return 0, 0
        
        if output_dir is None:
            output_dir = input_dir
        else:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
        
        # Find GIF files
        if recursive:
            gif_files = list(input_dir.rglob('*.gif'))
        else:
            gif_files = list(input_dir.glob('*.gif'))
        
        if not gif_files:
            print(f"No GIF files found in {input_dir}")
            return 0, 0
        
        print(f"\nFound {len(gif_files)} GIF file(s)")
        print(f"Settings: bit_depth={self.bit_depth}, encoding={self.encoding}")
        print(f"Output: {output_dir}")
        print("-" * 50)
        
        success_count = 0
        for i, gif_file in enumerate(gif_files, 1):
            print(f"\n[{i}/{len(gif_files)}] ", end="")
            
            # Calculate output path
            if recursive:
                rel_path = gif_file.relative_to(input_dir)
                out_path = output_dir / rel_path.with_suffix('.eaf')
                out_path.parent.mkdir(parents=True, exist_ok=True)
            else:
                out_path = output_dir / gif_file.with_suffix('.eaf').name
            
            if self.convert_file(gif_file, out_path):
                success_count += 1
            
            # Rate limiting to avoid overwhelming the server
            if i < len(gif_files):
                time.sleep(0.5)
        
        print("\n" + "-" * 50)
        print(f"Completed: {success_count}/{len(gif_files)} files converted successfully")
        
        return success_count, len(gif_files)


def main():
    parser = argparse.ArgumentParser(
        description='Batch convert GIF files to EAF format using Espressif online service',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Convert all GIF files in current directory
  python batch_gif_to_eaf.py ./gifs/

  # Convert single file
  python batch_gif_to_eaf.py --file animation.gif

  # Specify output directory
  python batch_gif_to_eaf.py ./gifs/ --output ./eaf_output/

  # Use different settings
  python batch_gif_to_eaf.py ./gifs/ --bit-depth 4 --encoding huffman

Settings:
  bit_depth: 4 (16 colors), 8 (256 colors), 24 (RGB565)
  encoding: rle (default), huffman, jpeg
        """
    )
    
    parser.add_argument('input', nargs='?', help='Input directory containing GIF files')
    parser.add_argument('--file', '-f', help='Single GIF file to convert')
    parser.add_argument('--output', '-o', help='Output directory')
    parser.add_argument('--bit-depth', '-b', type=int, choices=[4, 8, 24], default=8,
                        help='Color bit depth (default: 8)')
    parser.add_argument('--encoding', '-e', choices=['rle', 'huffman', 'jpeg'], default='rle',
                        help='Compression encoding (default: rle)')
    parser.add_argument('--recursive', '-r', action='store_true',
                        help='Search subdirectories recursively')
    parser.add_argument('--debug', '-d', action='store_true',
                        help='Show debug information')
    
    args = parser.parse_args()
    
    if not args.input and not args.file:
        parser.print_help()
        return 1
    
    converter = GifToEafConverter(
        bit_depth=args.bit_depth,
        encoding=args.encoding,
        debug=args.debug
    )
    
    if args.file:
        # Single file mode
        output = args.output
        if output and os.path.isdir(output):
            output = os.path.join(output, Path(args.file).with_suffix('.eaf').name)
        
        success = converter.convert_file(args.file, output)
        return 0 if success else 1
    else:
        # Directory mode
        success, total = converter.convert_directory(
            args.input,
            args.output,
            args.recursive
        )
        return 0 if success == total else 1


if __name__ == '__main__':
    sys.exit(main())
