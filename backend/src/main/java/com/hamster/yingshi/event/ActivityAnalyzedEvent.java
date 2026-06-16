package com.hamster.yingshi.event;

import com.fasterxml.jackson.databind.JsonNode;
import com.hamster.yingshi.entity.Camera;
import org.springframework.context.ApplicationEvent;

/**
 * Published by {@code FrameCaptureService} after each successful AI analysis.
 * Downstream listeners can react without coupling to the capture/analysis flow.
 */
public class ActivityAnalyzedEvent extends ApplicationEvent {

    private final Camera camera;
    private final JsonNode analysisResult;

    public ActivityAnalyzedEvent(Object source, Camera camera, JsonNode analysisResult) {
        super(source);
        this.camera = camera;
        this.analysisResult = analysisResult;
    }

    public Camera getCamera() {
        return camera;
    }

    public JsonNode getAnalysisResult() {
        return analysisResult;
    }
}
