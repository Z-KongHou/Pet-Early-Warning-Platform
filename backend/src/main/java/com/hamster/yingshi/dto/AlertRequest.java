package com.hamster.yingshi.dto;

import lombok.Data;

@Data
public class AlertRequest {
    private Integer hamsterId;
    private String activityStatus;
    private Integer activityScore;
    private Integer threshold;
    private String imageUrl;
}