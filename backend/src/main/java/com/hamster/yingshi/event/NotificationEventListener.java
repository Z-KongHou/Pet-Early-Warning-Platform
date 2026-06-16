package com.hamster.yingshi.event;

import com.hamster.yingshi.entity.Alert;
import com.hamster.yingshi.entity.Camera;
import com.hamster.yingshi.entity.Message;
import com.hamster.yingshi.service.MessageService;
import com.hamster.yingshi.service.SseService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.context.event.EventListener;
import org.springframework.stereotype.Component;

/**
 * Listens for newly created alerts and handles the notification side:
 * <ol>
 *   <li>Persists a {@link Message} record (persistent fallback for SSE)</li>
 *   <li>Pushes the alert via SSE to connected clients</li>
 * </ol>
 *
 * <p>The two actions are independent — failure in one does not block the other.</p>
 */
@Component
public class NotificationEventListener {

    private static final Logger log = LoggerFactory.getLogger(NotificationEventListener.class);

    @Autowired
    private MessageService messageService;

    @Autowired
    private SseService sseService;

    @EventListener
    public void onAlertCreated(AlertCreatedEvent event) {
        Alert alert = event.getAlert();
        Camera camera = event.getCamera();

        // 1. Create persistent message record (fallback for missed SSE)
        Integer messageId = null;
        try {
            Message message = new Message();
            message.setHamsterId(alert.getHamsterId());
            message.setAlertId(alert.getId());
            message.setUserId(alert.getUserId());
            message.setTitle(buildTitle(alert));
            message.setContent(buildContent(alert));
            message.setIsRead(0);
            message.setIsDeleted(0);
            messageService.create(message);
            messageId = message.getId();
            log.info("Message created: id={}, alertId={}, userId={}",
                    messageId, alert.getId(), alert.getUserId());
        } catch (Exception e) {
            log.error("Failed to create message for alertId={}: {}", alert.getId(), e.getMessage());
        }

        // 2. Push SSE to connected frontend clients
        try {
            SseService.AlertPayload payload = new SseService.AlertPayload(
                    alert.getId(),
                    messageId,
                    alert.getHamsterId(),
                    alert.getActivityStatus(),
                    alert.getActivityScore(),
                    buildTitle(alert),
                    buildContent(alert),
                    alert.getCreatedAt() != null ? alert.getCreatedAt().toString() : null
            );
            sseService.sendToUser(alert.getUserId(), payload);
        } catch (Exception e) {
            log.error("Failed to push SSE for alertId={}: {}", alert.getId(), e.getMessage());
        }
    }

    private String buildTitle(Alert alert) {
        if ("high".equals(alert.getActivityStatus())) {
            return "活动预警：仓鼠活动异常";
        } else if ("low".equals(alert.getActivityStatus())) {
            return "活动提醒：仓鼠活动偏低";
        }
        return "仓鼠活动通知";
    }

    private String buildContent(Alert alert) {
        return String.format(
                "活动状态：%s，活动评分：%d（预警阈值：%d）",
                alert.getActivityStatus(), alert.getActivityScore(), alert.getThreshold()
        );
    }
}
