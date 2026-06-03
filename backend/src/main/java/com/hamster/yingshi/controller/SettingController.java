package com.hamster.yingshi.controller;

import com.hamster.yingshi.common.Result;
import com.hamster.yingshi.dto.SettingRequest;
import com.hamster.yingshi.entity.Setting;
import com.hamster.yingshi.service.SettingService;
import com.hamster.yingshi.utils.SecurityUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;
import java.util.List;

@RestController
@RequestMapping("/api/settings")
public class SettingController {

    @Autowired
    private SettingService settingService;

    @Autowired
    private SecurityUtils securityUtils;

    @GetMapping
    public Result<List<Setting>> list() {
        Integer userId = securityUtils.getCurrentUserId();
        return Result.success(settingService.findByUserId(userId));
    }

    @GetMapping("/{keyName}")
    public Result<Setting> getByKeyName(@PathVariable String keyName) {
        return Result.success(settingService.findByKeyName(keyName));
    }

    @PostMapping("/{keyName}")
    public Result<Setting> update(@PathVariable String keyName, @RequestBody SettingRequest request) {
        return Result.success(settingService.update(keyName, request.getKeyValue(), request.getDescription()));
    }
}