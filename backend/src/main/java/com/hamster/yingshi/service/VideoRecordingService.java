package com.hamster.yingshi.service;

import com.hamster.yingshi.common.BusinessException;
import com.hamster.yingshi.common.ErrorCode;
import com.hamster.yingshi.config.RecordingProperties;
import com.hamster.yingshi.dto.ezviz.CloudRecordingDtos.*;
import com.hamster.yingshi.entity.Camera;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;

@Service
public class VideoRecordingService {

    private static final Logger log = LoggerFactory.getLogger(VideoRecordingService.class);
    private static final DateTimeFormatter MONTH_FMT = DateTimeFormatter.ofPattern("yyyyMM");

    @Autowired
    private RecordingProperties recordingProperties;

    @Autowired
    private CameraService cameraService;

    @Autowired
    private EzvizService ezvizService;

    // cameraId -> oneOffPlanId, tracks active cloud recording plans
    private final Map<Integer, Long> activePlans = new ConcurrentHashMap<>();

    @Scheduled(fixedDelayString = "${recording.duration-seconds:300}000")
    public void recordAllCameras() {
        if (!recordingProperties.isEnabled()) {
            return;
        }

        Long spaceId = recordingProperties.getSpaceId();
        if (spaceId == null) {
            log.warn("Cloud recording space-id not configured, skip recording");
            return;
        }

        List<Camera> cameras;
        try {
            cameras = cameraService.findAll();
        } catch (Exception e) {
            log.error("Failed to load camera list", e);
            return;
        }

        for (Camera camera : cameras) {
            try {
                recordCamera(camera, spaceId);
            } catch (Exception e) {
                log.error("Failed to create cloud recording plan for camera {}: {}", camera.getId(), e.getMessage());
            }
        }
    }

    private void recordCamera(Camera camera, Long spaceId) {
        int cameraId = camera.getId();

        if (camera.getRecordingEnabled() == null || camera.getRecordingEnabled() != 1) {
            return;
        }

        // Check if there is already an active plan for this camera
        Long existingPlanId = activePlans.get(cameraId);
        if (existingPlanId != null) {
            try {
                CloudPlanResponse planResp = ezvizService.getOneOffPlan(existingPlanId);
                if (planResp.getData() != null) {
                    int status = planResp.getData().getPlanStatus();
                    // 3=未开始, 4=进行中, 1=创建中
                    if (status == 1 || status == 3 || status == 4) {
                        log.debug("Camera {} already has an active cloud plan {}, skip", cameraId, existingPlanId);
                        return;
                    }
                }
            } catch (Exception e) {
                log.warn("Failed to check existing plan {} for camera {}, will create new one: {}",
                        existingPlanId, cameraId, e.getMessage());
            }
            activePlans.remove(cameraId);
        }

        int duration = recordingProperties.getDurationSeconds();
        Long templateId = recordingProperties.getTemplateId();
        String planName = "cam_" + cameraId + "_" + System.currentTimeMillis();
        String localIndex = camera.getChannelNo() != null ? String.valueOf(camera.getChannelNo()) : "1";

        try {
            CloudPlanResponse resp = ezvizService.createOneOffPlan(
                    spaceId, templateId, planName, camera.getDeviceKey(), localIndex, duration);

            if (resp.getData() != null) {
                Long planId = resp.getData().getOneOffPlanId();
                activePlans.put(cameraId, planId);
                log.info("Cloud recording plan created for camera {}: planId={}, duration={}s",
                        cameraId, planId, duration);
            }
        } catch (Exception e) {
            log.error("Failed to create cloud recording plan for camera {}: {}", cameraId, e.getMessage());
        }
    }

    public void stopRecording(Integer cameraId) {
        Long planId = activePlans.remove(cameraId);
        if (planId == null) {
            log.debug("No active cloud plan for camera {}", cameraId);
            return;
        }

        try {
            ezvizService.stopOneOffPlan(planId);
            log.info("Cloud recording plan stopped for camera {}: planId={}", cameraId, planId);
        } catch (Exception e) {
            log.error("Failed to stop cloud plan {} for camera {}: {}", planId, cameraId, e.getMessage());
        }
    }

