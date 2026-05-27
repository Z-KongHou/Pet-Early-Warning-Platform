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
     * Check camera online status every 10 seconds.
     */
    @Scheduled(fixedDelay = 10000)
    public void checkAllCamerasStatus() {
        List<Camera> cameras = cameraService.findAll();
        if (cameras.isEmpty()) {
            return;
        }

        log.info("Checking camera online status, total={}", cameras.size());

        for (Camera camera : cameras) {
            try {
                checkCameraStatus(camera);
            } catch (Exception e) {
                log.error("Failed to check camera {} status: {}", camera.getId(), e.getMessage());
            }
        }
    }

    /**
     * Check online status for a single camera.
     */
    private void checkCameraStatus(Camera camera) {
        boolean online = ezvizService.checkDeviceOnline(camera);
        int newStatus = online ? 1 : 0;

        // Update database only when status changes
        Integer currentStatus = camera.getOnlineStatus();
        if (currentStatus == null || currentStatus != newStatus) {
            LambdaUpdateWrapper<Camera> updateWrapper = new LambdaUpdateWrapper<Camera>()
                    .eq(Camera::getId, camera.getId())
                    .set(Camera::getOnlineStatus, newStatus);
            if (online) {
                updateWrapper.set(Camera::getLastOnlineTime, LocalDateTime.now());
            }
            cameraMapper.update(null, updateWrapper);
            log.info("Camera {} status changed: {} -> {}", camera.getId(),
                    currentStatus == null ? "unknown" : (currentStatus == 0 ? "offline" : "online"),
                    online ? "online" : "offline");
        }
    }
}
