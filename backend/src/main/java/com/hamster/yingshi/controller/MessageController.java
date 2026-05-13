package com.hamster.yingshi.controller;

import com.hamster.yingshi.common.Result;
import com.hamster.yingshi.entity.Message;
import com.hamster.yingshi.service.MessageService;
import com.hamster.yingshi.utils.SecurityUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;
import java.util.Map;

@RestController
@RequestMapping("/api/messages")
public class MessageController {

    @Autowired
    private MessageService messageService;

    @Autowired
    private SecurityUtils securityUtils;

    @GetMapping
    public Result<Map<String, Object>> list(
            @RequestParam(defaultValue = "1") Integer page,
            @RequestParam(defaultValue = "20") Integer size,
            @RequestParam(required = false) Integer isRead) {
        Integer userId = securityUtils.getCurrentUserId();
        var pageResult = messageService.findPage(page, size, userId, isRead);
        Map<String, Object> data = new java.util.HashMap<>();
        data.put("list", pageResult.getRecords());
        data.put("total", pageResult.getTotal());
        data.put("page", pageResult.getCurrent());
        data.put("size", pageResult.getSize());
        return Result.success(data);
    }

    @GetMapping("/{id}")
    public Result<Message> getById(@PathVariable Integer id) {
        return Result.success(messageService.findById(id));
    }

    @PostMapping("/{id}/read")
    public Result<Void> markAsRead(@PathVariable Integer id) {
        messageService.markAsRead(id);
        return Result.success();
    }

    @PostMapping("/read-all")
    public Result<Void> markAllAsRead() {
        Integer userId = securityUtils.getCurrentUserId();
        messageService.markAllAsRead(userId);
        return Result.success();
    }

    @DeleteMapping("/{id}")
    public Result<Void> delete(@PathVariable Integer id) {
        messageService.delete(id);
        return Result.success();
    }

    @GetMapping("/unread-count")
    public Result<Map<String, Object>> getUnreadCount() {
        Integer userId = securityUtils.getCurrentUserId();
        Long count = messageService.getUnreadCount(userId);
        Map<String, Object> data = new java.util.HashMap<>();
        data.put("count", count);
        return Result.success(data);
    }
}