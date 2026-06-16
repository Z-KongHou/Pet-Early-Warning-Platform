package com.hamster.yingshi.controller;

import com.hamster.yingshi.common.Result;
import com.hamster.yingshi.entity.Camera;
import com.hamster.yingshi.entity.FrameImage;
import com.hamster.yingshi.entity.Hamster;
import com.hamster.yingshi.entity.PetAnalysis;
import com.hamster.yingshi.entity.PetState;
import com.hamster.yingshi.entity.Setting;
import com.hamster.yingshi.service.CameraService;
import com.hamster.yingshi.service.FrameDataService;
import com.hamster.yingshi.service.HamsterService;
import com.hamster.yingshi.service.SettingService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * 内部 REST API，供 AI 服务调用，用于读写 MySQL 中的 frame_images / pet_state / pet_analysis 数据。
 */
@RestController
@RequestMapping("/api/internal")
public class FrameDataController {

    @Autowired
    private FrameDataService frameDataService;

    @Autowired
    private HamsterService hamsterService;

    @Autowired
    private CameraService cameraService;

    @Autowired
    private SettingService settingService;

    // ==================== agent context ====================

    /**
     * Returns non-sensitive database context for the AI agent:
     * hamsters (name, breed, age, weight, etc.), cameras, and filtered settings.
     * Excludes passwords, API keys, access tokens, and other secrets.
     */
    @GetMapping("/agent-context")
    public Result<Map<String, Object>> getAgentContext(
            @RequestParam(value = "user_id", required = false, defaultValue = "1") Integer userId) {

        // 1. Hamsters — all non-sensitive fields
        List<Map<String, Object>> hamsters = new ArrayList<>();
        for (Hamster h : hamsterService.findByUserId(userId)) {
            Map<String, Object> m = new HashMap<>();
            m.put("id", h.getId());
            m.put("name", h.getName());
            m.put("breed", h.getBreed());
            m.put("birthDate", h.getBirthDate() != null ? h.getBirthDate().toString() : null);
            m.put("gender", h.getGender());
            m.put("weight", h.getWeight());
            m.put("healthStatus", h.getHealthStatus());
            m.put("remark", h.getRemark());
            m.put("createdAt", h.getCreatedAt() != null ? h.getCreatedAt().toString() : null);
            hamsters.add(m);
        }

        // 2. Cameras — exclude accessToken
        List<Map<String, Object>> cameras = new ArrayList<>();
        for (Camera c : cameraService.findByUserId(userId)) {
            Map<String, Object> m = new HashMap<>();
            m.put("id", c.getId());
            m.put("hamsterId", c.getHamsterId());
            m.put("name", c.getName());
            m.put("deviceKey", c.getDeviceKey());
            m.put("channelNo", c.getChannelNo());
            m.put("onlineStatus", c.getOnlineStatus());
            m.put("lastOnlineTime", c.getLastOnlineTime() != null ? c.getLastOnlineTime().toString() : null);
            m.put("recordingEnabled", c.getRecordingEnabled());
            cameras.add(m);
        }

        // 3. Settings — exclude keys containing "api_key", "secret", "password"
        Map<String, String> settings = new HashMap<>();
        for (Setting s : settingService.findByUserId(userId)) {
            String key = s.getKeyName();
            String lower = key.toLowerCase();
            if (lower.contains("api_key") || lower.contains("secret") || lower.contains("password")) {
                continue;
            }
            settings.put(key, s.getKeyValue());
        }

        // 4. Pet state + recent activity history for each camera
        List<Map<String, Object>> cameraStates = new ArrayList<>();
        for (Camera c : cameraService.findByUserId(userId)) {
            String camId = String.valueOf(c.getId());
            Map<String, Object> cs = new HashMap<>();
            cs.put("cameraId", camId);

            // Pet state
            try {
                PetState state = frameDataService.getOrCreatePetState(userId, camId);
                Map<String, Object> st = new HashMap<>();
                st.put("lastEatingTime", state.getLastEatingTime() != null ? state.getLastEatingTime().toString() : null);
                st.put("stationaryStartTime", state.getStationaryStartTime() != null ? state.getStationaryStartTime().toString() : null);
                st.put("totalAnalyses", state.getTotalAnalyses());
                if (state.getLastPositionX() != null) {
                    Map<String, Object> pos = new HashMap<>();
                    pos.put("x", state.getLastPositionX());
                    pos.put("y", state.getLastPositionY());
                    pos.put("width", state.getLastPositionWidth());
                    pos.put("height", state.getLastPositionHeight());
                    st.put("lastPosition", pos);
                }
                cs.put("state", st);
            } catch (Exception e) {
                cs.put("state", null);
            }

            // Recent activity (last 5)
            try {
                List<PetAnalysis> analyses = frameDataService.getAnalysisHistory(camId);
                List<Map<String, Object>> recent = new ArrayList<>();
                int limit = Math.min(analyses.size(), 5);
                for (int i = analyses.size() - limit; i < analyses.size(); i++) {
                    PetAnalysis a = analyses.get(i);
                    Map<String, Object> am = new HashMap<>();
                    am.put("timestamp", a.getTimestamp() != null ? a.getTimestamp().toString() : null);
                    am.put("hasPet", a.getHasPet());
                    am.put("movementState", a.getMovementState());
                    am.put("foodState", a.getFoodState());
                    am.put("confidence", a.getConfidence());
                    recent.add(am);
                }
                cs.put("recentActivity", recent);
            } catch (Exception e) {
                cs.put("recentActivity", List.of());
            }

            cameraStates.add(cs);
        }

        Map<String, Object> data = new HashMap<>();
        data.put("hamsters", hamsters);
        data.put("cameras", cameras);
        data.put("settings", settings);
        data.put("cameraStates", cameraStates);
        data.put("userId", userId);
        return Result.success(data);
    }

