package com.hamster.yingshi.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;
import java.time.LocalDateTime;

@Data
@TableName("pet_state")
public class PetState {
    @TableId(value = "id", type = IdType.AUTO)
    private Long id;

    private Integer userId;

    private String cameraId;

    private Integer lastPositionX;

    private Integer lastPositionY;

    private Integer lastPositionWidth;

    private Integer lastPositionHeight;

    private LocalDateTime lastEatingTime;

    private LocalDateTime stationaryStartTime;

    private Integer foodBowlPositionX;

    private Integer foodBowlPositionY;

    private Integer foodBowlPositionWidth;

    private Integer foodBowlPositionHeight;

    private Integer totalAnalyses;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedAt;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;
}
