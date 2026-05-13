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
            throw new BusinessException(ErrorCode.SETTING_NOT_FOUND, "配置项不存在");
        }
        return setting;
    }

    public List<Setting> findAll() {
        return settingMapper.selectList(
            new LambdaQueryWrapper<Setting>().orderByAsc(Setting::getId)
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
}