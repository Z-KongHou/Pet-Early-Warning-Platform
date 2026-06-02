package com.hamster.yingshi.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

@Data
@Component
@ConfigurationProperties(prefix = "ai")
public class AiProperties {
    private String model;
    private String apiUrl;
    private String apiKey;
    private Integer timeout;
    private String serviceUrl = "http://127.0.0.1:8000";
}