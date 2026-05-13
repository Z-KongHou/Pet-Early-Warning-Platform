package com.hamster.yingshi.controller;

import com.hamster.yingshi.common.Result;
import com.hamster.yingshi.dto.HamsterRequest;
import com.hamster.yingshi.entity.Hamster;
import com.hamster.yingshi.service.HamsterService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

@RestController
@RequestMapping("/api/hamsters")
public class HamsterController {

    @Autowired
    private HamsterService hamsterService;

    @PostMapping
    public Result<Hamster> create(@RequestBody HamsterRequest request) {
        Hamster hamster = new Hamster();
        hamster.setName(request.getName());
        hamster.setBreed(request.getBreed());
        hamster.setBirthDate(request.getBirthDate());
        hamster.setGender(request.getGender());
        hamster.setWeight(request.getWeight());
        hamster.setAvatar(request.getAvatar());
        hamster.setRemark(request.getRemark());
        hamster.setHealthStatus(request.getHealthStatus() != null ? request.getHealthStatus() : 0);
        hamster.setIsDeleted(0);
        return Result.success(hamsterService.create(hamster));
    }

    @GetMapping
    public Result<Map<String, Object>> list() {
        List<Hamster> hamsters = hamsterService.findAll();
        List<Map<String, Object>> list = hamsters.stream().map(h -> {
            Map<String, Object> item = new java.util.HashMap<>();
            item.put("id", h.getId());
            item.put("name", h.getName());
            item.put("breed", h.getBreed());
            item.put("healthStatus", h.getHealthStatus());
            item.put("createdAt", h.getCreatedAt());
            return item;
        }).collect(Collectors.toList());
        Map<String, Object> data = new java.util.HashMap<>();
        data.put("list", list);
        data.put("total", list.size());
        return Result.success(data);
    }

    @GetMapping("/{id}")
    public Result<Hamster> getById(@PathVariable Integer id) {
        return Result.success(hamsterService.findById(id));
    }

    @PostMapping("/{id}")
    public Result<Hamster> update(@PathVariable Integer id, @RequestBody HamsterRequest request) {
        Hamster hamster = new Hamster();
        hamster.setName(request.getName());
        hamster.setBreed(request.getBreed());
        hamster.setBirthDate(request.getBirthDate());
        hamster.setGender(request.getGender());
        hamster.setWeight(request.getWeight());
        hamster.setAvatar(request.getAvatar());
        hamster.setRemark(request.getRemark());
        hamster.setHealthStatus(request.getHealthStatus());
        return Result.success(hamsterService.update(id, hamster));
    }

    @DeleteMapping("/{id}")
    public Result<Map<String, Object>> delete(@PathVariable Integer id) {
        hamsterService.delete(id);
        Map<String, Object> data = new java.util.HashMap<>();
        data.put("id", id);
        data.put("isDeleted", 1);
        data.put("deletedAt", java.time.LocalDateTime.now());
        return Result.success(data);
    }
}