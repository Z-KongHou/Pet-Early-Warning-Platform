package com.hamster.yingshi.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.hamster.yingshi.config.AiProperties;
import com.hamster.yingshi.entity.ActivityHistory;
import com.hamster.yingshi.entity.Camera;
import com.hamster.yingshi.entity.PetAnalysis;
import com.hamster.yingshi.mapper.PetAnalysisMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.http.*;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.web.client.RestTemplate;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.time.LocalDateTime;
import java.util.List;

@Service
public class FrameCaptureService {

    private static final Logger log = LoggerFactory.getLogger(FrameCaptureService.class);

    @Autowired
    private CameraService cameraService;

    @Autowired
    private EzvizService ezvizService;

    @Autowired
    private PetAnalysisMapper petAnalysisMapper;

    @Autowired
    private ActivityHistoryService activityHistoryService;

    @Autowired
    private AiProperties aiProperties;

    private final RestTemplate restTemplate = new RestTemplate();
    private final ObjectMapper objectMapper = new ObjectMapper();

    /**
     * 每5分钟执行一次：抓帧 → AI分析 → 入库
     */
    @Scheduled(fixedDelay = 300000)
    public void scheduledCaptureAndAnalyze() {
        log.info("Starting scheduled frame capture and analysis...");
        List<Camera> cameras = cameraService.findAll();
        for (Camera camera : cameras) {
            try {
                captureAndAnalyze(camera);
            } catch (Exception e) {
                log.error("Failed to capture and analyze for camera {}: {}", camera.getId(), e.getMessage());
            }
        }
        log.info("Scheduled frame capture and analysis completed");
    }

    /**
     * 对单个摄像头执行抓帧分析
     */
    public void captureAndAnalyze(Camera camera) {
        String streamUrl;
        try {
            streamUrl = ezvizService.getLiveStreamUrlWithRetry(camera);
        } catch (Exception e) {
            log.warn("Cannot get stream URL for camera {}: {}", camera.getId(), e.getMessage());
            return;
        }

        byte[] frameBytes = captureFrame(streamUrl);
        if (frameBytes == null || frameBytes.length == 0) {
            log.warn("Failed to capture frame for camera {}", camera.getId());
            return;
        }
        log.info("Frame captured for camera {}: {} bytes", camera.getId(), frameBytes.length);

        JsonNode analysisResult = callAiService(frameBytes, camera);
        if (analysisResult == null) {
            log.warn("AI analysis failed for camera {}", camera.getId());
            return;
        }

        saveAnalysisResult(camera, analysisResult);
        saveActivityHistory(camera, analysisResult);
    }

    private byte[] captureFrame(String streamUrl) {
        try {
            ProcessBuilder pb = new ProcessBuilder(
                "ffmpeg",
                "-i", streamUrl,
                "-frames:v", "1",
                "-f", "image2",
                "-c:v", "mjpeg",
                "-q:v", "2",
                "-"
            );
            pb.redirectErrorStream(false);
            Process process = pb.start();

            byte[] frameData;
            try (InputStream is = process.getInputStream();
                 ByteArrayOutputStream baos = new ByteArrayOutputStream()) {
                byte[] buffer = new byte[8192];
                int len;
                while ((len = is.read(buffer)) != -1) {
                    baos.write(buffer, 0, len);
                }
                frameData = baos.toByteArray();
            }

            int exitCode = process.waitFor();
            if (exitCode != 0) {
                log.warn("FFmpeg exited with code {}", exitCode);
                return null;
            }

            return frameData.length > 100 ? frameData : null;
        } catch (Exception e) {
            log.error("FFmpeg frame capture failed: {}", e.getMessage());
            return null;
        }
    }