    public void stopAllRecordings() {
        activePlans.forEach((cameraId, planId) -> {
            try {
                ezvizService.stopOneOffPlan(planId);
                log.info("Cloud recording plan stopped for camera {}: planId={}", cameraId, planId);
            } catch (Exception e) {
                log.error("Failed to stop cloud plan {} for camera {}: {}", planId, cameraId, e.getMessage());
            }
        });
        activePlans.clear();
        log.info("All cloud recording plans stopped");
    }

    public List<String> getRecordingCalendar(Integer cameraId, String month) {
        Camera camera = cameraService.findById(cameraId);
        Long spaceId = recordingProperties.getSpaceId();
        if (spaceId == null) {
            return new ArrayList<>();
        }
        String localIndex = camera.getChannelNo() != null ? String.valueOf(camera.getChannelNo()) : "1";
        return ezvizService.getRecordingCalendar(camera.getDeviceKey(), localIndex, spaceId, month);
    }

    public List<Map<String, Object>> getRecordings(Integer cameraId, String date) {
        Camera camera = cameraService.findById(cameraId);
        Long spaceId = recordingProperties.getSpaceId();
        if (spaceId == null) {
            return new ArrayList<>();
        }

        // 云点播 API 要求时间范围不超过 30 天，查询当天
        String startTime = date + " 00:00:00";
        String endTime = date + " 23:59:59";

        List<Map<String, Object>> vodFiles = ezvizService.getVodFileList(spaceId, startTime, endTime);

        String deviceSerial = camera.getDeviceKey();

        List<Map<String, Object>> result = new ArrayList<>();
        for (Map<String, Object> file : vodFiles) {
            String fileDeviceSerial = (String) file.getOrDefault("deviceSerial", "");

            // 过滤设备：匹配设备序列号，或设备信息为空时也返回
            if (!fileDeviceSerial.isEmpty() && !fileDeviceSerial.equals(deviceSerial)) {
                continue;
            }

            // 获取文件的时间信息（可能是时间戳或格式化字符串）
            Object startTimeObj = file.get("startTime");
            Object stopTimeObj = file.get("stopTime");

            long fileStartMillis = toMillis(startTimeObj);
            long fileEndMillis = toMillis(stopTimeObj);

            Map<String, Object> item = new HashMap<>();
            item.put("fileId", file.getOrDefault("fileNodeId", ""));
            // 格式化为可读时间
            item.put("startTime", formatMillis(fileStartMillis > 0 ? fileStartMillis : System.currentTimeMillis()));
            item.put("endTime", formatMillis(fileEndMillis > 0 ? fileEndMillis : System.currentTimeMillis()));
            item.put("fileSize", file.getOrDefault("fileSize", 0));
            // 从时间差计算时长（毫秒），不依赖 duration 字段
            long durationMillis = (fileStartMillis > 0 && fileEndMillis > 0) ? (fileEndMillis - fileStartMillis) : 0;
            item.put("videoLong", durationMillis);
            item.put("downloadPath", file.getOrDefault("playUrl", ""));
            item.put("coverPic", file.getOrDefault("coverPic", ""));
            item.put("coverPicUrl", file.getOrDefault("coverPicUrl", ""));
            item.put("deviceSerial", fileDeviceSerial);
            item.put("channelNo", String.valueOf(file.getOrDefault("channelNo", 0)));
            item.put("fileName", file.getOrDefault("fileName", ""));
            result.add(item);
        }

        result.sort((a, b) -> {
            String sa = (String) a.getOrDefault("startTime", "");
            String sb = (String) b.getOrDefault("startTime", "");
            return sb.compareTo(sa);
        });

        return result;
    }

    /**
     * 将各种时间格式转换为毫秒时间戳
     */
    private long toMillis(Object timeObj) {
        if (timeObj == null) return 0;
        if (timeObj instanceof Number) {
            long val = ((Number) timeObj).longValue();
            // 如果是秒级时间戳，转换为毫秒
            if (val < 10000000000L) {
                return val * 1000;
            }
            return val;
        }
        String timeStr = timeObj.toString().trim();
        if (timeStr.isEmpty()) return 0;
        try {
            return Long.parseLong(timeStr);
        } catch (NumberFormatException e) {
            return parseDateToMillis(timeStr);
        }
    }

