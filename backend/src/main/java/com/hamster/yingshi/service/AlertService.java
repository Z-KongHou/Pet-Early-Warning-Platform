package com.hamster.yingshi.service;

import com.hamster.yingshi.entity.Alert;
import com.hamster.yingshi.mapper.AlertMapper;
import com.hamster.yingshi.common.BusinessException;
import com.hamster.yingshi.common.ErrorCode;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import java.time.Duration;
import java.time.LocalDateTime;

@Service
public class AlertService {

    @Autowired
    private AlertMapper alertMapper;

    public Alert create(Alert alert) {
        alertMapper.insert(alert);
        return alert;
    }

    public Alert findById(Integer id) {
        Alert alert = alertMapper.selectOne(
            new LambdaQueryWrapper<Alert>()
                .eq(Alert::getId, id)
                .eq(Alert::getIsDeleted, 0)
        );
        if (alert == null) {
            throw new BusinessException(ErrorCode.ALERT_NOT_FOUND, "Alert not found");
        }
        return alert;
    }

    public Page<Alert> findPage(Integer page, Integer size, Integer hamsterId, Integer status) {
        Page<Alert> pageParam = new Page<>(page, size);
        LambdaQueryWrapper<Alert> wrapper = new LambdaQueryWrapper<Alert>()
            .eq(Alert::getIsDeleted, 0)
            .orderByDesc(Alert::getCreatedAt);
        if (hamsterId != null) {
            wrapper.eq(Alert::getHamsterId, hamsterId);
        }
        if (status != null) {
            wrapper.eq(Alert::getStatus, status);
        }
        return alertMapper.selectPage(pageParam, wrapper);
    }

    public Alert updateStatus(Integer id, Integer status, String handleRemark, Integer handlerId) {
        Alert alert = findById(id);
        alert.setStatus(status);
        if (handleRemark != null) {
            alert.setHandleRemark(handleRemark);
        }
        if (status == 2) {
            alert.setHandledAt(LocalDateTime.now());
        }
        alert.setHandlerId(handlerId);
        alertMapper.updateById(alert);
        return alert;
    }

    /**
     * Check whether an alert with the same (hamsterId, activityStatus) already exists
     * within the given time window. Used for dedup before creating a new alert.
     *
     * @param hamsterId      the hamster to check
     * @param activityStatus the alert status (high / low)
     * @param window         look-back duration from now
     * @return true if a duplicate exists and should be suppressed
     */
    public boolean hasDuplicateWithinWindow(Integer hamsterId, String activityStatus, Duration window) {
        LocalDateTime cutoff = LocalDateTime.now().minus(window);
        Long count = alertMapper.selectCount(
            new LambdaQueryWrapper<Alert>()
                .eq(Alert::getHamsterId, hamsterId)
                .eq(Alert::getActivityStatus, activityStatus)
                .eq(Alert::getIsDeleted, 0)
                .ge(Alert::getCreatedAt, cutoff)
        );
        return count != null && count > 0;
    }

    public void delete(Integer id) {
        Alert alert = findById(id);
        alertMapper.update(null,
            new LambdaUpdateWrapper<Alert>()
                .eq(Alert::getId, id)
                .set(Alert::getIsDeleted, 1)
        );
    }
}