package com.hamster.yingshi.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;
import java.time.LocalDateTime;

@Data
@TableName("pet_analysis")
public class PetAnalysis {
    @TableId(value = "id", type = IdType.AUTO)
    private Long id;

    private Integer userId;

    private String cameraId;

    private LocalDateTime timestamp;

    private Integer hasPet;

    private String movementState;

    private String foodState;

    private Integer positionX;

    private Integer positionY;

    private Integer positionWidth;

    private Integer positionHeight;

    private Double confidence;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;
}
