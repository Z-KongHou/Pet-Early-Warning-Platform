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
        return "请分析这张仓鼠的图片，评估其活动量状态。\n" +
                "请以JSON格式返回，包含以下字段：\n" +
                "- score: 活动量评分(0-100的整数)\n" +
                "- status: 活动状态(low/normal/high)\n" +
                "- description: 活动描述(中文)\n" +
                "- analysis: 详细分析(中文)\n" +
                "注意：只返回JSON，不要其他文字。";
    }

    private String callAiApi(String prompt) throws JsonProcessingException {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        headers.set("Authorization", "Bearer " + aiProperties.getApiKey());

        List<AiChatRequest.Message> messages = new ArrayList<>();
        messages.add(new AiChatRequest.Message("system", "你是一个专业的宠物健康分析助手。"));
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
        throw new RuntimeException("AI响应为空");
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
            description = "仓鼠活动较少，建议关注";
        } else if (score > 80) {
            status = "high";
            description = "仓鼠活动频繁，非常健康";
        } else {
            status = "normal";
            description = "仓鼠活动正常";
        }

        return new AnalysisResult(
                cameraId,
                score,
                status,
                description,
                "注意：这是备用分析结果，AI接口调用失败。请检查网络连接和API配置。"
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