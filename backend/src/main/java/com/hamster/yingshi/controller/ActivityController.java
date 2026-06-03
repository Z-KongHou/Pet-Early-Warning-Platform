package com.hamster.yingshi.controller;

import com.hamster.yingshi.common.Result;
import com.hamster.yingshi.entity.ActivityHistory;
import com.hamster.yingshi.service.ActivityHistoryService;
import com.hamster.yingshi.utils.SecurityUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.LocalTime;
import java.util.Map;

@RestController
@RequestMapping("/api/activity")
public class ActivityController {

    @Autowired
    private ActivityHistoryService activityHistoryService;

    @Autowired
    private SecurityUtils securityUtils;

    @GetMapping("/history")
    public Result<Map<String, Object>> history(
            @RequestParam Integer hamsterId,
            @RequestParam(required = false) String startDate,
            @RequestParam(required = false) String endDate,
            @RequestParam(defaultValue = "1") Integer page,
            @RequestParam(defaultValue = "100") Integer size) {
        Integer userId = securityUtils.getCurrentUserId();
        LocalDateTime start = startDate != null ? LocalDate.parse(startDate).atStartOfDay() : null;
        LocalDateTime end = endDate != null ? LocalDate.parse(endDate).atTime(LocalTime.MAX) : null;
        var pageResult = activityHistoryService.findPageByUserId(page, size, userId, hamsterId, start, end);
        Map<String, Object> data = new java.util.HashMap<>();
        data.put("list", pageResult.getRecords());
        data.put("total", pageResult.getTotal());
        data.put("page", pageResult.getCurrent());
        data.put("size", pageResult.getSize());
        return Result.success(data);
    }

    @GetMapping("/statistics")
    public Result<Map<String, Object>> statistics(
            @RequestParam Integer hamsterId,
            @RequestParam(defaultValue = "week") String period) {
        Object stats = activityHistoryService.getStatistics(hamsterId, period);
        Map<String, Object> data = new java.util.HashMap<>();
        data.put("statistics", stats);
        return Result.success(data);
    }

    @GetMapping("/trend")
    public Result<Map<String, Object>> trend(
            @RequestParam Integer hamsterId,
            @RequestParam(defaultValue = "day") String period,
            @RequestParam(defaultValue = "7") Integer days) {
        Object trendData = activityHistoryService.getTrend(hamsterId, period, days);
        Map<String, Object> data = new java.util.HashMap<>();
        data.put("trend", trendData);
        return Result.success(data);
    }
}