package com.hamster.yingshi.dto;

import lombok.Data;

@Data
public class AnalysisRequest {
    private Integer cameraId;
    private String imageUrl;
}