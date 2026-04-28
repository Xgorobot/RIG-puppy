#!/usr/bin/env python3
"""
EAF (Emote Animation Format) Viewer
A GUI tool to view and play EAF animation files.

EAF File Format:
- Offset 0, 1 byte: Magic number (0x89)
- Offset 1, 3 bytes: Format string ("EAF")
- Offset 4, 4 bytes: Total number of frames
- Offset 8, 4 bytes: Checksum
- Offset 12, 4 bytes: Length of table + data
- Offset 16, N bytes: Frame table (N = total_frames * 8)
- Frame data follows

Each frame entry: 4 bytes size + 4 bytes offset
"""

import struct
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
import io
import os
import time
import threading

# EAF Constants
EAF_FORMAT_MAGIC = 0x89
EAF_MAGIC_HEAD = 0x5A5A


class EAFFrame:
    """Represents a single frame in the EAF file"""
    def __init__(self):
        self.format = ""
        self.version = ""
        self.bit_depth = 0
        self.width = 0
        self.height = 0
        self.blocks = 0
        self.block_height = 0
        self.block_lengths = []
        self.data_offset = 0
        self.palette = []
        self.raw_data = b''
        self.image = None


class EAFParser:
    """Parser for EAF animation files"""
    
    def __init__(self):
        self.total_frames = 0
        self.checksum = 0
        self.data_length = 0
        self.frames = []
        self.file_data = None
        
    def load(self, filepath):
        """Load and parse an EAF file"""
        with open(filepath, 'rb') as f:
            self.file_data = f.read()
        
        return self._parse()
    
    def _parse(self):
        """Parse the EAF file header and frame table"""
        data = self.file_data
        
        # Check magic number
        if len(data) < 16:
            raise ValueError("File too small to be EAF")
        
        magic = data[0]
        format_str = data[1:4].decode('ascii', errors='ignore')
        
        if magic != EAF_FORMAT_MAGIC or format_str not in ('EAF', 'AAF'):
            raise ValueError(f"Invalid EAF magic: 0x{magic:02X} '{format_str}'")
        
        # Parse header
        self.total_frames = struct.unpack('<I', data[4:8])[0]
        self.checksum = struct.unpack('<I', data[8:12])[0]
        self.data_length = struct.unpack('<I', data[12:16])[0]
        
        # Parse frame table
        table_offset = 16
        self.frames = []
        
        # Frame data starts after the frame table
        frame_data_base = table_offset + self.total_frames * 8
        
        for i in range(self.total_frames):
            entry_offset = table_offset + i * 8
            frame_size = struct.unpack('<I', data[entry_offset:entry_offset+4])[0]
            frame_offset_rel = struct.unpack('<I', data[entry_offset+4:entry_offset+8])[0]
            
            # Absolute offset = frame_data_base + relative offset from table
            absolute_offset = frame_data_base + frame_offset_rel
            
            # Parse frame data
            frame = self._parse_frame(absolute_offset, frame_size)
            if frame:
                self.frames.append(frame)
        
        return True
    
    def _parse_frame(self, offset, size):
        """Parse a single frame from the file"""
        data = self.file_data
        
        if offset + size > len(data):
            return None
        
        frame_data = data[offset:offset + size]
        
        # Check for magic head (0x5A5A)
        if len(frame_data) >= 2:
            head = struct.unpack('<H', frame_data[0:2])[0]
            if head == EAF_MAGIC_HEAD:
                frame_data = frame_data[2:]  # Skip magic head
        
        frame = EAFFrame()
        frame.raw_data = frame_data
        
        # Parse frame header (based on ESP source code)
        if len(frame_data) < 18:
            return None
        
        try:
            # Format: 2 bytes at offset 0-1 (e.g., "_S")
            frame.format = frame_data[0:2].decode('ascii', errors='ignore')
            
            # Check if valid format
            if frame.format not in ('_S', '_C'):
                print(f"Unknown format: {frame.format}")
                return None
            
            if frame.format == '_C':  # Redirect format
                return None
            
            # Version: 6 bytes at offset 3-8 (note: offset 2 is skipped)
            frame.version = frame_data[3:9].decode('ascii', errors='ignore')
            
            # Bit depth: 1 byte at offset 9
            frame.bit_depth = frame_data[9]
            
            # Width: 2 bytes at offset 10
            frame.width = struct.unpack('<H', frame_data[10:12])[0]
            
            # Height: 2 bytes at offset 12
            frame.height = struct.unpack('<H', frame_data[12:14])[0]
            
            # Blocks: 2 bytes at offset 14
            frame.blocks = struct.unpack('<H', frame_data[14:16])[0]
            
            # Block height: 2 bytes at offset 16
            frame.block_height = struct.unpack('<H', frame_data[16:18])[0]
            
            # Block lengths: blocks * 4 bytes starting at offset 18
            block_len_offset = 18
            frame.block_lengths = []
            for i in range(frame.blocks):
                if block_len_offset + 4 <= len(frame_data):
                    bl = struct.unpack('<I', frame_data[block_len_offset:block_len_offset+4])[0]
                    frame.block_lengths.append(bl)
                    block_len_offset += 4
            
            # Parse palette if needed (4 bytes per color: RGBX format)
            if frame.bit_depth in (4, 8):
                num_colors = 1 << frame.bit_depth  # 16 or 256
                palette_size = num_colors * 4  # 4 bytes per color
                palette_offset = block_len_offset
                if palette_offset + palette_size <= len(frame_data):
                    frame.palette = self._parse_palette_rgba(frame_data[palette_offset:palette_offset + palette_size], num_colors)
                frame.data_offset = palette_offset + palette_size
            else:
                # 24-bit: no palette
                frame.data_offset = block_len_offset
            
            # Decode frame to image
            frame.image = self._decode_frame_to_image(frame)
            
        except Exception as e:
            print(f"Error parsing frame: {e}")
            import traceback
            traceback.print_exc()
            return None
        
        return frame
    
    def _parse_palette_rgba(self, palette_data, num_colors):
        """Parse RGBA palette (4 bytes per color) to RGB tuples"""
        palette = []
        for i in range(num_colors):
            if i * 4 + 4 <= len(palette_data):
                r = palette_data[i * 4 + 0]
                g = palette_data[i * 4 + 1]
                b = palette_data[i * 4 + 2]
                # byte 3 is alpha/padding, ignored
                palette.append((r, g, b))
        return palette
    
    def _decode_frame_to_image(self, frame):
        """Decode frame data to PIL Image"""
        if frame.width == 0 or frame.height == 0:
            return None
        
        # Create a placeholder image
        img = Image.new('RGB', (frame.width, frame.height), (30, 30, 50))
        
        try:
            # Decode each block
            all_pixels = []
            block_data_offset = frame.data_offset
            
            for block_idx in range(frame.blocks):
                if block_idx >= len(frame.block_lengths):
                    break
                    
                block_len = frame.block_lengths[block_idx]
                if block_data_offset + block_len > len(frame.raw_data):
                    break
                
                block_data = frame.raw_data[block_data_offset:block_data_offset + block_len]
                block_data_offset += block_len
                
                if len(block_data) < 1:
                    continue
                
                # First byte is encoding type
                encoding_type = block_data[0]
                compressed_data = block_data[1:]
                
                # Decode block based on encoding type
                if encoding_type == 0:  # RLE
                    decoded = self._decode_rle(compressed_data)
                else:
                    # For other encodings (Huffman, JPEG), use raw data as fallback
                    decoded = compressed_data
                
                # Convert decoded data to pixels using palette
                if frame.bit_depth in (4, 8) and frame.palette:
                    for byte in decoded:
                        if frame.bit_depth == 4:
                            idx1 = (byte >> 4) & 0x0F
                            idx2 = byte & 0x0F
                            all_pixels.append(frame.palette[idx1] if idx1 < len(frame.palette) else (0, 0, 0))
                            all_pixels.append(frame.palette[idx2] if idx2 < len(frame.palette) else (0, 0, 0))
                        else:
                            idx = byte
                            all_pixels.append(frame.palette[idx] if idx < len(frame.palette) else (0, 0, 0))
                elif frame.bit_depth == 24:
                    # RGB565 format
                    for i in range(0, len(decoded) - 1, 2):
                        rgb565 = struct.unpack('<H', bytes(decoded[i:i+2]))[0]
                        r = ((rgb565 >> 11) & 0x1F) << 3
                        g = ((rgb565 >> 5) & 0x3F) << 2
                        b = (rgb565 & 0x1F) << 3
                        all_pixels.append((r, g, b))
            
            # Create image from pixels
            expected_pixels = frame.width * frame.height
            if len(all_pixels) >= expected_pixels:
                all_pixels = all_pixels[:expected_pixels]
                img = Image.new('RGB', (frame.width, frame.height))
                img.putdata(all_pixels)
            else:
                print(f"Not enough pixels: got {len(all_pixels)}, expected {expected_pixels}")
                
        except Exception as e:
            print(f"Decode error: {e}")
            import traceback
            traceback.print_exc()
        
        return img
    
    def _decode_rle(self, data):
        """Decode RLE compressed data"""
        result = bytearray()
        i = 0
        while i < len(data):
            if i + 1 >= len(data):
                break
            count = data[i]
            value = data[i + 1]
            
            if count == 0:
                # Literal run
                if i + 2 >= len(data):
                    break
                literal_count = data[i + 1]
                i += 2
                for j in range(literal_count):
                    if i < len(data):
                        result.append(data[i])
                        i += 1
            else:
                # Repeat run
                result.extend([value] * count)
                i += 2
        
        return result


