package com.hamster.yingshi.dto;

import lombok.Data;

@Data
public class CameraTokenRequest {
    private String accessToken;
    private String tokenExpires;
}