    // ==================== frame_images ====================

    @PostMapping("/frames")
    public Result<Map<String, Object>> insertFrame(@RequestBody Map<String, Object> body) {
        Integer userId = (Integer) body.get("user_id");
        String cameraId = (String) body.get("camera_id");
        String requestId = (String) body.get("request_id");
        String originalFilename = (String) body.get("original_filename");
        String filePath = (String) body.get("file_path");
        Integer fileSize = (Integer) body.get("file_size");
        LocalDateTime imageTimestamp = LocalDateTime.parse((String) body.get("image_timestamp"));
        String source = body.containsKey("source") ? (String) body.get("source") : "upload";

        Long id = frameDataService.insertFrame(userId, cameraId, requestId,
                originalFilename, filePath, fileSize, imageTimestamp, source);

        Map<String, Object> data = new HashMap<>();
        data.put("id", id);
        return Result.success(data);
    }

    @GetMapping("/frames/{id}")
    public Result<Map<String, Object>> getFrameById(@PathVariable Long id) {
        FrameImage frame = frameDataService.getFrameById(id);
        if (frame == null) {
            return Result.error(404, "Frame not found");
        }
        return Result.success(frameToMap(frame));
    }

    @GetMapping("/frames/window")
    public Result<Map<String, Object>> getFramesInWindow(
            @RequestParam("camera_id") String cameraId,
            @RequestParam("latest_ts") @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) LocalDateTime latestTs,
            @RequestParam("window_seconds") int windowSeconds) {

        List<FrameImage> frames = frameDataService.getFramesInWindow(cameraId, latestTs, windowSeconds);
        List<Map<String, Object>> list = new ArrayList<>();
        for (FrameImage f : frames) {
            list.add(frameToMap(f));
        }

        Map<String, Object> data = new HashMap<>();
        data.put("frames", list);
        data.put("count", list.size());
        return Result.success(data);
    }

    @GetMapping("/frames/latest-detected")
    public Result<Map<String, Object>> getLatestDetectedFrame(
            @RequestParam("camera_id") String cameraId,
            @RequestParam("before_ts") @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) LocalDateTime beforeTs) {

        FrameImage frame = frameDataService.getLatestDetectedFrame(cameraId, beforeTs);
        if (frame == null) {
            Map<String, Object> data = new HashMap<>();
            data.put("frame", null);
            return Result.success(data);
        }
        Map<String, Object> data = new HashMap<>();
        data.put("frame", frameToMap(frame));
        return Result.success(data);
    }

    @PutMapping("/frames/{id}/detection")
    public Result<Void> updateFrameDetection(@PathVariable Long id, @RequestBody Map<String, Object> body) {
        Integer hasPet = body.containsKey("has_pet") ? ((Boolean) body.get("has_pet") ? 1 : 0) : null;

        @SuppressWarnings("unchecked")
        Map<String, Object> position = (Map<String, Object>) body.get("position");
        Integer posX = null, posY = null, posWidth = null, posHeight = null;
        if (position != null) {
            posX = position.containsKey("x") ? (Integer) position.get("x") : null;
            posY = position.containsKey("y") ? (Integer) position.get("y") : null;
            posWidth = position.containsKey("width") ? (Integer) position.get("width") : null;
            posHeight = position.containsKey("height") ? (Integer) position.get("height") : null;
        }

        Double confidence = body.containsKey("confidence") ? ((Number) body.get("confidence")).doubleValue() : null;
        String foodStatus = (String) body.get("food_status");

        frameDataService.updateFrameDetection(id, hasPet, posX, posY, posWidth, posHeight, confidence, foodStatus);
        return Result.success();
    }

    @PutMapping("/frames/batch-status")
    public Result<Void> batchUpdateStatus(@RequestBody Map<String, Object> body) {
        @SuppressWarnings("unchecked")
        List<Number> ids = (List<Number>) body.get("frame_ids");
        String status = (String) body.get("status");
        List<Long> frameIds = new ArrayList<>();
        for (Number n : ids) {
            frameIds.add(n.longValue());
        }
        frameDataService.batchUpdateStatus(frameIds, status);
        return Result.success();
    }

    @PutMapping("/frames/batch-touch")
    public Result<Void> batchTouchFrames(@RequestBody Map<String, Object> body) {
        @SuppressWarnings("unchecked")
        List<Number> ids = (List<Number>) body.get("frame_ids");
        List<Long> frameIds = new ArrayList<>();
        for (Number n : ids) {
            frameIds.add(n.longValue());
        }
        frameDataService.batchTouchFrames(frameIds);
        return Result.success();
    }

    @PostMapping("/frames/evict")
    public Result<Void> evictLruFrames(@RequestParam("camera_id") String cameraId) {
        frameDataService.evictLruFrames(cameraId);
        return Result.success();
    }

    // ==================== pet_state ====================

    @GetMapping("/pet-state")
    public Result<Map<String, Object>> getPetState(
            @RequestParam("camera_id") String cameraId,
            @RequestParam(value = "user_id", required = false, defaultValue = "1") Integer userId) {
        PetState state = frameDataService.getOrCreatePetState(userId, cameraId);
        return Result.success(petStateToMap(state));
    }

    @PutMapping("/pet-state")
    public Result<Void> updatePetState(
            @RequestParam("camera_id") String cameraId,
            @RequestBody Map<String, Object> updates) {
        frameDataService.updatePetState(cameraId, updates);
        return Result.success();
    }

    // ==================== pet_analysis ====================

    @GetMapping("/pet-analysis/history")
    public Result<Map<String, Object>> getAnalysisHistory(@RequestParam("camera_id") String cameraId) {
        List<PetAnalysis> history = frameDataService.getAnalysisHistory(cameraId);
        List<Map<String, Object>> list = new ArrayList<>();
        for (PetAnalysis a : history) {
            list.add(analysisToMap(a));
        }
        Map<String, Object> data = new HashMap<>();
        data.put("history", list);
        data.put("count", list.size());
        return Result.success(data);
    }

    // ==================== helpers ====================

    private Map<String, Object> frameToMap(FrameImage f) {
        Map<String, Object> m = new HashMap<>();
        m.put("id", f.getId());
        m.put("camera_id", f.getCameraId());
        m.put("request_id", f.getRequestId());
        m.put("filename", f.getOriginalFilename());
        m.put("file_path", f.getFilePath());
        m.put("file_size", f.getFileSize());
        m.put("image_timestamp", f.getImageTimestamp() != null ? f.getImageTimestamp().toString() : null);
        m.put("timestamp", f.getImageTimestamp() != null ? f.getImageTimestamp().toString() : null);
        m.put("source", f.getSource());
        m.put("status", f.getStatus());
        m.put("last_accessed_at", f.getLastAccessedAt() != null ? f.getLastAccessedAt().toString() : null);

        Map<String, Object> position = null;
        if (f.getPositionX() != null) {
            position = new HashMap<>();
            position.put("x", f.getPositionX());
            position.put("y", f.getPositionY());
            position.put("width", f.getPositionWidth());
            position.put("height", f.getPositionHeight());
        }
        m.put("position", position);

        Map<String, Object> analysis = null;
        if (f.getHasPet() != null) {
            analysis = new HashMap<>();
            analysis.put("has_pet", f.getHasPet() == 1);
            analysis.put("pet_type", "仓鼠");
            analysis.put("position", position);
            analysis.put("confidence", f.getConfidence() != null ? f.getConfidence() : 0.0);
            analysis.put("food_status", f.getFoodStatus() != null ? f.getFoodStatus() : "unknown");
            analysis.put("is_moving", false);
            Map<String, Object> anomaly = new HashMap<>();
            anomaly.put("long_stationary", false);
            anomaly.put("no_eating", false);
            analysis.put("anomaly", anomaly);
        }
        m.put("analysis", analysis);
        return m;
    }

    private Map<String, Object> petStateToMap(PetState s) {
        Map<String, Object> m = new HashMap<>();
        m.put("id", s.getId());
        m.put("camera_id", s.getCameraId());

        Map<String, Object> lastPos = null;
        if (s.getLastPositionX() != null) {
            lastPos = new HashMap<>();
            lastPos.put("x", s.getLastPositionX());
            lastPos.put("y", s.getLastPositionY());
            lastPos.put("width", s.getLastPositionWidth());
            lastPos.put("height", s.getLastPositionHeight());
        }
        m.put("last_position", lastPos);

        m.put("last_eating_time", s.getLastEatingTime() != null ? s.getLastEatingTime().toString() : null);
        m.put("stationary_start_time", s.getStationaryStartTime() != null ? s.getStationaryStartTime().toString() : null);

        Map<String, Object> bowlPos = null;
        if (s.getFoodBowlPositionX() != null) {
            bowlPos = new HashMap<>();
            bowlPos.put("x", s.getFoodBowlPositionX());
            bowlPos.put("y", s.getFoodBowlPositionY());
            bowlPos.put("width", s.getFoodBowlPositionWidth());
            bowlPos.put("height", s.getFoodBowlPositionHeight());
        }
        m.put("food_bowl_position", bowlPos);
        m.put("total_analyses", s.getTotalAnalyses());
        m.put("history", new ArrayList<>());
        return m;
    }

    private Map<String, Object> analysisToMap(PetAnalysis a) {
        Map<String, Object> m = new HashMap<>();
        m.put("id", a.getId());
        m.put("camera_id", a.getCameraId());
        m.put("timestamp", a.getTimestamp() != null ? a.getTimestamp().toString() : null);
        m.put("has_pet", a.getHasPet() != null && a.getHasPet() == 1);
        m.put("movement_state", a.getMovementState());
        m.put("is_moving", "moving".equals(a.getMovementState()));
        m.put("food_state", a.getFoodState());

        Map<String, Object> position = null;
        if (a.getPositionX() != null) {
            position = new HashMap<>();
            position.put("x", a.getPositionX());
            position.put("y", a.getPositionY());
            position.put("width", a.getPositionWidth());
            position.put("height", a.getPositionHeight());
        }
        m.put("position", position);
        m.put("confidence", a.getConfidence());
        return m;
    }
}
