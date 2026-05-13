package com.hamster.yingshi.dto;

import lombok.Data;
import java.time.LocalDate;
import java.math.BigDecimal;

@Data
public class HamsterRequest {
    private String name;
    private String breed;
    private LocalDate birthDate;
    private Integer gender;
    private BigDecimal weight;
    private String avatar;
    private String remark;
    private Integer healthStatus;
}