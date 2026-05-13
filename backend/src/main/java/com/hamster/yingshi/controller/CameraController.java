package com.hamster.yingshi.controller;

import com.hamster.yingshi.common.Result;
import com.hamster.yingshi.dto.CameraRequest;
import com.hamster.yingshi.dto.CameraTokenRequest;
import com.hamster.yingshi.entity.Camera;
import com.hamster.yingshi.service.CameraService;
import com.hamster.yingshi.service.UserCameraService;
import com.hamster.yingshi.utils.SecurityUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

@RestController
@RequestMapping("/api/cameras")
public class CameraController {

    @Autowired
    private CameraService cameraService;

    @Autowired
    private UserCameraService userCameraService;

    @Autowired
    private SecurityUtils securityUtils;

    @PostMapping
    public Result<Camera> create(@RequestBody CameraRequest request) {
        Integer userId = securityUtils.getCurrentUserId();
        Camera camera = new Camera();
        camera.setHamsterId(request.getHamsterId());
        camera.setName(request.getName());
        camera.setDeviceKey(request.getDeviceKey());
        camera.setChannelNo(request.getChannelNo() != null ? request.getChannelNo() : 1);
        camera.setOnlineStatus(0);
        camera.setIsDeleted(0);
        Camera created = cameraService.create(camera);
        userCameraService.bind(userId, created.getId());
        return Result.success(created);
    }

    @GetMapping
    public Result<Map<String, Object>> list(@RequestParam(required = false) Integer hamsterId) {
        Integer userId = securityUtils.getCurrentUserId();
        List<Camera> cameras;
        if (hamsterId != null) {
            cameras = cameraService.findByHamsterId(hamsterId);
            cameras = cameras.stream()
                .filter(c -> cameraService.hasAccess(userId, c.getId()))
                .collect(Collectors.toList());
        } else {
            cameras = cameraService.findByUserId(userId);
        }
        List<Map<String, Object>> list = cameras.stream().map(c -> {
            Map<String, Object> item = new java.util.HashMap<>();
            item.put("id", c.getId());
            item.put("hamsterId", c.getHamsterId());
            item.put("name", c.getName());
            item.put("deviceKey", c.getDeviceKey());
            item.put("onlineStatus", c.getOnlineStatus());
            item.put("lastOnlineTime", c.getLastOnlineTime());
            return item;
        }).collect(Collectors.toList());
        Map<String, Object> data = new java.util.HashMap<>();
        data.put("list", list);
        data.put("total", list.size());
        return Result.success(data);
    }

    @GetMapping("/{id}")
    public Result<Camera> getById(@PathVariable Integer id) {
        Integer userId = securityUtils.getCurrentUserId();
        cameraService.checkAccess(userId, id);
        return Result.success(cameraService.findById(id));
    }

    @PostMapping("/{id}")
    public Result<Camera> update(@PathVariable Integer id, @RequestBody CameraRequest request) {
        Camera camera = new Camera();
        camera.setName(request.getName());
        camera.setChannelNo(request.getChannelNo());
        camera.setHamsterId(request.getHamsterId());
        return Result.success(cameraService.update(id, camera));
    }

    @DeleteMapping("/{id}")
    public Result<Void> delete(@PathVariable Integer id) {
        cameraService.delete(id);
        return Result.success();
    }

    @GetMapping("/{id}/stream")
    public Result<Map<String, String>> getStream(@PathVariable Integer id) {
        Integer userId = securityUtils.getCurrentUserId();
        cameraService.checkAccess(userId, id);
        Map<String, String> data = new java.util.HashMap<>();
        data.put("streamUrl", "rtsp://placeholder-stream-url");
        return Result.success(data);
    }

    @GetMapping("/{id}/snapshot")
    public Result<Map<String, String>> getSnapshot(@PathVariable Integer id) {
        Integer userId = securityUtils.getCurrentUserId();
        cameraService.checkAccess(userId, id);
        Map<String, String> data = new java.util.HashMap<>();
        data.put("imageUrl", "https://placeholder-snapshot-url");
        return Result.success(data);
    }

    @PostMapping("/{id}/token")
    public Result<Void> updateToken(@PathVariable Integer id, @RequestBody CameraTokenRequest request) {
        LocalDateTime tokenExpires = LocalDateTime.parse(request.getTokenExpires());
        cameraService.updateToken(id, request.getAccessToken(), tokenExpires);
        return Result.success();
    }

    @GetMapping("/{id}/token")
    public Result<Map<String, Object>> getToken(@PathVariable Integer id) {
        Camera camera = cameraService.findById(id);
        Map<String, Object> data = new java.util.HashMap<>();
        data.put("cameraId", camera.getId());
        data.put("tokenExpires", camera.getTokenExpires());
        return Result.success(data);
    }
}