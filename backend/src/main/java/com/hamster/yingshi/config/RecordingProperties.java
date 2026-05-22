package com.hamster.yingshi.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

@Data
@Component
@ConfigurationProperties(prefix = "recording")
public class RecordingProperties {
    private boolean enabled = true;
    private int durationSeconds = 60;
    private String storagePath = "./video";
    private String ffmpegPath = "ffmpeg";
}
