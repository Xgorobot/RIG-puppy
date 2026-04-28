#include "imu.h"
#include "config.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "driver/i2c_master.h"
#include "esp_log.h"
#include <cstdio>
#include <cmath>

#define TAG "ICM42670P"

// ---------------------- I2C配置 ----------------------
#define ICM_ADDR        0x69
#define I2C_FREQ_HZ     400000

// ---------------------- 寄存器 ----------------------
#define REG_WHO_AM_I        0x75
#define REG_BANK_SEL        0x76
#define REG_PWR_MGMT0       0x1F
#define REG_GYRO_CONFIG0    0x4F
#define REG_ACCEL_CONFIG0   0x50
#define REG_INT_STATUS      0x2D
#define REG_ACCEL_DATA_X1_H 0x0B

#define WHOAMI_EXPECTED     0x67

// ---------------------- 状态 ----------------------
static i2c_master_bus_handle_t bus_handle = nullptr;
static i2c_master_dev_handle_t dev_handle = nullptr;
static bool imu_initialized = false;

// 导出的姿态数据
float roll = 0.0f;
float pitch = 0.0f;
float yaw = 0.0f;
float accel_x = 0.0f;
float accel_y = 0.0f;
float accel_z = 0.0f;

bool imu_is_initialized() {
    return imu_initialized;
}

// ---------------------- 内部函数 ----------------------
static esp_err_t write_reg(uint8_t reg, uint8_t val) {
    if (!dev_handle) return ESP_ERR_INVALID_STATE;
    uint8_t data[2] = {reg, val};
    return i2c_master_transmit(dev_handle, data, 2, pdMS_TO_TICKS(50));
}

static esp_err_t read_regs(uint8_t reg, uint8_t *buf, size_t len) {
    if (!dev_handle) return ESP_ERR_INVALID_STATE;
    return i2c_master_transmit_receive(dev_handle, &reg, 1, buf, len, pdMS_TO_TICKS(50));
}

// ---------------------- 初始化 ----------------------
void imu_init() {
    if (imu_initialized) {
        ESP_LOGW(TAG, "IMU already initialized");
        return;
    }
    
    ESP_LOGI(TAG, "Initializing IMU on SDA=%d, SCL=%d", IMU_I2C_SDA, IMU_I2C_SCL);
    
    // 创建I2C总线
    i2c_master_bus_config_t bus_cfg = {
        .i2c_port = I2C_NUM_0,
        .sda_io_num = IMU_I2C_SDA,
        .scl_io_num = IMU_I2C_SCL,
        .clk_source = I2C_CLK_SRC_DEFAULT,
        .glitch_ignore_cnt = 7,
        .intr_priority = 0,
        .trans_queue_depth = 0,
        .flags = {.enable_internal_pullup = true},
    };
    
    esp_err_t ret = i2c_new_master_bus(&bus_cfg, &bus_handle);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to create I2C bus: %s", esp_err_to_name(ret));
        return;
    }

    // 探测IMU
    if (i2c_master_probe(bus_handle, ICM_ADDR, pdMS_TO_TICKS(200)) != ESP_OK) {
        ESP_LOGW(TAG, "IMU not found at 0x%02X", ICM_ADDR);
        i2c_del_master_bus(bus_handle);
        bus_handle = nullptr;
        return;
    }

    // 添加设备
    i2c_device_config_t dev_cfg = {
        .dev_addr_length = I2C_ADDR_BIT_LEN_7,
        .device_address = ICM_ADDR,
        .scl_speed_hz = I2C_FREQ_HZ,
    };
    ret = i2c_master_bus_add_device(bus_handle, &dev_cfg, &dev_handle);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to add device: %s", esp_err_to_name(ret));
        i2c_del_master_bus(bus_handle);
        bus_handle = nullptr;
        return;
    }

    vTaskDelay(pdMS_TO_TICKS(50));

    // 验证 WHO_AM_I
    uint8_t id = 0;
    ret = read_regs(REG_WHO_AM_I, &id, 1);
    if (ret != ESP_OK || id != WHOAMI_EXPECTED) {
        ESP_LOGE(TAG, "WHO_AM_I=0x%02X (expected 0x%02X)", id, WHOAMI_EXPECTED);
        i2c_master_bus_rm_device(dev_handle);
        i2c_del_master_bus(bus_handle);
        dev_handle = nullptr;
        bus_handle = nullptr;
        return;
    }

    // 配置传感器
    write_reg(REG_BANK_SEL, 0x00);
    vTaskDelay(pdMS_TO_TICKS(10));
    write_reg(REG_PWR_MGMT0, 0x0F);  // 唤醒
    vTaskDelay(pdMS_TO_TICKS(50));
    write_reg(REG_GYRO_CONFIG0, 0x06);   // ±2000dps
    write_reg(REG_ACCEL_CONFIG0, 0x06);  // ±8g

    imu_initialized = true;
    ESP_LOGI(TAG, "IMU initialized successfully");
}

// ---------------------- 读取数据 ----------------------
void imu_read_once() {
    if (!imu_initialized || !dev_handle) {
        return;
    }

    uint8_t raw[12] = {0};
    if (read_regs(REG_ACCEL_DATA_X1_H, raw, 12) != ESP_OK) {
        return;
    }

    // 解析加速度 (大端序)
    int16_t ax = (int16_t)((raw[0] << 8) | raw[1]);
    int16_t ay = (int16_t)((raw[2] << 8) | raw[3]);
    int16_t az = (int16_t)((raw[4] << 8) | raw[5]);
    
    // 转换为 m/s^2 (±8g 量程)
    accel_x = ax / 32768.0f * 9.80665f * 8.0f;
    accel_y = ay / 32768.0f * 9.80665f * 8.0f;
    accel_z = az / 32768.0f * 9.80665f * 8.0f;
    
    // 计算姿态角
    pitch = atan2f(accel_y, accel_z) * 180.0f / 3.14159f;
    roll = atan2f(accel_x, accel_z) * 180.0f / 3.14159f;
}

// ---------------------- 清理 ----------------------
void imu_deinit() {
    if (dev_handle) {
        i2c_master_bus_rm_device(dev_handle);
        dev_handle = nullptr;
    }
    if (bus_handle) {
        i2c_del_master_bus(bus_handle);
        bus_handle = nullptr;
    }
    imu_initialized = false;
    ESP_LOGI(TAG, "IMU deinitialized");
}