class EAFViewer(tk.Tk):
    """Main GUI application for viewing EAF files"""
    
    def __init__(self):
        super().__init__()
        
        self.title("EAF Viewer - 表情动画查看器")
        self.geometry("800x600")
        self.configure(bg='#2b2b2b')
        
        self.parser = None
        self.current_frame = 0
        self.playing = False
        self.play_thread = None
        self.fps = 20
        self._updating_slider = False  # Prevent recursion
        
        self._setup_ui()
        
    def _setup_ui(self):
        """Setup the user interface"""
        # Style
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TButton', padding=5)
        style.configure('TLabel', background='#2b2b2b', foreground='white')
        style.configure('TFrame', background='#2b2b2b')
        
        # Top toolbar
        toolbar = ttk.Frame(self)
        toolbar.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(toolbar, text="打开 EAF", command=self._open_file).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="播放/暂停", command=self._toggle_play).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="上一帧", command=self._prev_frame).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="下一帧", command=self._next_frame).pack(side=tk.LEFT, padx=2)
        
        # FPS control
        ttk.Label(toolbar, text="  FPS:").pack(side=tk.LEFT, padx=2)
        self.fps_var = tk.StringVar(value="20")
        fps_entry = ttk.Entry(toolbar, textvariable=self.fps_var, width=5)
        fps_entry.pack(side=tk.LEFT, padx=2)
        fps_entry.bind('<Return>', self._update_fps)
        
        # Main content area
        content = ttk.Frame(self)
        content.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Left panel - Image display
        left_panel = ttk.Frame(content)
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.canvas = tk.Canvas(left_panel, bg='#1a1a1a', highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # Right panel - Info
        right_panel = ttk.Frame(content, width=250)
        right_panel.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))
        right_panel.pack_propagate(False)
        
        # Info text
        info_label = ttk.Label(right_panel, text="文件信息", font=('Arial', 12, 'bold'))
        info_label.pack(pady=5)
        
        self.info_text = tk.Text(right_panel, bg='#1a1a1a', fg='#00ff00', 
                                  font=('Consolas', 10), wrap=tk.WORD, height=20)
        self.info_text.pack(fill=tk.BOTH, expand=True)
        
        # Bottom status bar
        status_frame = ttk.Frame(self)
        status_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.status_label = ttk.Label(status_frame, text="请打开 EAF 文件")
        self.status_label.pack(side=tk.LEFT)
        
        self.frame_label = ttk.Label(status_frame, text="")
        self.frame_label.pack(side=tk.RIGHT)
        
        # Frame slider
        self.frame_slider = ttk.Scale(status_frame, from_=0, to=0, orient=tk.HORIZONTAL,
                                       command=self._on_slider_change)
        self.frame_slider.pack(fill=tk.X, expand=True, padx=10)
        
    def _open_file(self):
        """Open an EAF file"""
        filepath = filedialog.askopenfilename(
            title="选择 EAF 文件",
            filetypes=[("EAF Files", "*.eaf"), ("AAF Files", "*.aaf"), ("All Files", "*.*")]
        )
        
        if filepath:
            try:
                self.parser = EAFParser()
                self.parser.load(filepath)
                
                self.current_frame = 0
                self.frame_slider.configure(to=max(0, len(self.parser.frames) - 1))
                
                self._update_info(filepath)
                self._display_frame(0)
                
                self.status_label.config(text=f"已加载: {os.path.basename(filepath)}")
                
            except Exception as e:
                messagebox.showerror("错误", f"无法加载文件:\n{e}")
    
    def _update_info(self, filepath):
        """Update the info panel"""
        self.info_text.delete(1.0, tk.END)
        
        info = f"""文件: {os.path.basename(filepath)}
大小: {os.path.getsize(filepath)} bytes

帧数: {self.parser.total_frames}
校验和: 0x{self.parser.checksum:08X}
数据长度: {self.parser.data_length}

"""
        
        if self.parser.frames:
            frame = self.parser.frames[0]
            info += f"""第一帧信息:
  格式: {frame.format}
  版本: {frame.version}
  位深: {frame.bit_depth}
  尺寸: {frame.width} x {frame.height}
  块数: {frame.blocks}
  块高: {frame.block_height}
"""
        
        self.info_text.insert(tk.END, info)
    
    def _display_frame(self, index):
        """Display a specific frame"""
        if not self.parser or not self.parser.frames:
            return
        
        if index < 0 or index >= len(self.parser.frames):
            return
        
        self.current_frame = index
        frame = self.parser.frames[index]
        
        if frame.image:
            # Scale image to fit canvas
            canvas_w = self.canvas.winfo_width()
            canvas_h = self.canvas.winfo_height()
            
            if canvas_w > 1 and canvas_h > 1:
                scale = min(canvas_w / frame.width, canvas_h / frame.height, 2.0)
                new_w = int(frame.width * scale)
                new_h = int(frame.height * scale)
                
                img_resized = frame.image.resize((new_w, new_h), Image.Resampling.NEAREST)
                self.photo = ImageTk.PhotoImage(img_resized)
                
                self.canvas.delete("all")
                x = canvas_w // 2
                y = canvas_h // 2
                self.canvas.create_image(x, y, image=self.photo, anchor=tk.CENTER)
        
        self.frame_label.config(text=f"帧: {index + 1} / {len(self.parser.frames)}")
        
        # Update slider without triggering callback
        self._updating_slider = True
        self.frame_slider.set(index)
        self._updating_slider = False
    
    def _toggle_play(self):
        """Toggle play/pause"""
        if not self.parser or not self.parser.frames:
            return
        
        self.playing = not self.playing
        
        if self.playing:
            self.play_thread = threading.Thread(target=self._play_loop, daemon=True)
            self.play_thread.start()
    
    def _play_loop(self):
        """Animation playback loop"""
        while self.playing:
            self.current_frame = (self.current_frame + 1) % len(self.parser.frames)
            self.after(0, lambda: self._display_frame(self.current_frame))
            time.sleep(1.0 / self.fps)
    
    def _prev_frame(self):
        """Go to previous frame"""
        if self.parser and self.parser.frames:
            self._display_frame((self.current_frame - 1) % len(self.parser.frames))
    
    def _next_frame(self):
        """Go to next frame"""
        if self.parser and self.parser.frames:
            self._display_frame((self.current_frame + 1) % len(self.parser.frames))
    
    def _on_slider_change(self, value):
        """Handle slider change"""
        if self._updating_slider:
            return
        if self.parser and self.parser.frames:
            self._display_frame(int(float(value)))
    
    def _update_fps(self, event=None):
        """Update FPS from entry"""
        try:
            self.fps = max(1, min(60, int(self.fps_var.get())))
            self.fps_var.set(str(self.fps))
        except ValueError:
            self.fps_var.set("20")
            self.fps = 20


def main():
    app = EAFViewer()
    app.mainloop()


if __name__ == "__main__":
    main()
