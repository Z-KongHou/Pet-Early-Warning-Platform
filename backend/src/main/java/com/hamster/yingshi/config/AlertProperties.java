package com.hamster.yingshi.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

import java.time.Duration;
import java.util.HashMap;
import java.util.Map;

@Data
@Component
@ConfigurationProperties(prefix = "alert")
public class AlertProperties {

    /**
     * Which activity statuses trigger alert creation.
     * Default: only "high" (mapped from AI "critical") triggers alerts.
     * Set {@code alert.triggers.low=true} in application.yml to also trigger on "low".
     */
    private Map<String, Boolean> triggers = new HashMap<>();
    {
        triggers.put("high", true);
        triggers.put("low", false);
    }

    /**
     * Dedup time window per (hamster_id, activity_status).
     * Within this window, only the first alert is created; subsequent analyses
     * with the same status are silently skipped.
     */
    private Map<String, Duration> dedupWindows = new HashMap<>();
    {
        dedupWindows.put("high", Duration.ofMinutes(30));
        dedupWindows.put("low", Duration.ofMinutes(60));
    }

    /**
     * Default threshold value written into the alert record.
     */
    private int defaultThreshold = 30;
}
