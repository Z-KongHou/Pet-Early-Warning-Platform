package com.hamster.yingshi.dto;

import lombok.Data;

@Data
public class AlertStatusRequest {
    private Integer status;
    private String handleRemark;
}