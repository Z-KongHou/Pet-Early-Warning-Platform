package com.hamster.yingshi.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.hamster.yingshi.config.AiProperties;
import com.hamster.yingshi.dto.AiChatRequest;
import com.hamster.yingshi.dto.AiChatResponse;
import com.hamster.yingshi.entity.ActivityHistory;
import com.hamster.yingshi.entity.Camera;
import com.hamster.yingshi.event.ActivityAnalyzedEvent;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.http.*;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;

import java.util.ArrayList;
import java.util.List;
import java.util.Random;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

@Service
public class AnalysisService {

    private static final Logger log = LoggerFactory.getLogger(AnalysisService.class);

    @Autowired
    private AiProperties aiProperties;

    @Autowired
    private ObjectMapper objectMapper;

    @Autowired
    private CameraService cameraService;

    @Autowired
    private ActivityHistoryService activityHistoryService;

    @Autowired
    private ApplicationEventPublisher eventPublisher;

    private final RestTemplate restTemplate = new RestTemplate();

    public AnalysisResult analyzeActivity(Integer cameraId, String imageUrl, boolean forceFallback) {
        AnalysisResult result;
        if (forceFallback) {
            result = generateFallbackResult(cameraId);
        } else {
            try {
                String prompt = buildPrompt(imageUrl);
                String aiResponse = callAiApi(prompt);
                result = parseAiResponse(aiResponse, cameraId);
            } catch (Exception e) {
                log.warn("AI analysis failed, using fallback: {}", e.getMessage());
                result = generateFallbackResult(cameraId);
            }
        }

        // Persist to activity_history and trigger downstream alert pipeline
        try {
            saveAndPublish(cameraId, result);
        } catch (Exception e) {
            log.error("Failed to save/publish analysis result for camera {}: {}", cameraId, e.getMessage());
        }

        return result;
    }

    private void saveAndPublish(Integer cameraId, AnalysisResult result) {
        Camera camera = cameraService.findById(cameraId);
        if (camera == null) {
            log.warn("Camera not found: {}, skipping history/alert", cameraId);
            return;
        }

        // Save activity history
        ActivityHistory history = new ActivityHistory();
        history.setUserId(camera.getUserId());
        history.setHamsterId(camera.getHamsterId());
        history.setCameraId(cameraId);
        history.setActivityScore(result.getActivityScore());
        history.setStatus(mapStatus(result.getStatus()));
        history.setAnalysisResult(result.getAnalysisResult());
        activityHistoryService.create(history);
        log.info("Activity history saved: cameraId={}, score={}, status={}",
                cameraId, result.getActivityScore(), result.getStatus());

        // Build a minimal JsonNode that mimics the AI service response format,
        // so the AlertEventListener can consume it just like a real analysis.
        // Score semantics: LOW = danger (inactive/not eating), HIGH = healthy.
        ObjectNode analysisJson = objectMapper.createObjectNode();
        analysisJson.put("has_pet", true);
        analysisJson.put("activity_score", result.getActivityScore());
        // AlertEventListener.mapActivityStatus converts "critical"→"high" for DB alert
        analysisJson.put("activity_status", result.getStatus());
        analysisJson.put("analysis_result", result.getAnalysisResult());
        analysisJson.put("activity_description", result.getDescription());
        analysisJson.put("confidence", 0.85);
        analysisJson.put("is_moving", result.getActivityScore() >= 40);
        analysisJson.put("food_status", "unknown");
        ObjectNode anomaly = analysisJson.putObject("anomaly");
        anomaly.put("long_stationary", result.getActivityScore() < 40);
        anomaly.put("no_eating", result.getActivityScore() < 40);

        eventPublisher.publishEvent(new ActivityAnalyzedEvent(this, camera, analysisJson));
        log.info("ActivityAnalyzedEvent published for cameraId={}", cameraId);
    }

    private String mapStatus(String status) {
        if (status == null) return "normal";
        switch (status) {
            case "critical": return "high";  // danger → DB high
            case "low": return "low";
            case "high": return "high";
            default: return "normal";
        }
    }