    /**
     * 解析日期字符串为毫秒时间戳
     */
    private long parseDateToMillis(String dateStr) {
        try {
            java.time.LocalDateTime ldt = java.time.LocalDateTime.parse(dateStr,
                    java.time.format.DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss"));
            return ldt.atZone(java.time.ZoneId.systemDefault()).toInstant().toEpochMilli();
        } catch (Exception e) {
            return 0;
        }
    }

    /**
     * 将毫秒时间戳格式化为 yyyy-MM-dd HH:mm:ss
     */
    private String formatMillis(long millis) {
        try {
            java.time.LocalDateTime ldt = java.time.LocalDateTime.ofInstant(
                    java.time.Instant.ofEpochMilli(millis), java.time.ZoneId.systemDefault());
            return ldt.format(java.time.format.DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss"));
        } catch (Exception e) {
            return String.valueOf(millis);
        }
    }

    public Map<String, Object> getCloudPlayAddress(Integer cameraId, String startTime, String endTime) {
        Camera camera = cameraService.findById(cameraId);
        Long spaceId = recordingProperties.getSpaceId();
        if (spaceId == null) {
            throw new BusinessException(ErrorCode.EZVIZ_API_ERROR, "Cloud recording space not configured");
        }

        // 先从云点播获取录像文件列表，找到对应时间段的文件
        List<Map<String, Object>> vodFiles = ezvizService.getVodFileList(spaceId, startTime, endTime);
        if (!vodFiles.isEmpty()) {
            // 找到匹配的文件，获取其播放地址
            Map<String, Object> file = vodFiles.get(0);
            String fileNodeId = (String) file.getOrDefault("fileNodeId", "");
            String playUrl = (String) file.getOrDefault("playUrl", "");

            // 如果没有 playUrl，通过 downloadurl 接口获取
            if (playUrl.isEmpty() && !fileNodeId.isEmpty()) {
                playUrl = ezvizService.getVodFileDownloadUrl(spaceId, fileNodeId, 3600);
            }

            Map<String, Object> result = new HashMap<>();
            result.put("url", playUrl);
            result.put("deviceKey", camera.getDeviceKey());
            result.put("channelNo", camera.getChannelNo() != null ? camera.getChannelNo() : 1);
            result.put("accessToken", camera.getAccessToken());
            result.put("playType", "vod");  // 标记为云点播播放
            return result;
        }

        // 降级：使用云录制 ezopen:// 播放
        String localIndex = camera.getChannelNo() != null ? String.valueOf(camera.getChannelNo()) : "1";
        CloudPlayAddressResponse.PlayData playData = ezvizService.getCloudPlaybackAddress(
                camera.getDeviceKey(), localIndex, spaceId, startTime, endTime);

        Map<String, Object> result = new HashMap<>();
        result.put("url", playData.getUrl());
        result.put("deviceKey", camera.getDeviceKey());
        result.put("channelNo", camera.getChannelNo() != null ? camera.getChannelNo() : 1);
        result.put("accessToken", camera.getAccessToken());
        result.put("playType", "ezopen");
        return result;
    }

    public void deleteRecording(Integer cameraId, String startTime, String endTime) {
        Camera camera = cameraService.findById(cameraId);
        Long spaceId = recordingProperties.getSpaceId();
        if (spaceId == null) {
            throw new BusinessException(ErrorCode.EZVIZ_API_ERROR, "Cloud recording space not configured");
        }

        String localIndex = camera.getChannelNo() != null ? String.valueOf(camera.getChannelNo()) : "1";
        ezvizService.deleteCloudRecording(camera.getDeviceKey(), localIndex, spaceId, startTime, endTime);
    }

    private String formatCloudTime(String raw) {
        if (raw == null || raw.isEmpty()) return raw;
        // Input format: "20240124115700" -> "2024-01-24 11:57:00"
        if (raw.length() == 14 && !raw.contains("-")) {
            return raw.substring(0, 4) + "-" + raw.substring(4, 6) + "-" + raw.substring(6, 8)
                    + " " + raw.substring(8, 10) + ":" + raw.substring(10, 12) + ":" + raw.substring(12, 14);
        }
        return raw;
    }
}
