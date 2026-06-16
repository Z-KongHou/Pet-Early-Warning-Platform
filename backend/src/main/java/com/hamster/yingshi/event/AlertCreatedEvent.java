package com.hamster.yingshi.event;

import com.hamster.yingshi.entity.Alert;
import com.hamster.yingshi.entity.Camera;
import org.springframework.context.ApplicationEvent;

/**
 * Published after an alert has been successfully persisted.
 * Downstream listeners handle notification creation and SSE push.
 */
public class AlertCreatedEvent extends ApplicationEvent {

    private final Alert alert;
    private final Camera camera;

    public AlertCreatedEvent(Object source, Alert alert, Camera camera) {
        super(source);
        this.alert = alert;
        this.camera = camera;
    }

    public Alert getAlert() {
        return alert;
    }

    public Camera getCamera() {
        return camera;
    }
}