    private String buildPrompt(String imageUrl) {
        return "Analyze this hamster image and assess its health/wellness status.\n" +
                "Return JSON only with the following fields:\n" +
                "- score: wellness score (integer 0-100, where LOW score = unhealthy/dangerous, HIGH score = healthy/active)\n" +
                "- status: danger level (critical/low/normal)\n" +
                "  * critical: score < 40 — hamster is inactive, not moving, not eating, needs urgent attention\n" +
                "  * low: score 40-70 — hamster shows reduced activity, monitor closely\n" +
                "  * normal: score >= 70 — hamster is healthy and active, no concern\n" +
                "- description: brief status description (in English)\n" +
                "- analysis: detailed analysis explanation (in English)\n" +
                "Note: return JSON only, no other text.";
    }

    private String callAiApi(String prompt) throws JsonProcessingException {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        headers.set("Authorization", "Bearer " + aiProperties.getApiKey());

        List<AiChatRequest.Message> messages = new ArrayList<>();
        messages.add(new AiChatRequest.Message("system", "You are a professional pet health analysis assistant."));
        messages.add(new AiChatRequest.Message("user", prompt));

        AiChatRequest request = new AiChatRequest(aiProperties.getModel(), messages);
        String requestBody = objectMapper.writeValueAsString(request);

        HttpEntity<String> entity = new HttpEntity<>(requestBody, headers);
        ResponseEntity<String> response = restTemplate.exchange(
                aiProperties.getApiUrl(),
                HttpMethod.POST,
                entity,
                String.class
        );

        AiChatResponse aiResponse = objectMapper.readValue(response.getBody(), AiChatResponse.class);
        if (aiResponse.getChoices() != null && !aiResponse.getChoices().isEmpty()) {
            return aiResponse.getChoices().get(0).getMessage().getContent();
        }
        throw new RuntimeException("AI response is empty");
    }

    private AnalysisResult parseAiResponse(String aiResponse, Integer cameraId) {
        try {
            String jsonStr = extractJson(aiResponse);
            AiAnalysisResult result = objectMapper.readValue(jsonStr, AiAnalysisResult.class);
            return new AnalysisResult(
                    cameraId,
                    result.getScore() != null ? result.getScore() : 50,
                    result.getStatus() != null ? result.getStatus() : "normal",
                    result.getDescription() != null ? result.getDescription() : "",
                    result.getAnalysis() != null ? result.getAnalysis() : ""
            );
        } catch (Exception e) {
            log.warn("Failed to parse AI response, using fallback: {}", e.getMessage());
            return generateFallbackResult(cameraId);
        }
    }

    private String extractJson(String text) {
        Pattern pattern = Pattern.compile("\\{.*\\}", Pattern.DOTALL);
        Matcher matcher = pattern.matcher(text);
        if (matcher.find()) {
            return matcher.group();
        }
        return text;
    }

    /**
     * Fallback when the AI API is unavailable.  Generates a random wellness score
     * and maps it to the same status semantics as the Python AI service:
     * <pre>
     *   score < 40  → "critical" (danger — triggers alert via AlertEventListener)
     *   score 40-70 → "low"      (warning)
     *   score >= 70 → "normal"   (healthy)
     * </pre>
     */
    private AnalysisResult generateFallbackResult(Integer cameraId) {
        Random random = new Random();
        // Bias toward lower scores so we get a mix of critical/low/normal
        int score = random.nextInt(101);
        String status;
        String description;

        if (score < 40) {
            status = "critical";
            description = String.format(
                "Score %d: hamster shows very low activity — may not be moving or eating, needs attention", score);
        } else if (score < 70) {
            status = "low";
            description = String.format(
                "Score %d: hamster activity is below normal, monitoring recommended", score);
        } else {
            status = "normal";
            description = String.format(
                "Score %d: hamster is active and appears healthy", score);
        }

        return new AnalysisResult(
                cameraId,
                score,
                status,
                description,
                "Fallback/demo result — AI API was not available for this analysis."
        );
    }

    @lombok.Data
    public static class AiAnalysisResult {
        private Integer score;
        private String status;
        private String description;
        private String analysis;
    }

    @lombok.Data
    @lombok.AllArgsConstructor
    public static class AnalysisResult {
        private Integer cameraId;
        private Integer activityScore;
        private String status;
        private String description;
        private String analysisResult;
    }
}
