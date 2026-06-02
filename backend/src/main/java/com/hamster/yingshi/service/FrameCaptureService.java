package com.hamster.yingshi.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.hamster.yingshi.config.AiProperties;
import com.hamster.yingshi.entity.Camera;
import com.hamster.yingshi.entity.PetAnalysis;
import com.hamster.yingshi.mapper.PetAnalysisMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.context.properties.ConfigurationProperties;
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
        // 1. 获取直播流地址
        String streamUrl;
        try {
            streamUrl = ezvizService.getLiveStreamUrlWithRetry(camera);
        } catch (Exception e) {
            log.warn("Cannot get stream URL for camera {}: {}", camera.getId(), e.getMessage());
            return;
        }

        // 2. 用 FFmpeg 抓取一帧
        byte[] frameBytes = captureFrame(streamUrl);
        if (frameBytes == null || frameBytes.length == 0) {
            log.warn("Failed to capture frame for camera {}", camera.getId());
            return;
        }
        log.info("Frame captured for camera {}: {} bytes", camera.getId(), frameBytes.length);

        // 3. 调用 AI 分析服务
        JsonNode analysisResult = callAiService(frameBytes, camera.getId());
        if (analysisResult == null) {
            log.warn("AI analysis failed for camera {}", camera.getId());
            return;
        }

        // 4. 解析结果并入库
        saveAnalysisResult(camera.getId(), analysisResult);
    }

    /**
     * 使用 FFmpeg 从直播流截取一帧图片
     */
    private byte[] captureFrame(String streamUrl) {
        try {
            // FFmpeg 从流中截取一帧，输出到 stdout
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

            // 读取 stdout 获取图片数据
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

            // 等待进程结束
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

    /**
     * 调用 Python AI 分析服务
     */
    private JsonNode callAiService(byte[] frameBytes, Integer cameraId) {
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
            body.add("camera_id", String.valueOf(cameraId));

            HttpEntity<MultiValueMap<String, Object>> request = new HttpEntity<>(body, headers);
            ResponseEntity<String> response = restTemplate.exchange(targetUrl, HttpMethod.POST, request, String.class);

            JsonNode root = objectMapper.readTree(response.getBody());
            int code = root.path("code").asInt(0);
            if (code == 200) {
                JsonNode data = root.path("data");
                JsonNode results = data.path("results");
                if (results.isArray() && results.size() > 0) {
                    return results.get(0);
                }
            }
            log.warn("AI service returned non-200: code={}, body={}", code, response.getBody());
            return null;
        } catch (Exception e) {
            log.error("Failed to call AI service: {}", e.getMessage());
            return null;
        }
    }

    /**
     * 解析 AI 分析结果并保存到 pet_analysis 表
     */
    private void saveAnalysisResult(Integer cameraId, JsonNode result) {
        try {
            PetAnalysis analysis = new PetAnalysis();
            analysis.setCameraId(String.valueOf(cameraId));
            analysis.setTimestamp(LocalDateTime.now());
            analysis.setHasPet(result.path("has_pet").asBoolean(false) ? 1 : 0);

            // 运动状态
            boolean isMoving = result.path("is_moving").asBoolean(false);
            analysis.setMovementState(isMoving ? "moving" : "stationary");

            // 食物状态
            String foodStatus = result.path("food_status").asText("unknown");
            analysis.setFoodState(foodStatus);

            // 位置信息
            JsonNode position = result.path("position");
            if (position != null && !position.isNull()) {
                analysis.setPositionX(position.path("x").asInt(0));
                analysis.setPositionY(position.path("y").asInt(0));
                analysis.setPositionWidth(position.path("width").asInt(0));
                analysis.setPositionHeight(position.path("height").asInt(0));
            }

            // 置信度
            analysis.setConfidence(result.path("confidence").asDouble(0));

            petAnalysisMapper.insert(analysis);
            log.info("Analysis result saved for camera {}: hasPet={}, movement={}, food={}",
                    cameraId, analysis.getHasPet(), analysis.getMovementState(), analysis.getFoodState());
        } catch (Exception e) {
            log.error("Failed to save analysis result: {}", e.getMessage());
        }
    }
}
