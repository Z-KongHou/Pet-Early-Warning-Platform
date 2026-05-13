package com.hamster.yingshi.dto;

import lombok.Data;

@Data
public class CameraRequest {
    private Integer hamsterId;
    private String name;
    private String deviceKey;
    private Integer channelNo;
}