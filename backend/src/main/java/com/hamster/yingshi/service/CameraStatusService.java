package com.hamster.yingshi.service;

import com.hamster.yingshi.entity.Camera;
import com.hamster.yingshi.mapper.CameraMapper;
import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.List;

@Service
public class CameraStatusService {

    private static final Logger log = LoggerFactory.getLogger(CameraStatusService.class);

    @Autowired
    private CameraMapper cameraMapper;

    @Autowired
    private EzvizService ezvizService;

    @Autowired
    private CameraService cameraService;

    /**
     * 每10秒检测一次摄像头在线状态
     */
    @Scheduled(fixedDelay = 10000)
    public void checkAllCamerasStatus() {
        List<Camera> cameras = cameraService.findAll();
        if (cameras.isEmpty()) {
            return;
        }

        log.info("开始检测摄像头在线状态, 共{}个摄像头", cameras.size());

        for (Camera camera : cameras) {
            try {
                checkCameraStatus(camera);
            } catch (Exception e) {
                log.error("检测摄像头 {} 状态失败: {}", camera.getId(), e.getMessage());
            }
        }
    }

    /**
     * 检测单个摄像头的在线状态
     */
    private void checkCameraStatus(Camera camera) {
        boolean online = ezvizService.checkDeviceOnline(camera);
        int newStatus = online ? 1 : 0;

        // 只在状态变化时更新数据库
        Integer currentStatus = camera.getOnlineStatus();
        if (currentStatus == null || currentStatus != newStatus) {
            LambdaUpdateWrapper<Camera> updateWrapper = new LambdaUpdateWrapper<Camera>()
                    .eq(Camera::getId, camera.getId())
                    .set(Camera::getOnlineStatus, newStatus);
            if (online) {
                updateWrapper.set(Camera::getLastOnlineTime, LocalDateTime.now());
            }
            cameraMapper.update(null, updateWrapper);
            log.info("摄像头 {} 状态变更: {} -> {}", camera.getId(),
                    currentStatus == 0 ? "离线" : "在线",
                    online ? "在线" : "离线");
        }
    }
}
