package com.hamster.yingshi.event;

import com.fasterxml.jackson.databind.JsonNode;
import com.hamster.yingshi.config.AlertProperties;
import com.hamster.yingshi.entity.Alert;
import com.hamster.yingshi.entity.Camera;
import com.hamster.yingshi.service.AlertService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.context.event.EventListener;
import org.springframework.stereotype.Component;

import java.time.Duration;

/**
 * Listens for completed AI analyses and decides whether to create an alert.
 *
 * <p>This listener is intentionally <b>synchronous</b> — alert creation is a
 * lightweight DB insert that completes in milliseconds.  Async is unnecessary
 * given the 5-minute scheduling interval.</p>
 */
@Component
public class AlertEventListener {

    private static final Logger log = LoggerFactory.getLogger(AlertEventListener.class);

    @Autowired
    private AlertProperties alertProperties;

    @Autowired
    private AlertService alertService;

    @Autowired
    private ApplicationEventPublisher eventPublisher;

    @EventListener
    public void onActivityAnalyzed(ActivityAnalyzedEvent event) {
        Camera camera = event.getCamera();
        JsonNode result = event.getAnalysisResult();

        // 1. Map AI python status → DB status (same convention as FrameCaptureService)
        String rawStatus = result.path("activity_status").asText("normal");
        String mappedStatus = mapActivityStatus(rawStatus);
        int activityScore = result.path("activity_score").asInt(50);

        // 2. Check whether this status is configured to trigger alerts
        if (!alertProperties.getTriggers().getOrDefault(mappedStatus, false)) {
            log.debug("Status '{}' not in trigger whitelist for hamsterId={}, skipping",
                    mappedStatus, camera.getHamsterId());
            return;
        }

        // 3. Dedup: skip if an alert for (hamster, status) already exists within the window
        Duration window = alertProperties.getDedupWindows()
                .getOrDefault(mappedStatus, Duration.ofMinutes(30));
        if (alertService.hasDuplicateWithinWindow(camera.getHamsterId(), mappedStatus, window)) {
            log.info("Dedup hit: hamsterId={}, status={}, window={} — alert suppressed",
                    camera.getHamsterId(), mappedStatus, window);
            return;
        }

        // 4. Create the alert
        Alert alert = new Alert();
        alert.setUserId(camera.getUserId());
        alert.setHamsterId(camera.getHamsterId());
        alert.setActivityStatus(mappedStatus);
        alert.setActivityScore(activityScore);
        alert.setThreshold(alertProperties.getDefaultThreshold());
        alert.setImageUrl(null);
        alert.setStatus(0); // pending
        alert.setIsDeleted(0);
        alertService.create(alert);

        log.info("Alert created: id={}, hamsterId={}, status={}, score={}",
                alert.getId(), camera.getHamsterId(), mappedStatus, activityScore);

        // 5. Publish downstream event for notification + SSE push
        eventPublisher.publishEvent(new AlertCreatedEvent(this, alert, camera));
    }

    /**
     * Maps AI service (Python) status strings to database values.
     * Consistent with {@code FrameCaptureService.mapActivityStatus}.
     */
    static String mapActivityStatus(String pythonStatus) {
        if (pythonStatus == null) {
            return "normal";
        }
        switch (pythonStatus) {
            case "critical":
                return "high";
            case "low":
            case "high":
            case "normal":
                return pythonStatus;
            default:
                return "normal";
        }
    }
}
