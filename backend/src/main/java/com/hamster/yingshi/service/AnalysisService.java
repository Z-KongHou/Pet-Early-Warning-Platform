package com.hamster.yingshi.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.hamster.yingshi.config.AiProperties;
import com.hamster.yingshi.dto.AiChatRequest;
import com.hamster.yingshi.dto.AiChatResponse;
import org.springframework.beans.factory.annotation.Autowired;
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

    @Autowired
    private AiProperties aiProperties;

    @Autowired
    private ObjectMapper objectMapper;

    private final RestTemplate restTemplate = new RestTemplate();

    public AnalysisResult analyzeActivity(Integer cameraId, String imageUrl) {
        try {
            String prompt = buildPrompt(imageUrl);
            String aiResponse = callAiApi(prompt);
            return parseAiResponse(aiResponse, cameraId);
        } catch (Exception e) {
            e.printStackTrace();
            return generateFallbackResult(cameraId);
        }
    }

    private String buildPrompt(String imageUrl) {
        return "Analyze this hamster image and assess its activity level.\n" +
                "Return JSON only with the following fields:\n" +
                "- score: activity score (integer 0-100)\n" +
                "- status: activity status (low/normal/high)\n" +
                "- description: activity description (in English)\n" +
                "- analysis: detailed analysis (in English)\n" +
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
                    result.getScore(),
                    result.getStatus(),
                    result.getDescription(),
                    result.getAnalysis()
            );
        } catch (Exception e) {
            e.printStackTrace();
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

    private AnalysisResult generateFallbackResult(Integer cameraId) {
        Random random = new Random();
        int score = random.nextInt(101);
        String status;
        String description;

        if (score < 30) {
            status = "low";
            description = "Hamster activity is low; monitoring recommended";
        } else if (score > 80) {
            status = "high";
            description = "Hamster is very active and appears healthy";
        } else {
            status = "normal";
            description = "Hamster activity is normal";
        }

        return new AnalysisResult(
                cameraId,
                score,
                status,
                description,
                "Note: this is a fallback result because the AI API call failed. Check network connectivity and API configuration."
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