package com.hamster.yingshi.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.AllArgsConstructor;
import lombok.Data;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.io.IOException;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CopyOnWriteArrayList;

/**
 * Manages per-user SSE connections for real-time alert push.
 *
 * <h3>Multi-instance note</h3>
 * This implementation stores emitters in local JVM memory. In a multi-node
 * deployment, an alert created on node A will not reach SSE clients connected
 * to node B. Redis pub/sub or a message broker is the natural upgrade path.
 */
@Service
public class SseService {

    private static final Logger log = LoggerFactory.getLogger(SseService.class);
    private static final long SSE_TIMEOUT = 30 * 60 * 1000L; // 30 minutes

    private final ConcurrentHashMap<Integer, List<SseEmitter>> userEmitters = new ConcurrentHashMap<>();
    private final ObjectMapper objectMapper = new ObjectMapper();

    /**
     * Register a new SSE connection for the given user.
     *
     * @param userId the authenticated user id
     * @return a ready SseEmitter (caller should return it from the controller)
     */
    public SseEmitter subscribe(Integer userId) {
        SseEmitter emitter = new SseEmitter(SSE_TIMEOUT);

        userEmitters.computeIfAbsent(userId, k -> new CopyOnWriteArrayList<>()).add(emitter);

        emitter.onCompletion(() -> removeEmitter(userId, emitter));
        emitter.onTimeout(() -> removeEmitter(userId, emitter));
        emitter.onError(e -> removeEmitter(userId, emitter));

        // Send "connected" event so the client knows it's ready
        try {
            emitter.send(SseEmitter.event()
                    .name("connected")
                    .data("{\"userId\":" + userId + ",\"message\":\"SSE connected\"}"));
        } catch (IOException e) {
            removeEmitter(userId, emitter);
        }

        log.info("SSE subscribed: userId={}, activeConnections={}", userId, countEmitters(userId));
        return emitter;
    }

    /**
     * Push an alert to all active SSE connections for a user.
     * If no connections exist the alert is silently skipped — the user will
     * pick it up via the polling fallback ({@code GET /api/messages/unread-count}).
     */
    public void sendToUser(Integer userId, AlertPayload payload) {
        List<SseEmitter> emitters = userEmitters.get(userId);
        if (emitters == null || emitters.isEmpty()) {
            log.debug("No active SSE connections for userId={}, alertId={}", userId, payload.getAlertId());
            return;
        }

        String json;
        try {
            json = objectMapper.writeValueAsString(payload);
        } catch (JsonProcessingException e) {
            log.error("Failed to serialize SSE payload for alertId={}: {}", payload.getAlertId(), e.getMessage());
            return;
        }

        int pushed = 0;
        for (SseEmitter emitter : emitters) {
            try {
                emitter.send(SseEmitter.event()
                        .name("alert")
                        .data(json));
                pushed++;
            } catch (IOException e) {
                log.warn("SSE push failed, removing emitter: userId={}, error={}", userId, e.getMessage());
                removeEmitter(userId, emitter);
            }
        }
        log.info("SSE alert pushed: userId={}, alertId={}, pushedTo={}/{}",
                userId, payload.getAlertId(), pushed, emitters.size());
    }

    /**
     * Send a heartbeat comment every 30 seconds to keep connections alive
     * and detect disconnected clients early.
     */
    @Scheduled(fixedRate = 30000)
    public void sendHeartbeats() {
        if (userEmitters.isEmpty()) {
            return;
        }
        int total = 0;
        for (Map.Entry<Integer, List<SseEmitter>> entry : userEmitters.entrySet()) {
            for (SseEmitter emitter : entry.getValue()) {
                try {
                    emitter.send(SseEmitter.event()
                            .name("heartbeat")
                            .data("{}"));
                    total++;
                } catch (IOException e) {
                    removeEmitter(entry.getKey(), emitter);
                }
            }
        }
        if (total > 0) {
            log.debug("SSE heartbeat sent to {} emitters", total);
        }
    }

    private void removeEmitter(Integer userId, SseEmitter emitter) {
        List<SseEmitter> emitters = userEmitters.get(userId);
        if (emitters != null) {
            emitters.remove(emitter);
            if (emitters.isEmpty()) {
                userEmitters.remove(userId);
            }
            log.debug("SSE emitter removed: userId={}, remaining={}", userId,
                    emitters.isEmpty() ? 0 : emitters.size());
        }
    }

    private int countEmitters(Integer userId) {
        List<SseEmitter> emitters = userEmitters.get(userId);
        return emitters == null ? 0 : emitters.size();
    }

    // ------------------------------------------------------------------

    @Data
    @AllArgsConstructor
    public static class AlertPayload {
        private Integer alertId;
        private Integer messageId;
        private Integer hamsterId;
        private String activityStatus;
        private Integer activityScore;
        private String title;
        private String content;
        private String createdAt;
    }
}
