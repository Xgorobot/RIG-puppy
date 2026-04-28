# RIG-Puppy

基于 ESP32-S3 的智能机器狗固件，集成语音交互、表情显示、舵机控制等功能。

## 功能特性

### 语音交互
- **离线唤醒词**：支持自定义唤醒词（基于 ESP-SR）
- **语音识别**：云端 ASR 语音转文字
- **语音合成**：云端 TTS 文字转语音
- **VAD 检测**：自动检测语音起止
- **AGC 增益**：自动增益控制，提升远场拾音效果

### 表情显示
- **EAF 动画**：流畅的表情动画播放（基于 LVGL）
- **多种表情**：neutral、happy、sad、thinking、listen 等 20+ 种表情
- **状态表情**：calibration（标定）、wificonfig（配网）、connecting 等

### 运动控制
- **5 舵机控制**：头部左右、头部上下、尾巴等
- **舵机标定**：三击按键进入/退出标定模式
- **预设动作**：坐下、起身、摇尾巴、开心等
- **IMU 姿态**：头部跟随设备倾斜

### 网络功能
- **BluFi 配网**：蓝牙辅助 WiFi 配网（小程序）
- **OTA 升级**：支持远程固件更新
- **设备激活**：HMAC 硬件签名激活机制
- **MCP 协议**：支持 MCP 工具扩展

### 外设支持
- **摄像头**：OV2640 图像采集
- **激光**：启动指示灯
- **按键**：单击、长按、三连击多功能

## 硬件要求

| 组件 | 规格 |
|------|------|
| MCU | ESP32-S3 (N16R8) |
| Flash | 16MB |
| PSRAM | 8MB (Octal) |
| 显示屏 | GC9A01 圆屏 240x240 |
| 舵机 | 5x 总线舵机 |
| 麦克风 | I2S 数字麦克风 |
| 扬声器 | I2S DAC + 功放 |
| 摄像头 | OV2640 (可选) |

## 安装

### 环境准备

1. **安装 ESP-IDF v5.4+**
   ```bash
   # 参考官方文档
   # https://docs.espressif.com/projects/esp-idf/zh_CN/latest/esp32s3/get-started/
   ```

2. **克隆项目**
   ```bash
   git clone https://github.com/your-repo/RIG-Puppy.git
   cd RIG-Puppy
   ```

### 编译烧录

```bash
# 设置目标芯片
idf.py set-target esp32s3

# 配置（可选）
idf.py menuconfig

# 编译
idf.py build

# 烧录（替换 COMx 为实际端口）
idf.py -p COMx flash

# 监视日志
idf.py -p COMx monitor
```

### 单独烧录分区

```bash
# 只烧录应用
idf.py -p COMx app-flash

# 只烧录 assets
esptool.py --chip esp32s3 -p COMx write_flash 0x710000 build/assets.bin
```

## 配置说明

### menuconfig 主要选项

```
Xiaozhi Assistant  --->
    [*] Board Type: LULU ESP32-S3 (XGO Robot Dog)
    [*] Default Language: Chinese (简体中文)
    [*] Flash Assets: Flash Emote Assets
    [*] Use BluFi WiFi Provisioning
```

### 关键配置文件

| 文件 | 说明 |
|------|------|
| `sdkconfig.defaults` | 通用默认配置 |
| `sdkconfig.defaults.esp32s3` | ESP32-S3 特定配置 |
| `partitions/v2/16m.csv` | 分区表 |
| `main/boards/lulu-esp32s3/` | 板级实现 |

## 开发指南

### 项目结构

```
RIG-Puppy/
├── main/
│   ├── application.cc      # 应用主逻辑
│   ├── audio/              # 音频处理
│   │   ├── wake_words/     # 唤醒词
│   │   └── processors/     # 音频前端
│   ├── boards/
│   │   ├── common/         # 通用板级代码
│   │   └── lulu-esp32s3/   # LULU 板级实现
│   ├── display/            # 显示相关
│   │   └── lvgl_display/   # LVGL 显示
│   ├── protocols/          # 通信协议
│   └── assets/             # 资源文件
│       └── locales/        # 多语言资源
├── partitions/             # 分区表
├── scripts/                # 工具脚本
└── docs/                   # 文档
```

### 添加新表情

1. 制作 EAF 动画文件
2. 放入 `main/boards/lulu-esp32s3/240_240/` 目录
3. 编辑 `emote.json` 添加配置：
   ```json
   {"emote": "my_emotion", "src": "my_emotion.eaf", "loop": true, "fps": 30}
   ```
4. 重新编译并烧录 assets 分区

### 添加新语音

1. 准备 OGG 格式音频文件
2. 放入 `main/assets/locales/zh-CN/` 目录
3. 编辑 `main/assets/lang_config.h` 添加声明：
   ```cpp
   extern const char ogg_my_sound_start[] asm("_binary_my_sound_ogg_start");
   extern const char ogg_my_sound_end[] asm("_binary_my_sound_ogg_end");
   static const std::string_view OGG_MY_SOUND {
       static_cast<const char*>(ogg_my_sound_start),
       static_cast<size_t>(ogg_my_sound_end - ogg_my_sound_start)
   };
   ```
4. 运行 `idf.py reconfigure` 后重新编译

### 舵机标定流程

1. **进入标定**：三击按键（1秒内）
2. **调整舵机**：手动将各关节调整到零位
3. **保存退出**：再次三击按键

### 按键功能

| 操作 | 功能 |
|------|------|
| 单击 | 切换对话状态 / 进入配网 |
| 长按 1秒 | 显示 NVS 重置表情 |
| 长按 3秒 | 清除 NVS 并重启 |
| 三连击 | 进入/退出标定模式 |

## 调试

### 常用日志 TAG

```bash
# 过滤特定模块日志
idf.py monitor | grep -E "LULU|XGO|BLUFI|AFE"
```

| TAG | 模块 |
|-----|------|
| `LULUESP32S3` | 板级主代码 |
| `XGO` | 舵机控制 |
| `BLUFI` | 蓝牙配网 |
| `AFE` | 音频前端 |
| `Application` | 应用主逻辑 |

### 常见问题

**Q: WiFi 列表超时？**
A: 已限制最多发送 20 个 AP，按信号强度排序。

**Q: 唤醒响应慢？**
A: 检查 `SetEmotion` 是否在 `EnableVoiceProcessing` 之后调用。

**Q: 舵机抖动？**
A: 检查标定值是否正确，或电源是否稳定。

## 许可证

[MIT License](LICENSE)

## 贡献

欢迎提交 Issue 和 Pull Request！
