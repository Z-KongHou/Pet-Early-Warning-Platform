package com.hamster.yingshi.service;

import com.hamster.yingshi.entity.Setting;
import com.hamster.yingshi.mapper.SettingMapper;
import com.hamster.yingshi.common.BusinessException;
import com.hamster.yingshi.common.ErrorCode;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import java.util.List;

@Service
public class SettingService {

    @Autowired
    private SettingMapper settingMapper;

    public Setting findByKeyName(String keyName) {
        Setting setting = settingMapper.selectOne(
            new LambdaQueryWrapper<Setting>().eq(Setting::getKeyName, keyName)
        );
        if (setting == null) {
            throw new BusinessException(ErrorCode.SETTING_NOT_FOUND, "Setting not found");
        }
        return setting;
    }

    public List<Setting> findAll() {
        return settingMapper.selectList(
            new LambdaQueryWrapper<Setting>().orderByAsc(Setting::getId)
        );
    }

    public List<Setting> findByUserId(Integer userId) {
        return settingMapper.selectList(
            new LambdaQueryWrapper<Setting>()
                .eq(Setting::getUserId, userId)
                .orderByAsc(Setting::getId)
        );
    }

    public Setting update(String keyName, String keyValue, String description) {
        Setting setting = findByKeyName(keyName);
        if (keyValue != null) {
            setting.setKeyValue(keyValue);
        }
        if (description != null) {
            setting.setDescription(description);
        }
        settingMapper.updateById(setting);
        return setting;
    }

    /**
     * 为新用户初始化默认配置
     */
    public void initDefaultSettings(Integer userId) {
        // 检查是否已有配置
        List<Setting> existing = findByUserId(userId);
        if (!existing.isEmpty()) {
            return;
        }

        // 创建默认配置项
        createSetting(userId, "activity_interval", "600", "活动检测间隔（秒）");
        createSetting(userId, "low_activity_threshold", "30", "低活跃阈值");
        createSetting(userId, "high_activity_threshold", "80", "高活跃阈值");
        createSetting(userId, "deepseek_api_key", "", "API密钥（敏感数据）");
    }

    private void createSetting(Integer userId, String keyName, String keyValue, String description) {
        Setting setting = new Setting();
        setting.setUserId(userId);
        setting.setKeyName(keyName);
        setting.setKeyValue(keyValue);
        setting.setDescription(description);
        settingMapper.insert(setting);
    }
}