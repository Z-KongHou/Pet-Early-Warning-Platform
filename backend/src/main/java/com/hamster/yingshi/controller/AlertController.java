package com.hamster.yingshi.controller;

import com.hamster.yingshi.common.Result;
import com.hamster.yingshi.dto.AlertRequest;
import com.hamster.yingshi.dto.AlertStatusRequest;
import com.hamster.yingshi.entity.Alert;
import com.hamster.yingshi.service.AlertService;
import com.hamster.yingshi.utils.SecurityUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

@RestController
@RequestMapping("/api/alerts")
public class AlertController {

    @Autowired
    private AlertService alertService;

    @Autowired
    private SecurityUtils securityUtils;

    @PostMapping
    public Result<Alert> create(@RequestBody AlertRequest request) {
        Alert alert = new Alert();
        alert.setHamsterId(request.getHamsterId());
        alert.setActivityStatus(request.getActivityStatus());
        alert.setActivityScore(request.getActivityScore());
        alert.setThreshold(request.getThreshold());
        alert.setImageUrl(request.getImageUrl());
        alert.setStatus(0);
        alert.setIsDeleted(0);
        return Result.success(alertService.create(alert));
    }

    @GetMapping
    public Result<Map<String, Object>> list(
            @RequestParam(required = false) Integer hamsterId,
            @RequestParam(required = false) Integer status,
            @RequestParam(defaultValue = "1") Integer page,
            @RequestParam(defaultValue = "20") Integer size) {
        var pageResult = alertService.findPage(page, size, hamsterId, status);
        List<Map<String, Object>> list = pageResult.getRecords().stream().map(a -> {
            Map<String, Object> item = new java.util.HashMap<>();
            item.put("id", a.getId());
            item.put("hamsterId", a.getHamsterId());
            item.put("activityStatus", a.getActivityStatus());
            item.put("activityScore", a.getActivityScore());
            item.put("threshold", a.getThreshold());
            item.put("status", a.getStatus());
            item.put("createdAt", a.getCreatedAt());
            return item;
        }).collect(Collectors.toList());
        Map<String, Object> data = new java.util.HashMap<>();
        data.put("list", list);
        data.put("total", pageResult.getTotal());
        data.put("page", pageResult.getCurrent());
        data.put("size", pageResult.getSize());
        return Result.success(data);
    }

    @GetMapping("/{id}")
    public Result<Alert> getById(@PathVariable Integer id) {
        return Result.success(alertService.findById(id));
    }

    @PostMapping("/{id}/status")
    public Result<Alert> updateStatus(@PathVariable Integer id, @RequestBody AlertStatusRequest request) {
        Integer handlerId = securityUtils.getCurrentUserId();
        return Result.success(alertService.updateStatus(id, request.getStatus(), request.getHandleRemark(), handlerId));
    }

    @DeleteMapping("/{id}")
    public Result<Void> delete(@PathVariable Integer id) {
        alertService.delete(id);
        return Result.success();
    }
}