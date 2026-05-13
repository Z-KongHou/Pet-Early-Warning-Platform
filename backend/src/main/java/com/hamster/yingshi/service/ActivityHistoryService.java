package com.hamster.yingshi.service;

import com.hamster.yingshi.entity.ActivityHistory;
import com.hamster.yingshi.mapper.ActivityHistoryMapper;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import java.time.LocalDateTime;
import java.util.List;

@Service
public class ActivityHistoryService {

    @Autowired
    private ActivityHistoryMapper activityHistoryMapper;

    public ActivityHistory create(ActivityHistory history) {
        activityHistoryMapper.insert(history);
        return history;
    }

    public Page<ActivityHistory> findPage(Integer page, Integer size, Integer hamsterId, LocalDateTime startDate, LocalDateTime endDate) {
        Page<ActivityHistory> pageParam = new Page<>(page, size);
        LambdaQueryWrapper<ActivityHistory> wrapper = new LambdaQueryWrapper<ActivityHistory>()
            .eq(hamsterId != null, ActivityHistory::getHamsterId, hamsterId)
            .ge(startDate != null, ActivityHistory::getCreatedAt, startDate)
            .le(endDate != null, ActivityHistory::getCreatedAt, endDate)
            .orderByDesc(ActivityHistory::getCreatedAt);
        return activityHistoryMapper.selectPage(pageParam, wrapper);
    }

    public List<ActivityHistory> findByHamsterId(Integer hamsterId, Integer days) {
        LocalDateTime startDate = LocalDateTime.now().minusDays(days);
        return activityHistoryMapper.selectList(
            new LambdaQueryWrapper<ActivityHistory>()
                .eq(ActivityHistory::getHamsterId, hamsterId)
                .ge(ActivityHistory::getCreatedAt, startDate)
                .orderByDesc(ActivityHistory::getCreatedAt)
        );
    }

    public Object getStatistics(Integer hamsterId, String period) {
        return null;
    }

    public Object getTrend(Integer hamsterId, String period, Integer days) {
        return null;
    }
}