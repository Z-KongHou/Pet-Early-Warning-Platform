package com.hamster.yingshi.controller;

import com.hamster.yingshi.common.Result;
import com.hamster.yingshi.dto.BindCameraRequest;
import com.hamster.yingshi.entity.Camera;
import com.hamster.yingshi.service.CameraService;
import com.hamster.yingshi.service.UserCameraService;
import com.hamster.yingshi.utils.SecurityUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

@RestController
@RequestMapping("/api/users/me/cameras")
public class UserCameraController {

    @Autowired
    private UserCameraService userCameraService;

    @Autowired
    private CameraService cameraService;

    @Autowired
    private SecurityUtils securityUtils;

    @PostMapping("/bind")
    public Result<Void> bind(@RequestBody BindCameraRequest request) {
        Integer userId = securityUtils.getCurrentUserId();
        userCameraService.bind(userId, request.getCameraId());
        return Result.success();
    }

    @PostMapping("/unbind")
    public Result<Void> unbind(@RequestBody BindCameraRequest request) {
        Integer userId = securityUtils.getCurrentUserId();
        userCameraService.unbind(userId, request.getCameraId());
        return Result.success();
    }

    @GetMapping
    public Result<Map<String, Object>> list() {
        Integer userId = securityUtils.getCurrentUserId();
        List<Camera> cameras = cameraService.findByUserId(userId);
        List<Map<String, Object>> list = cameras.stream().map(camera -> {
            Map<String, Object> item = new java.util.HashMap<>();
            item.put("cameraId", camera.getId());
            item.put("name", camera.getName());
            item.put("onlineStatus", camera.getOnlineStatus());
            return item;
        }).collect(Collectors.toList());
        Map<String, Object> data = new java.util.HashMap<>();
        data.put("list", list);
        data.put("total", list.size());
        return Result.success(data);
    }
}