    private JsonNode callAiService(byte[] frameBytes, Camera camera) {
        try {
            String targetUrl = aiProperties.getServiceUrl() + "/api/hamster/analyze";

            HttpHeaders headers = new HttpHeaders();
            headers.setContentType(MediaType.MULTIPART_FORM_DATA);

            MultiValueMap<String, Object> body = new LinkedMultiValueMap<>();
            ByteArrayResource fileResource = new ByteArrayResource(frameBytes) {
                @Override
                public String getFilename() {
                    return "capture.jpg";
                }
            };
            body.add("files", fileResource);
            body.add("camera_id", String.valueOf(camera.getId()));
            if (camera.getAccessToken() != null && !camera.getAccessToken().isBlank()) {
                body.add("ezviz_access_token", camera.getAccessToken());
            }

            HttpEntity<MultiValueMap<String, Object>> request = new HttpEntity<>(body, headers);
            ResponseEntity<String> response = restTemplate.exchange(targetUrl, HttpMethod.POST, request, String.class);

            JsonNode root = objectMapper.readTree(response.getBody());
            int code = root.path("code").asInt(0);
            if (code != 200) {
                log.warn("AI service returned non-200: code={}, body={}", code, response.getBody());
                return null;
            }

            JsonNode data = root.path("data");
            JsonNode result = data.path("result");
            if (!result.isMissingNode() && result.path("success").asBoolean(false)) {
                return result;
            }

            // 兼容旧版 results 数组格式
            JsonNode results = data.path("results");
            if (results.isArray() && results.size() > 0) {
                return results.get(0);
            }

            log.warn("AI service response missing result: {}", response.getBody());
            return null;
        } catch (Exception e) {
            log.error("Failed to call AI service: {}", e.getMessage());
            return null;
        }
    }

    private void saveAnalysisResult(Camera camera, JsonNode result) {
        try {
            PetAnalysis analysis = new PetAnalysis();
            analysis.setUserId(camera.getUserId());
            analysis.setCameraId(String.valueOf(camera.getId()));
            analysis.setTimestamp(LocalDateTime.now());
            analysis.setHasPet(result.path("has_pet").asBoolean(false) ? 1 : 0);

            boolean isMoving = result.path("is_moving").asBoolean(false);
            analysis.setMovementState(isMoving ? "moving" : "stationary");

            String foodStatus = result.path("food_status").asText("unknown");
            analysis.setFoodState(foodStatus);

            JsonNode position = result.path("position");
            if (position != null && !position.isNull()) {
                analysis.setPositionX(position.path("x").asInt(0));
                analysis.setPositionY(position.path("y").asInt(0));
                analysis.setPositionWidth(position.path("width").asInt(0));
                analysis.setPositionHeight(position.path("height").asInt(0));
            }

            analysis.setConfidence(result.path("confidence").asDouble(0));

            petAnalysisMapper.insert(analysis);
            log.info("Pet analysis saved for camera {}: hasPet={}, movement={}, food={}",
                    camera.getId(), analysis.getHasPet(), analysis.getMovementState(), analysis.getFoodState());
        } catch (Exception e) {
            log.error("Failed to save pet analysis: {}", e.getMessage());
        }
    }

    private void saveActivityHistory(Camera camera, JsonNode result) {
        try {
            ActivityHistory history = new ActivityHistory();
            history.setUserId(camera.getUserId());
            history.setHamsterId(camera.getHamsterId());
            history.setCameraId(camera.getId());
            history.setActivityScore(result.path("activity_score").asInt(50));
            history.setStatus(mapActivityStatus(result.path("activity_status").asText("normal")));

            String analysisText = result.path("analysis_result").asText(null);
            if (analysisText == null || analysisText.isBlank()) {
                analysisText = result.path("activity_description").asText("");
            }
            history.setAnalysisResult(analysisText);

            activityHistoryService.create(history);
            log.info("Activity history saved for camera {}: score={}, status={}",
                    camera.getId(), history.getActivityScore(), history.getStatus());
        } catch (Exception e) {
            log.error("Failed to save activity history: {}", e.getMessage());
        }
    }

    private String mapActivityStatus(String pythonStatus) {
        if (pythonStatus == null) {
            return "normal";
        }
        return switch (pythonStatus) {
            case "critical" -> "high";
            case "low", "high", "normal" -> pythonStatus;
            default -> "normal";
        };
    }
}
