package com.hamster.yingshi.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

@Data
@Component
@ConfigurationProperties(prefix = "recording")
public class RecordingProperties {
    private boolean enabled = true;
    private int durationSeconds = 300;
    private Long spaceId;
    private Long templateId;
    private String spaceName = "hamster_default";
    private int expireDays = 7;
}
